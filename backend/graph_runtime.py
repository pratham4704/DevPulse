"""
DevPulse — Web Runtime for the LangGraph Multi-Agent Graph
=============================================================
This is the web-layer counterpart to langgraph_agent.py (Phase 4 of the
capstone manual). Same router -> conditional edge -> specialist topology,
same tool scoping per specialist, same real MCP server underneath. Two
things are swapped so it can run behind a WebSocket instead of a CLI:

  1. Human-in-the-loop approval: instead of blocking on input(), each
     specialist emits a "tool_pending" event and awaits an asyncio.Future
     that the WebSocket handler resolves when the browser sends
     approve/reject.
  2. Progress: instead of print(), each step emits a structured event
     dict onto an asyncio.Queue-like callback that the WebSocket handler
     forwards to the client as JSON.

The graph "shape" (router, 3 specialists, tool scoping) is unchanged from
langgraph_agent.py -- see that file for the original CLI reference
implementation this is adapted from.
"""

import json
import uuid
import asyncio
from typing import TypedDict, Optional, Callable, Awaitable

from model_client import get_client_and_model
from mcp_bridge import mcp_session, discover_openai_tools, call_mcp_tool

client, MODEL, BACKEND = get_client_and_model()


class DevPulseState(TypedDict):
    query: str
    history: list
    category: str
    tool_calls_made: list
    answer: str


CATEGORY_LABELS = {
    "repo_info": "Repo Analyst",
    "issue_triage": "Issue Triage Agent",
    "release_notes": "Release Notes Agent",
}

SPECIALIST_TOOLS = {
    "repo_info": {"search_repositories", "get_repo_details", "list_contributors"},
    "issue_triage": {"list_open_issues"},
    "release_notes": {"get_latest_release"},
}

SPECIALIST_PERSONAS = {
    "repo_info": (
        "You are the Repo Analyst. Use search_repositories or get_repo_details "
        "or list_contributors to answer with real, current GitHub data."
    ),
    "issue_triage": (
        "You are the Issue Triage Agent. Use list_open_issues to answer with "
        "real, currently-open issues. Briefly note priority where relevant."
    ),
    "release_notes": (
        "You are the Release Notes Agent. Use get_latest_release to answer "
        "with the real, current latest version and notes."
    ),
}


class DevPulseRuntime:
    """One instance per browser connection. Holds conversation history and
    the pending-approval future for the tool call currently awaiting a
    human decision."""

    def __init__(self):
        self.history: list = []
        self._pending_approval: Optional[asyncio.Future] = None
        self._pending_call_id: Optional[str] = None

    def resolve_approval(self, call_id: str, approved: bool):
        """Called by the WebSocket handler when the browser sends a decision."""
        if self._pending_approval and call_id == self._pending_call_id and not self._pending_approval.done():
            self._pending_approval.set_result(approved)

    async def _await_approval(self, call_id: str) -> bool:
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_approval = fut
        self._pending_call_id = call_id
        try:
            return await fut
        finally:
            self._pending_approval = None
            self._pending_call_id = None

    async def classify(self, query: str) -> str:
        prompt = (
            "Classify this GitHub-related query into exactly one category:\n"
            "repo_info, issue_triage, release_notes\n\n"
            "repo_info = general repo stats, search, contributors\n"
            "issue_triage = anything about open issues\n"
            "release_notes = anything about latest release/version\n\n"
            f"Query: {query}\n\nReply with ONLY one of the three words."
        )
        result = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}]
        )
        category = result.choices[0].message.content.strip().lower()
        valid = {"repo_info", "issue_triage", "release_notes"}
        return category if category in valid else "repo_info"

    async def run_turn(self, query: str, emit: Callable[[dict], Awaitable[None]]):
        """Runs one full turn: classify -> route -> specialist -> (HITL per
        tool call) -> synthesize answer. Emits structured events via `emit`
        as it goes."""

        await emit({"type": "status", "stage": "classifying"})
        category = await self.classify(query)
        label = CATEGORY_LABELS[category]
        await emit({"type": "routed", "category": category, "label": label})

        allowed_tools = SPECIALIST_TOOLS[category]
        persona = SPECIALIST_PERSONAS[category]

        async with mcp_session() as session:
            all_tools = await discover_openai_tools(session)
            scoped_tools = [t for t in all_tools if t["function"]["name"] in allowed_tools]

            messages = [{"role": "system", "content": persona}] + self.history + [
                {"role": "user", "content": query}
            ]

            response = client.chat.completions.create(
                model=MODEL, messages=messages, tools=scoped_tools, tool_choice="auto"
            )
            msg = response.choices[0].message

            tool_results_for_followup = []

            if response.choices[0].finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)
                    call_id = str(uuid.uuid4())

                    await emit({
                        "type": "tool_pending",
                        "call_id": call_id,
                        "tool": tc.function.name,
                        "args": args,
                        "category": category,
                    })

                    approved = await self._await_approval(call_id)

                    if not approved:
                        await emit({
                            "type": "tool_denied",
                            "call_id": call_id,
                            "tool": tc.function.name,
                        })
                        tool_results_for_followup.append((tc, "Tool execution denied by human reviewer."))
                        continue

                    await emit({
                        "type": "tool_running",
                        "call_id": call_id,
                        "tool": tc.function.name,
                    })

                    result_text = await call_mcp_tool(session, tc.function.name, args)

                    await emit({
                        "type": "tool_result",
                        "call_id": call_id,
                        "tool": tc.function.name,
                        "result": result_text,
                    })

                    tool_results_for_followup.append((tc, result_text))

                follow_up = messages + [
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                    }
                ] + [
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                    for tc, result in tool_results_for_followup
                ]

                await emit({"type": "status", "stage": "synthesizing"})
                final = client.chat.completions.create(model=MODEL, messages=follow_up)
                answer = final.choices[0].message.content
            else:
                answer = msg.content

            self.history.append({"role": "user", "content": query})
            self.history.append({"role": "assistant", "content": answer})

            await emit({
                "type": "final_answer",
                "category": category,
                "label": label,
                "answer": answer,
            })
