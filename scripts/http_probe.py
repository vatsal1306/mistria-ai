"""Minimal HTTP probe used by compose health checks and CI."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the HTTP probe utility."""
    parser = argparse.ArgumentParser(description="Probe an HTTP endpoint.")
    parser.add_argument("--url", required=True, help="Endpoint URL to request.")
    parser.add_argument(
        "--expected-status",
        type=int,
        default=200,
        help="Expected HTTP status code.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--expect-json",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Assert a top-level or dotted JSON field equals the expected value.",
    )
    return parser.parse_args()


def _parse_expected_value(value: str) -> object:
    """Parse a JSON-style scalar expected value from the CLI."""
    normalized = value.strip()
    if normalized.lower() == "true":
        return True
    if normalized.lower() == "false":
        return False
    if normalized.lower() == "null":
        return None

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return value


def _lookup_json_value(payload: object, dotted_key: str) -> object:
    """Read a dotted key from a JSON object."""
    current = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_key)
        current = current[part]
    return current


def _assert_json_expectations(body: bytes, expectations: list[str]) -> bool:
    """Validate all JSON field expectations against the response body."""
    if not expectations:
        return True

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        print(f"Response body is not valid JSON: {exc}", file=sys.stderr)
        return False

    for expectation in expectations:
        if "=" not in expectation:
            print(f"Invalid JSON expectation {expectation!r}; expected KEY=VALUE", file=sys.stderr)
            return False

        key, expected_raw = expectation.split("=", 1)
        key = key.strip()
        expected = _parse_expected_value(expected_raw)
        try:
            actual = _lookup_json_value(payload, key)
        except KeyError:
            print(f"Missing JSON field for expectation: {key}", file=sys.stderr)
            return False

        if actual != expected:
            print(
                f"Unexpected JSON value for {key}: {actual!r} != {expected!r}",
                file=sys.stderr,
            )
            return False

    return True


def main() -> int:
    """Execute one HTTP probe and return a shell-friendly exit code."""
    args = parse_args()
    parsed = urlparse(args.url)

    if parsed.scheme not in {"http", "https"}:
        print(f"Unsupported URL scheme for probe: {args.url}", file=sys.stderr)
        return 1

    try:
        with urllib.request.urlopen(args.url, timeout=args.timeout_seconds) as response:  # nosec B310
            if response.status != args.expected_status:
                print(
                    f"Unexpected status for {args.url}: {response.status} != {args.expected_status}",
                    file=sys.stderr,
                )
                return 1
            body = response.read()
    except urllib.error.URLError as exc:
        print(f"HTTP probe failed for {args.url}: {exc}", file=sys.stderr)
        return 1

    if not _assert_json_expectations(body, args.expect_json):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
