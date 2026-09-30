"""
DevPulse — FastAPI + WebSocket server
=============================================================
Web-layer entry point, sitting on top of graph_runtime.py (the WebSocket
adaptation of langgraph_agent.py / Phase 4). One WebSocket connection = one
DevPulseRuntime (own conversation history + own pending-approval state).

The browser sends:
    {"type": "query", "text": "..."}
    {"type": "approve", "call_id": "...", "approved": true|false}

The server streams back the structured events emitted by
graph_runtime.DevPulseRuntime.run_turn(), plus a couple of framing
events ("turn_start" / "turn_end" / "error").
"""

import sys
import asyncio

# On Windows, asyncio's default SelectorEventLoop cannot spawn subprocesses
# (NotImplementedError from _make_subprocess_transport) -- and MCP's stdio
# transport needs to launch mcp_server.py as a subprocess. This must be set
# at import time, before uvicorn creates its event loop -- setting it only
# inside `if __name__ == "__main__"` is too late when running via the
# `uvicorn server:app` CLI command (as opposed to `python server.py`).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()  # reads backend/.env, if present, into os.environ

import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from graph_runtime import DevPulseRuntime

app = FastAPI(title="DevPulse")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    runtime = DevPulseRuntime()

    async def emit(event: dict):
        await websocket.send_json(event)

    try:
        while True:
            msg = await websocket.receive_json()

            if msg.get("type") == "query":
                query = (msg.get("text") or "").strip()
                if not query:
                    continue
                await emit({"type": "turn_start", "query": query})
                try:
                    await runtime.run_turn(query, emit)
                except Exception as e:
                    traceback.print_exc()
                    await emit({"type": "error", "message": str(e)})
                await emit({"type": "turn_end"})

            elif msg.get("type") == "approve":
                call_id = msg.get("call_id")
                approved = bool(msg.get("approved"))
                runtime.resolve_approval(call_id, approved)

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
