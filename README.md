# DevPulse — Multi-Agent GitHub AI Assistant

Built in the five phases from the capstone manual, plus a web frontend on
top of the CLI phases.

## Phases (backend/)

| Phase | File(s) | What it proves |
|---|---|---|
| 1 — Real MCP Server & Protocol Test | `mcp_server.py`, `mcp_client_test.py` | A FastMCP server exposing 5 real GitHub tools, 1 resource, 1 prompt — proven with the raw MCP handshake (`initialize → list_tools → call_tool`), no LLM involved. |
| 2 — Shared Infrastructure | `model_client.py`, `mcp_bridge.py` | Backend-agnostic LLM client (Ollama/Groq) and a generic MCP↔OpenAI schema bridge, reusable by any agent framework. |
| 3 — Single ReAct Agent + HITL | `agent_core.py` | One agent: Model + Tools + Memory + Human-in-the-Loop approval (CLI `input()` prompt), talking to the real MCP server. |
| 4 — LangGraph Multi-Agent | `langgraph_agent.py` | Router node classifies intent → conditional edge dispatches to one of 3 scoped specialist nodes, all sharing one MCP session. |
| 5 — A2A Agent Card | `a2a_card.py` | Publishes DevPulse as a discoverable `AgentCard` — only the 3 skills are visible externally, never the MCP server, GitHub API, or LangGraph internals underneath. |

Run any phase standalone from `backend/` (after `pip install -r requirements.txt`):
```bash
python mcp_client_test.py     # Phase 1
python agent_core.py          # Phase 3
python langgraph_agent.py     # Phase 4
python a2a_card.py            # Phase 5 demo
```

## Web layer (on top of Phase 4)

```
┌─────────────┐   WebSocket    ┌──────────────────┐   stdio (MCP)   ┌────────────────┐
│  React UI   │ ─────────────▶ │  FastAPI server   │ ──────────────▶ │  mcp_server.py  │ ──▶ api.github.com
│  (frontend) │ ◀───────────── │  (graph_runtime)  │ ◀────────────── │  (5 real tools) │
└─────────────┘   JSON events  └──────────────────┘   tool results  └────────────────┘
```

`graph_runtime.py` is the same router → specialist topology as
`langgraph_agent.py`, with two changes so a browser can drive it:

- **HITL approval**: `langgraph_agent.py`'s blocking `input()` becomes an
  `asyncio.Future` that `server.py`'s WebSocket handler resolves when the
  browser sends an approve/reject decision.
- **Progress**: `print()` calls become structured JSON events
  (`routed`, `tool_pending`, `tool_running`, `tool_result`, `final_answer`)
  streamed live to the UI.

`server.py` is the FastAPI + WebSocket entry point that wraps it.

## Two real bugs this codebase already fixes

Both are called out in the capstone manual as genuinely instructive —
worth knowing cold for a walkthrough:

1. **Environment doesn't reach the subprocess.** `StdioServerParameters`
   does not inherit the parent's environment by default, so without
   `env=os.environ.copy()` in `mcp_bridge.py`, the MCP server subprocess
   never sees `GITHUB_TOKEN` — it silently runs unauthenticated (60 req/hr
   instead of 5,000). Already fixed in `mcp_bridge.py` and
   `mcp_client_test.py`.
2. **stdout/stderr protocol corruption.** On the stdio transport, stdout is
   reserved exclusively for MCP's JSON-RPC messages — any stray `print()`
   in the server corrupts the stream (`"Failed to parse JSON-RPC message
   from server"`). `mcp_server.py` sends every log line to `stderr`
   explicitly.

## Windows-specific fixes (this fork vs. the manual's reference code)

- **`mcp_bridge.py`** launches the MCP server with `sys.executable`
  instead of the manual's hardcoded `command="python"` — Windows doesn't
  reliably expose a `python` that resolves to the active venv, which
  surfaced as `FileNotFoundError: [WinError 2]`.
- **`server.py`** sets `asyncio.WindowsProactorEventLoopPolicy()` at
  import time on Windows — the default `SelectorEventLoop` can't spawn
  subprocesses, which is what MCP's stdio transport needs
  (`NotImplementedError` otherwise).
- **`requirements.txt`** pins `mcp[cli]>=1.2.0,<2.0.0`. `mcp` 2.0.0 is a
  breaking rewrite that removes `mcp.server.fastmcp` entirely
  (`ModuleNotFoundError`), which `mcp_server.py` needs.

## Run it

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env   # then fill in GITHUB_TOKEN etc. (see manual's env table)

uvicorn server:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open the printed localhost URL. Connects to `ws://localhost:8000/ws` by
default — override with `VITE_WS_URL` in a frontend `.env`.

## UI

- **Left — Roster**: the three specialists as a live graph. The router
  node pulses while classifying, then a signal travels to whichever
  specialist gets the handoff.
- **Center — Chat**: every tool call surfaces as an approval card —
  nothing hits the GitHub API until you click *Approve & run*.
- **Right — Ledger**: a running audit trail of every tool call this
  session — name, arguments, status, and result.
