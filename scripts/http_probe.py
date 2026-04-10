"""Minimal HTTP probe used by compose health checks and CI."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def main() -> int:
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
    except urllib.error.URLError as exc:
        print(f"HTTP probe failed for {args.url}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
