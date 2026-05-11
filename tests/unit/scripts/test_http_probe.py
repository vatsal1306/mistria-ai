"""Unit tests for the HTTP probe utility."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts import http_probe


class _Response:
    def __init__(self, status: int = 200, body: bytes = b"{}"):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


def test_parse_expected_value_parses_json_scalars():
    assert http_probe._parse_expected_value("true") is True
    assert http_probe._parse_expected_value("false") is False
    assert http_probe._parse_expected_value("null") is None
    assert http_probe._parse_expected_value("42") == 42
    assert http_probe._parse_expected_value("plain") == "plain"


def test_lookup_json_value_reads_dotted_path():
    assert http_probe._lookup_json_value({"a": {"b": 3}}, "a.b") == 3
    with pytest.raises(KeyError):
        http_probe._lookup_json_value({"a": {}}, "a.b")


def test_assert_json_expectations_success_and_failures(capsys):
    assert http_probe._assert_json_expectations(b'{"status":"ok","ready":true}', ["status=ok", "ready=true"])
    assert not http_probe._assert_json_expectations(b"not json", ["status=ok"])
    assert not http_probe._assert_json_expectations(b"{}", ["bad-format"])
    assert not http_probe._assert_json_expectations(b"{}", ["status=ok"])
    assert not http_probe._assert_json_expectations(b'{"status":"bad"}', ["status=ok"])
    assert "Unexpected JSON value" in capsys.readouterr().err


def test_main_rejects_unsupported_scheme(monkeypatch, capsys):
    monkeypatch.setattr(http_probe, "parse_args", lambda: SimpleNamespace(url="ftp://example.com", expected_status=200, timeout_seconds=1, expect_json=[]))

    assert http_probe.main() == 1
    assert "Unsupported URL scheme" in capsys.readouterr().err


def test_main_success_with_json_expectations(monkeypatch):
    response = _Response(body=json.dumps({"status": "ok"}).encode())
    monkeypatch.setattr(http_probe, "parse_args", lambda: SimpleNamespace(url="http://example.com", expected_status=200, timeout_seconds=1, expect_json=["status=ok"]))
    monkeypatch.setattr(http_probe.urllib.request, "urlopen", mock.Mock(return_value=response))

    assert http_probe.main() == 0


def test_main_reports_status_and_url_errors(monkeypatch, capsys):
    monkeypatch.setattr(http_probe, "parse_args", lambda: SimpleNamespace(url="http://example.com", expected_status=201, timeout_seconds=1, expect_json=[]))
    monkeypatch.setattr(http_probe.urllib.request, "urlopen", mock.Mock(return_value=_Response(status=200)))
    assert http_probe.main() == 1

    monkeypatch.setattr(http_probe, "parse_args", lambda: SimpleNamespace(url="http://example.com", expected_status=200, timeout_seconds=1, expect_json=[]))
    monkeypatch.setattr(http_probe.urllib.request, "urlopen", mock.Mock(side_effect=http_probe.urllib.error.URLError("down")))
    assert http_probe.main() == 1
    assert "HTTP probe failed" in capsys.readouterr().err


def test_parse_args_reads_cli_arguments(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["http_probe.py", "--url", "http://example.com", "--expected-status", "204", "--expect-json", "status=ok"],
    )

    args = http_probe.parse_args()

    assert args.url == "http://example.com"
    assert args.expected_status == 204
    assert args.expect_json == ["status=ok"]
