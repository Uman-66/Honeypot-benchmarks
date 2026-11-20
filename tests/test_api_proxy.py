"""Tests for harness/api_proxy.py: timing fields, usage capture, and redaction."""

import hashlib
import http.client
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

import api_proxy  # noqa: E402

# Fixture built at runtime so no scanner pattern fires on this source line.
SECRET = "sk_live" + "_51H8xYzSecretKey987654321"
TOKEN = "Bearer " + SECRET
BODY = json.dumps({
    "model": "accounts/fireworks/models/test-model",
    "messages": [{"role": "user", "content": f"config: {SECRET}"}],
    "stream": False,
}).encode()
USAGE_RESPONSE = json.dumps({
    "model": "accounts/fireworks/models/test-model",
    "choices": [],
    "usage": {"prompt_tokens": 10, "completion_tokens": 32, "total_tokens": 42},
}).encode()


class _UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    status_code = 200
    payload = USAGE_RESPONSE

    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)


def _serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


@pytest.fixture()
def proxy(tmp_path):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    upstream.daemon_threads = True
    _serve(upstream)

    log_path = tmp_path / "proxy.jsonl"
    cfg = api_proxy.ProxyConfig(
        upstream=f"http://127.0.0.1:{upstream.server_address[1]}/inference/v1",
        log_path=log_path,
        timeout=10.0,
    )
    server = api_proxy.ProxyServer(("127.0.0.1", 0), cfg)
    _serve(server)

    yield server, log_path

    server.shutdown()
    server.server_close()
    upstream.shutdown()
    upstream.server_close()


def _post(port, path="/inference/v1/chat/completions", body=BODY):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", path, body=body, headers={
        "Content-Type": "application/json",
        "Authorization": TOKEN,
    })
    response = conn.getresponse()
    payload = response.read()
    conn.close()
    return response.status, payload


def _read_log(path):
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [json.loads(line) for line in lines]


def test_proxy_records_timing_status_size_and_usage(proxy):
    server, log_path = proxy
    status, _ = _post(server.server_address[1])
    assert status == 200

    entries = _read_log(log_path)
    assert len(entries) == 1
    entry = entries[0]

    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0
    assert entry["response_bytes"] == len(USAGE_RESPONSE)
    assert entry["request_bytes"] == len(BODY)
    assert entry["request_sha256"] == hashlib.sha256(BODY).hexdigest()
    assert entry["usage"]["total_tokens"] == 42
    assert entry["prompt_tokens"] == 10
    assert entry["completion_tokens"] == 32
    assert entry["model_requested"] == "accounts/fireworks/models/test-model"
    assert entry["model_reported"] == "accounts/fireworks/models/test-model"
    assert entry["stream"] is False
    assert entry["error"] is None


def test_log_never_contains_the_authorization_header_or_body(proxy):
    server, log_path = proxy
    _post(server.server_address[1])

    raw = log_path.read_text(encoding="utf-8")
    assert SECRET not in raw
    assert "sk_live_" not in raw
    assert "Authorization" not in raw
    assert "Bearer" not in raw
    # The body is represented only by its hash.
    assert hashlib.sha256(BODY).hexdigest() in raw


def test_upstream_failure_is_logged_as_502(tmp_path):
    log_path = tmp_path / "proxy.jsonl"
    cfg = api_proxy.ProxyConfig(
        upstream="http://127.0.0.1:1/inference/v1",  # nothing listens here
        log_path=log_path,
        timeout=2.0,
    )
    server = api_proxy.ProxyServer(("127.0.0.1", 0), cfg)
    _serve(server)
    try:
        status, _ = _post(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()

    assert status == 502
    entry = _read_log(log_path)[0]
    assert entry["status"] == 502
    assert entry["error"]
    assert SECRET not in log_path.read_text(encoding="utf-8")


def test_upstream_path_keeps_the_base_prefix_idempotent():
    from urllib.parse import urlsplit
    base = urlsplit("https://api.fireworks.ai/inference/v1")
    handler = api_proxy.ProxyHandler
    assert handler._upstream_path("/inference/v1/chat/completions", base) == \
        "/inference/v1/chat/completions"
    assert handler._upstream_path("/chat/completions", base) == \
        "/inference/v1/chat/completions"


def test_usage_is_parsed_from_a_streamed_response():
    sse = (
        b'data: {"model":"m","choices":[]}\n\n'
        b'data: {"usage":{"prompt_tokens":3,"completion_tokens":4,"total_tokens":7}}\n\n'
        b"data: [DONE]\n\n"
    )
    usage, model = api_proxy.usage_from_response(sse, "text/event-stream")
    assert usage["total_tokens"] == 7
    assert model == "m"


def test_body_metadata_extraction_does_not_keep_the_body():
    meta = api_proxy._request_meta(BODY)
    assert meta["model"] == "accounts/fireworks/models/test-model"
    assert meta["stream"] is False
    assert "messages" not in meta


def test_remote_bind_requires_explicit_flag(capsys):
    assert api_proxy.main(["--bind", "0.0.0.0"]) == 2
    assert "allow-remote-bind" in capsys.readouterr().err
