"""
Test Trace Generator — populates the eval-dashboard with multiple conversation traces.

Usage:
  # Terminal 1 — start the server:
  cd backend
  # bash: source venv/Scripts/activate
  # PowerShell: .\venv\Scripts\Activate.ps1
  uvicorn main:app --reload --port 8000

  # Terminal 2 — generate traces (server must be running):
  cd backend
  source venv/Scripts/activate   # bash
  # .\venv\Scripts\Activate.ps1  # PowerShell
  python test_traces.py

What it does:
  - Opens 4 conversation sessions
  - Sends 4-6 messages per session
  - Covers all action types: search, chat, compare, buy, show
  - Each session creates separate traces visible in the dashboard
  - Mixed scenarios: normal search, no-results, vague queries, chitchat
"""

import asyncio
import httpx
import sys
import time

BASE_URL = "http://localhost:8000"

# ── Color helpers ──
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg):
    print(f"  {GREEN}[OK]{RESET} {msg}")

def info(msg):
    print(f"  {BLUE}[..]{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}[!!]{RESET} {msg}")

def fail(msg):
    print(f"  {RED}[XX]{RESET} {msg}")


async def send_message(session_id: str, message: str, label: str = "") -> dict:
    """Send a single message and return the response."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{BASE_URL}/chat", json={
            "session_id": session_id,
            "message": message,
        })
        data = resp.json()
        n_products = len(data.get("products", []))
        reply_preview = data.get("reply", "")[:60]
        tag = f" [{label}]" if label else ""
        info(f"products={n_products}, reply=\"{reply_preview}...\"{tag}")
        return data


async def run_session(session_id: str, messages: list, label: str):
    """Run a multi-turn conversation in one session."""
    print(f"\n{BOLD}── Session: {label} ──{RESET}")
    print(f"  session_id = {session_id}")
    results = []
    for i, msg in enumerate(messages):
        print(f"\n  {YELLOW}[{i+1}]{RESET} \"{msg}\"")
        try:
            data = await send_message(session_id, msg, label)
            results.append(data)
            if data.get("reply"):
                ok(f"reply received ({len(data['reply'])} chars)")
        except Exception as e:
            fail(f"{e}")
    return results


async def main():
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Commerce Agents — Test Trace Generator{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"\nServer: {BASE_URL}")

    # Ping health check
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BASE_URL}/health")
            assert r.status_code == 200
    except Exception as e:
        print(f"\n{RED}Server not reachable at {BASE_URL}{RESET}")
        print(f"  {e}")
        print(f"\nMake sure uvicorn is running:\n  cd backend && source venv/Scripts/activate && uvicorn main:app --reload --port 8000")
        sys.exit(1)

    print(f"  {GREEN}Server is running [OK]{RESET}\n")

    # ═══════════════════════════════════════════════════════════
    # Session 1: Clothing search — happy path
    # ═══════════════════════════════════════════════════════════
    await run_session(
        session_id="test-session-1",
        label="Clothes & Fashion",
        messages=[
            "find me a jacket",
            "I need a jacket for winter, any recommendations?",
            "great! now i also need a backpack for travel",
            "show me some shirts too",
        ],
    )

    # ═══════════════════════════════════════════════════════════
    # Session 2: Electronics — search + no-results
    # ═══════════════════════════════════════════════════════════
    await run_session(
        session_id="test-session-2",
        label="Electronics",
        messages=[
            "find me a laptop under 500",
            "show me some smartphones",
            "do you have any headphones?",
            "thanks, that's all",
        ],
    )

    # ═══════════════════════════════════════════════════════════
    # Session 3: Mixed actions — vague + chat + buy intent
    # ═══════════════════════════════════════════════════════════
    await run_session(
        session_id="test-session-3",
        label="Mixed & Vague",
        messages=[
            "i need a gift for a friend",
            "find me a dress or something nice",
            "i want to buy the first one",
            "also search for electronics",
        ],
    )

    # ═══════════════════════════════════════════════════════════
    # Session 4: Chat-heavy + compare + buy
    # ═══════════════════════════════════════════════════════════
    await run_session(
        session_id="test-session-4",
        label="Chat & Actions",
        messages=[
            "hello, what can you help me with?",
            "find me a shirt",
            "compare the first two shirts",
            "tell me a joke",
            "how much is the first one?",
            "ok buy it for me",
        ],
    )

    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  18 traces generated across 4 sessions.{RESET}")
    print(f"{GREEN}  Refresh the eval-dashboard to see them all.{RESET}")
    print(f"{GREEN}  → http://localhost:8000/eval-dashboard{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
