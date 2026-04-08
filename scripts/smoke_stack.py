"""End-to-end smoke checks for the docker-compose stack."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse
from uuid import uuid4

from websocket import create_connection


def parse_args() -> argparse.Namespace:
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
        except urllib.error.URLError as exc:
            last_error = exc
        time.sleep(2.0)

    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def add_api_key(websocket_url: str, api_key: str) -> str:
    if not api_key:
        return websocket_url

    separator = "&" if "?" in websocket_url else "?"
    return f"{websocket_url}{separator}{urlencode({'api_key': api_key})}"


def assert_ready_frame(frame: dict[str, object]) -> None:
    if frame.get("type") != "ready":
        raise RuntimeError(f"Expected ready frame, received: {frame}")


def run_websocket_round_trip(websocket_url: str) -> None:
    connection = create_connection(websocket_url, timeout=15.0)
    try:
        ready_frame = json.loads(connection.recv())
        assert_ready_frame(ready_frame)

        user_message = f"smoke-test-{uuid4().hex[:8]}"
        request_payload = {
            "action": "chat",
            "request_id": uuid4().hex,
            "messages": [{"role": "user", "content": user_message}],
        }
        connection.send(json.dumps(request_payload))

        seen_start = False
        seen_done = False
        collected_chunks: list[str] = []

        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            frame = json.loads(connection.recv())
            frame_type = frame.get("type")
            if frame_type == "start":
                seen_start = True
                continue
            if frame_type == "delta":
                delta = str(frame.get("delta", ""))
                if delta:
                    collected_chunks.append(delta)
                continue
            if frame_type == "done":
                seen_done = True
                done_text = str(frame.get("text", ""))
                if not done_text.strip():
                    raise RuntimeError(f"Received empty done frame: {frame}")
                break
            if frame_type == "error":
                raise RuntimeError(f"Backend returned an error frame: {frame}")
            raise RuntimeError(f"Unexpected websocket frame: {frame}")

        if not seen_start:
            raise RuntimeError("Did not receive websocket start frame.")
        if not seen_done:
            raise RuntimeError("Did not receive websocket done frame.")
        if not "".join(collected_chunks).strip():
            raise RuntimeError("Did not receive any websocket delta frames.")
    finally:
        connection.close()


def main() -> int:
    args = parse_args()

    wait_for_http(args.backend_health_url, args.timeout_seconds)
    wait_for_http(args.frontend_url, args.timeout_seconds)
    run_websocket_round_trip(add_api_key(args.websocket_url, args.api_key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
