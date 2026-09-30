

 
import os
import sys
 
 
def get_client_and_model():
    """Returns (client, model_name, backend). client exposes .chat.completions.create(...)
    with the same signature regardless of backend."""
    backend = os.environ.get("LLM_BACKEND", "ollama" if not os.environ.get("GROQ_API_KEY") else "groq").lower()
 
    if backend == "groq":
        from groq import Groq
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        return client, model, "groq"
 
    # -- Ollama, via its OpenAI-compatible endpoint --------------------------
    # Same base_url pattern used by the AutoGen/LangGraph labs' config_list:
    # http://localhost:11434/v1 — the api_key is a required-but-unchecked
    # placeholder, exactly like in those labs.
    from openai import OpenAI
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    client = OpenAI(base_url=base_url, api_key="ollama")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    return client, model, "ollama"
 
 
def check_connection(client, model, backend):
    """Friendly pre-flight check, same idea as the MCP capstone's call_qwen
    test — fail with a clear, backend-specific message instead of a raw
    connection traceback."""
    try:
        client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Say OK in one word"}], max_tokens=5
        )
        print("after api call")
        return True
    except Exception as e:
        if backend == "ollama":
            print(f"\nCould not reach Ollama at the configured base_url.", file=sys.stderr)
            print(f"  1) Is it running?  ->  ollama serve", file=sys.stderr)
            print(f"  2) Is the model pulled?  ->  ollama pull {model}", file=sys.stderr)
        else:
            print(f"\nCould not reach Groq.", file=sys.stderr)
            print(f"  Check that GROQ_API_KEY is set correctly.", file=sys.stderr)
        print(f"  Underlying error: {e}\n", file=sys.stderr)
        return False
 
 
"""
=============================================================
DevPulse — Agent Core
Model + Tools + Memory + Human-in-the-Loop (HITL)
 
Flow:
User
   ↓
LLM (Reason)
   ↓
Select Tool
   ↓
Human Approval
   ↓
MCP Tool
   ↓
GitHub API
   ↓
LLM Response
=============================================================
"""
 
import json
import asyncio
 
from model_client import get_client_and_model, check_connection
from mcp_bridge import mcp_session, discover_openai_tools, call_mcp_tool
 
 
SYSTEM_PROMPT = (
    "You are DevPulse, an assistant that answers questions about GitHub "
    "repositories using real, live tools. Always use a tool to look up facts "
    "instead of guessing. Remember repo names mentioned earlier in the "
    "conversation so the user doesn't have to repeat them."
)
 
 
class DevPulseAgent:
 
    def __init__(self):
        self.client, self.model, self.backend = get_client_and_model()
        self.history = []
 
    async def ask(self, user_input: str, max_loops: int = 4) -> str:
 
        self.history.append(
            {
                "role": "user",
                "content": user_input
            }
        )
 
        async with mcp_session() as session:
 
            # Discover MCP tools dynamically
            tools = await discover_openai_tools(session)
 
            for _ in range(max_loops):
 
                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    }
                ] + self.history
 
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto"
                )
 
                msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason
 
                # No tool required → Final Answer
                if finish_reason != "tool_calls" or not msg.tool_calls:
 
                    self.history.append(
                        {
                            "role": "assistant",
                            "content": msg.content
                        }
                    )
 
                    return msg.content
 
                # Store assistant tool request
                self.history.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            tc.model_dump()
                            for tc in msg.tool_calls
                        ]
                    }
                )
 
                # Execute each tool requested by the LLM
                for tool_call in msg.tool_calls:
 
                    args = json.loads(tool_call.function.arguments)
 
                    print("\n")
                    print("=" * 60)
                    print(" HUMAN-IN-THE-LOOP APPROVAL ")
                    print("=" * 60)
                    print(f"Tool Selected : {tool_call.function.name}")
                    print(f"Arguments     : {args}")
                    print("=" * 60)
 
                    approval = input(
                        "Approve tool execution? (y/n): "
                    ).strip().lower()
 
                    if approval != "y":
 
                        print("\n❌ Tool execution rejected by human.\n")
 
                        self.history.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": "Tool execution denied by human reviewer."
                            }
                        )
 
                        continue
 
                    print("\n✅ Human approved.")
                    print("Executing MCP Tool...\n")
 
                    result_text = await call_mcp_tool(
                        session,
                        tool_call.function.name,
                        args
                    )
 
                    print("=" * 60)
                    print(" TOOL RESULT ")
                    print("=" * 60)
                    print(result_text)
                    print("=" * 60)
 
                    # Feed tool result back to LLM
                    self.history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        }
                    )
 
        return "I wasn't able to resolve this within the allotted reasoning steps."
 
 
async def main():
 
    agent = DevPulseAgent()
 
    if not check_connection(
        agent.client,
        agent.model,
        agent.backend
    ):
        return
 
    print("\n")
    print("=" * 70)
    print(" DevPulse Agent with Human-in-the-Loop ")
    print("=" * 70)
    print(f"Model : {agent.model}")
    print("Type 'quit' to exit.")
    print("=" * 70)
 
    while True:
 
        user_input = input("\nYou : ").strip()
 
        if user_input.lower() == "quit":
            break
 
        if not user_input:
            continue
 
        answer = await agent.ask(user_input)
 
        print("\n")
        print("=" * 70)
        print(" DevPulse Response ")
        print("=" * 70)
        print(answer)
        print("=" * 70)
 
 
if __name__ == "__main__":
    asyncio.run(main())
 