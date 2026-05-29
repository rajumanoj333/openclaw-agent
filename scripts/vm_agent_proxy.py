"""
OpenClaw subprocess wrapper.

Run on the VM next to OpenClaw. Exposes a tiny HTTP API on 127.0.0.1:9000
so the laptop's FastAPI gateway (over SSH tunnel) can submit a user message
and get the agent's reply text back as JSON.

Usage:
    pip install fastapi uvicorn
    python3 vm_agent_proxy.py

Endpoints:
    GET  /health                  -> {"status": "ok"}
    POST /agent     body: {"message": "...", "agent": "main", "timeout": 90}
                    -> {"reply": "...", "session_id": "...", "model": "...", "ms": 12345}
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "openclaw")
DEFAULT_AGENT = os.environ.get("OPENCLAW_AGENT", "main")
DEFAULT_TIMEOUT = int(os.environ.get("OPENCLAW_TIMEOUT", "120"))

# Per-phone (or per-session) lock map. OpenClaw stores per-session memory in
# a single JSONL file with a write lock; concurrent CLI calls for the same
# session collide and one fails with SessionWriteLockTimeoutError. Serialize
# them at the proxy so callers queue up instead of stomping the lock.
_session_locks: dict[str, asyncio.Lock] = {}


def _session_key(req: "AgentRequest") -> str:
    """Pick a stable key per logical session — to, session_id, or agent."""
    return req.session_id or req.to or req.agent or "default"


def _get_lock(key: str) -> asyncio.Lock:
    # dict.setdefault is atomic under the GIL — first caller wins, second
    # observes the same Lock instance. Naive get-then-set raced when two
    # concurrent requests for a new phone both observed None.
    return _session_locks.setdefault(key, asyncio.Lock())


class AgentRequest(BaseModel):
    # Onboarding prompts can ship 20k+ chars of scraped page text, so we
    # set a generous ceiling. OpenClaw's own context window is the real limit.
    message: str = Field(..., min_length=1, max_length=80000)
    agent: str = DEFAULT_AGENT
    to: str | None = None
    session_id: str | None = None
    timeout: int = DEFAULT_TIMEOUT


class AgentResponse(BaseModel):
    reply: str
    session_id: str | None = None
    model: str | None = None
    ms: int = 0
    raw: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="OpenClaw VM Proxy", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _build_args(req: AgentRequest) -> list[str]:
    args = [OPENCLAW_BIN, "agent", "--json", "--timeout", str(req.timeout)]
    if req.session_id:
        args += ["--session-id", req.session_id]
    elif req.to:
        args += ["--to", req.to]
    else:
        args += ["--agent", req.agent]
    args += ["--message", req.message]
    return args


def _extract_reply(stdout: str) -> tuple[str, dict | None]:
    """OpenClaw mixes log lines with the JSON body. Find the {…} payload."""
    start = stdout.find("{")
    if start == -1:
        return stdout.strip()[:2000], None
    blob = stdout[start:]
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        # find last balanced {...} block
        depth = 0
        last_end = -1
        for i, ch in enumerate(blob):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    last_end = i + 1
        if last_end == -1:
            return stdout.strip()[:2000], None
        try:
            data = json.loads(blob[:last_end])
        except json.JSONDecodeError:
            return stdout.strip()[:2000], None

    # Newer OpenClaw CLI nests the body under `result`:
    #   {runId, status, summary, result: {payloads:[...], meta:{...}}}
    # Older shape:
    #   {payloads:[...], meta:{...}}
    # Try both — prefer the legacy shape if both are present.
    result_block = data.get("result")
    if isinstance(result_block, dict):
        # Merge nested result into top-level for downstream meta lookup
        nested_payloads = result_block.get("payloads")
        if nested_payloads and "payloads" not in data:
            data = {**data, **result_block}

    payloads = data.get("payloads") or []
    if payloads and isinstance(payloads, list) and payloads[0].get("text"):
        return payloads[0]["text"], data
    meta = data.get("meta") or {}
    if meta.get("finalAssistantVisibleText"):
        return meta["finalAssistantVisibleText"], data
    return json.dumps(data)[:2000], data


@app.post("/agent", response_model=AgentResponse)
async def run_agent(req: AgentRequest):
    args = _build_args(req)
    env = os.environ.copy()
    # Ensure npm-global bin (where `openclaw` lives) is on PATH for non-login subprocs
    home = env.get("HOME", "/home/manoj")
    extra = f"{home}/.npm-global/bin"
    if extra not in env.get("PATH", ""):
        env["PATH"] = f"{extra}:{env.get('PATH', '')}"

    # Serialize per session — concurrent calls to the same --to share the
    # OpenClaw session JSONL and clobber each other's write lock.
    lock = _get_lock(_session_key(req))
    async with lock:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=req.timeout + 30
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(504, "openclaw subprocess timed out")

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

    # CLI writes JSON to stderr when falling back to embedded mode.
    # Search both streams for the response payload.
    reply, data = _extract_reply(stdout)
    if not reply.strip():
        reply, data = _extract_reply(stderr)

    if not reply.strip():
        raise HTTPException(
            502,
            f"openclaw produced no extractable reply. "
            f"rc={proc.returncode} stderr={stderr[:400]} stdout={stdout[:400]}",
        )

    meta = (data or {}).get("meta") or {}
    agent_meta = meta.get("agentMeta") or {}
    return AgentResponse(
        reply=reply,
        session_id=agent_meta.get("sessionId"),
        model=agent_meta.get("model"),
        ms=int(meta.get("durationMs") or 0),
        raw=None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9000)
