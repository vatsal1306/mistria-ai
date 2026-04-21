"""End-to-end smoke checks for the docker-compose stack."""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse
from uuid import uuid4

from websocket import create_connection


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the compose smoke test."""
    parser = argparse.ArgumentParser(description="Smoke test the running stack.")
    parser.add_argument("--frontend-url", required=True, help="Streamlit base URL.")
    parser.add_argument("--backend-health-url", required=True, help="Backend health URL.")
    parser.add_argument("--websocket-url", required=True, help="Backend websocket URL.")
    parser.add_argument(
        "--api-key",
        default="",
        help="Optional API key to append to the websocket URL.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Total wait timeout for HTTP readiness checks.",
    )
    return parser.parse_args()


def wait_for_http(url: str, timeout_seconds: float) -> None:
    """Poll an HTTP endpoint until it returns `200` or times out."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"Unsupported readiness probe URL: {url}")

    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5.0) as response:  # nosec B310
                if response.status == 200:
                    return
                last_error = RuntimeError(f"Unexpected status code {response.status} for {url}")
        except (urllib.error.URLError, ConnectionResetError, http.client.HTTPException, OSError, socket.timeout) as exc:
            last_error = exc
        time.sleep(2.0)

    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def add_api_key(websocket_url: str, api_key: str) -> str:
    """Append the API key query parameter when websocket auth is enabled."""
    if not api_key:
        return websocket_url

    separator = "&" if "?" in websocket_url else "?"
    return f"{websocket_url}{separator}{urlencode({'api_key': api_key})}"


def assert_ready_frame(frame: dict[str, object]) -> None:
    """Validate that the websocket handshake starts with a ready event."""
    if frame.get("type") != "ready":
        raise RuntimeError(f"Expected ready frame, received: {frame}")


def _post_json(base_url: str, path: str, payload: dict) -> dict:
    """Send a POST request with a JSON body and return the parsed response."""
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=10.0) as response:  # nosec B310
        return json.loads(response.read())


def seed_smoke_user(backend_base_url: str) -> tuple[str, int]:
    """Register a smoke-test user, companion preferences, and AI companion.

    Returns the user email and the created AI companion ID.
    """
    email = f"smoke-{uuid4().hex[:8]}@ci.test"

    _post_json(backend_base_url, "/users", {"email": email, "name": "CI Smoke User"})

    _post_json(backend_base_url, "/user-companion", {
        "user_mail_id": email,
        "intent_type": "easy",
        "dominance_mode": "user_leads",
        "intensity_level": "show_me",
        "silence_response": "wait",
        "secret_desire": "running",
    })

    ai_companion = _post_json(backend_base_url, "/ai-companion", {
        "user_mail_id": email,
        "title": "CI Bot",
        "gender": "Female",
        "style": "Anime",
        "ethnicity": "East Asian",
        "eyeColor": "Brown",
        "hairStyle": "Short",
        "hairColor": "Black",
        "personality": "Playful",
        "voice": "Calm",
        "connection": "New Encounter",
    })

    return email, ai_companion["id"]


def run_websocket_round_trip(websocket_url: str, user_email: str, ai_companion_id: int) -> None:
    """Send one chat request over websocket and assert the streamed lifecycle is complete."""
    connection = create_connection(websocket_url, timeout=15.0)
    try:
        ready_frame = json.loads(connection.recv())
        assert_ready_frame(ready_frame)

        request_payload = {
            "action": "chat",
            "user_id": user_email,
            "ai_companion_id": ai_companion_id,
            "user_message": f"smoke-test-{uuid4().hex[:8]}",
        }
        connection.send(json.dumps(request_payload))

        seen_done = False
        collected_chunks: list[str] = []

        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            frame = json.loads(connection.recv())
            frame_type = frame.get("type")
            if frame_type == "delta":
                delta = str(frame.get("delta", ""))
                if delta:
                    collected_chunks.append(delta)
                continue
            if frame_type == "done":
                seen_done = True
                break
            if frame_type == "error":
                raise RuntimeError(f"Backend returned an error frame: {frame}")
            raise RuntimeError(f"Unexpected websocket frame: {frame}")

        if not seen_done:
            raise RuntimeError("Did not receive websocket done frame.")
        if not "".join(collected_chunks).strip():
            raise RuntimeError("Did not receive any websocket delta frames.")
    finally:
        connection.close()


def main() -> int:
    """Run the full smoke test sequence and return a shell-friendly exit code."""
    args = parse_args()

    wait_for_http(args.backend_health_url, args.timeout_seconds)
    wait_for_http(args.frontend_url, args.timeout_seconds)

    backend_base_url = args.backend_health_url.rsplit("/health", 1)[0]
    user_email, ai_companion_id = seed_smoke_user(backend_base_url)

    run_websocket_round_trip(
        add_api_key(args.websocket_url, args.api_key),
        user_email,
        ai_companion_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

