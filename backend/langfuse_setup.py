"""
Langfuse observability configuration

Uses direct REST API calls to bypass SDK v2.55.0 bugs where:
- trace.score() creates orphaned scores
- langfuse.trace() doesn't reliably flush traces to the server

All traces and scores are created via Langfuse Public REST API.
"""

import os
import httpx
import uuid
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")


def _get_auth():
    """Return HTTP Basic Auth tuple for Langfuse API."""
    return (PUBLIC_KEY, SECRET_KEY)


async def create_trace_api(
    session_id: str,
    user_message: str,
    output: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, int]] = None,
) -> Optional[str]:
    """
    Create a trace in Langfuse via REST API.

    Includes output and metadata in the initial creation (Langfuse Public API
    does not support PATCH updates for traces in all versions).

    Returns the trace ID on success, or None on failure.
    """
    trace_id = str(uuid.uuid4())
    url = f"{HOST}/api/public/traces"

    payload: Dict[str, Any] = {
        "id": trace_id,
        "name": "commerce-agent-session",
        "sessionId": session_id,
        "input": user_message,
        "metadata": metadata or {"app": "Commerce Agents"},
    }
    if output:
        payload["output"] = output
    if usage and usage.get("total_tokens"):
        payload["usage"] = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
            "unit": "TOKENS",
        }
        print(f"[Langfuse-API] Usage: {payload['usage']}", flush=True)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                auth=_get_auth(),
                timeout=10,
            )
        if resp.status_code in (200, 201):
            print(f"[Langfuse-API] Trace created: {trace_id[:12]}... (session={session_id[:20]}...)", flush=True)
            return trace_id
        else:
            print(f"[Langfuse-API] Failed to create trace: HTTP {resp.status_code} {resp.text[:200]}", flush=True)
            return None
    except Exception as e:
        print(f"[Langfuse-API] Error creating trace: {e}", flush=True)
        return None


async def post_score_via_api(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
) -> bool:
    """Post an evaluation score to Langfuse via REST API."""
    url = f"{HOST}/api/public/scores"

    payload = {
        "traceId": trace_id,
        "name": name,
        "value": value,
    }
    if comment:
        payload["comment"] = comment

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                auth=_get_auth(),
                timeout=10,
            )
        if resp.status_code in (200, 201):
            return True
        else:
            print(f"[Langfuse-API] Failed to post score: HTTP {resp.status_code} {resp.text[:200]}", flush=True)
            return False
    except Exception as e:
        print(f"[Langfuse-API] Error posting score: {e}", flush=True)
        return False
