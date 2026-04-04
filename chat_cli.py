"""
Interactive terminal chat client for the Mistria API.

Usage:
    1. Start the API server:  python main.py
    2. In another terminal:   python chat_cli.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
DEFAULT_USER_ID = "user_101"


def _post_chat(user_id: str, message: str) -> dict:
    payload = json.dumps({
        "user_id": user_id,
        "message": message,
        "resume_pulse": True,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _check_health() -> bool:
    try:
        req = urllib.request.Request(f"{BASE_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except (urllib.error.URLError, OSError):
        return False


def main() -> None:
    print("\n" + "=" * 50)
    print("  Mistria Chat  —  Interactive Terminal Client")
    print("=" * 50)

    if not _check_health():
        print(
            "\n[ERROR] Cannot reach the API at " + BASE_URL,
            "\n        Start the server first:  python main.py",
        )
        sys.exit(1)

    print(f"\n  Server is live at {BASE_URL}")

    user_id = input(f"\n  Enter user_id [{DEFAULT_USER_ID}]: ").strip()
    if not user_id:
        user_id = DEFAULT_USER_ID

    print(f"\n  Chatting as '{user_id}'. Type 'quit' or 'exit' to leave.\n")
    print("-" * 50)

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not message:
            continue
        if message.lower() in {"quit", "exit"}:
            print("\nGoodbye!")
            break

        print("\n  [Thinking...]")

        try:
            result = _post_chat(user_id, message)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"\n  [API Error {exc.code}] {body}")
            continue
        except (urllib.error.URLError, OSError) as exc:
            print(f"\n  [Connection Error] {exc}")
            continue

        reply = result.get("reply", "")
        pulse = result.get("pulse", "?")
        latency = result.get("latency_seconds", 0)

        print(f"\nMistria: {reply}")
        print(f"\n  [pulse: {pulse}  |  latency: {latency:.1f}s]")
        print("-" * 50)


if __name__ == "__main__":
    main()
