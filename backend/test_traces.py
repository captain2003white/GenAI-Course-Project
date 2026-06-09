"""
Test Trace Generator — populates the eval-dashboard with multiple conversation traces.

Usage:
  # Terminal 1 — start the server:
  cd backend
  uvicorn main:app --reload --port 8000

  # Terminal 2 — generate traces (server must be running):
  cd backend
  python test_traces.py

What it does:
  - Opens 4 conversation sessions
  - Sends 3-6 messages per session
  - Covers search, chat, compare, buy scenarios
  - Each session creates separate traces visible in the dashboard
"""

import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

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

def fail(msg):
    print(f"  {RED}[XX]{RESET} {msg}")


def send_message(session_id: str, message: str, label: str = "") -> dict:
    """Send a single message (sync) and return the response."""
    resp = requests.post(f"{BASE_URL}/chat", json={
        "session_id": session_id,
        "message": message,
    }, timeout=120)
    data = resp.json()
    n_products = len(data.get("products", []))
    reply_preview = data.get("reply", "")[:60]
    tag = f" [{label}]" if label else ""
    info(f"products={n_products}, reply=\"{reply_preview}...\"{tag}")
    return data


def run_session(session_id: str, messages: list, label: str):
    """Run a multi-turn conversation in one session."""
    print(f"\n{BOLD}── Session: {label} ──{RESET}")
    for i, msg in enumerate(messages):
        print(f"\n  {YELLOW}[{i+1}]{RESET} \"{msg}\"")
        try:
            data = send_message(session_id, msg, label)
            if data.get("reply"):
                ok(f"reply received ({len(data['reply'])} chars)")
        except Exception as e:
            fail(f"{e}")


def main():
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Commerce Agents — Test Trace Generator{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"\nServer: {BASE_URL}")

    # Health check
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        print(f"\n{RED}Server not reachable at {BASE_URL}{RESET}")
        print(f"  {e}")
        sys.exit(1)

    print(f"  {GREEN}Server is running [OK]{RESET}\n")

    # Session 1: Clothing
    run_session("test-session-1", [
        "find me a jacket",
        "great! now i also need a backpack for travel",
        "show me some shirts too",
    ], "Clothes & Fashion")

    # Session 2: Electronics
    run_session("test-session-2", [
        "find me a laptop under 500",
        "show me some smartphones",
        "do you have any headphones?",
    ], "Electronics")

    # Session 3: Mixed
    run_session("test-session-3", [
        "i need a gift for a friend",
        "find me a dress or something nice",
        "i want to buy the first one",
        "also search for electronics",
    ], "Mixed & Vague")

    # Session 4: Chat-heavy
    run_session("test-session-4", [
        "hello, what can you help me with?",
        "find me a shirt",
        "compare the first two shirts",
        "tell me a joke",
        "how much is the first one?",
        "ok buy it for me",
    ], "Chat & Actions")

    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}  Traces generated across 4 sessions.{RESET}")
    print(f"{GREEN}  → http://localhost:8000/eval-dashboard{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")


if __name__ == "__main__":
    main()
