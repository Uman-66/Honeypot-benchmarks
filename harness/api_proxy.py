#!/usr/bin/env python3
"""
harness/api_proxy.py
Local reverse proxy that times every LLM request the honeypots make.

Why it exists: the benchmark measures end-to-end command latency, which folds
queueing, network and model generation into one number.  Pointing each target
at this proxy splits that number into per-request API duration plus everything
else, and records the token usage the provider reports.

What is logged (one JSON object per line, JSONL):

    ts, method, path, upstream_path, status, duration_ms,
    request_bytes, request_sha256, response_bytes,
    model_requested, model_reported, stream, usage,
    prompt_tokens, completion_tokens, total_tokens, error

What is NEVER logged: the Authorization header, any API key, and request or
response bodies.  Headers are not copied into the log record at all; the only
body-derived value is its SHA-256, so a logged request can be matched against a
transcript without republishing its content.

Usage:
    python harness/api_proxy.py                       # bind 127.0.0.1:11435
    python harness/api_proxy.py --bind 0.0.0.0 --allow-remote-bind
    python harness/api_proxy.py --upstream https://api.fireworks.ai/inference/v1

Pointing a target at it (see docs/STAGE2_NOTES.md for the full table):

    OPENAI_BASE_URL=http://127.0.0.1:11435/inference/v1     # host-run clients
    OPENAI_BASE_URL=http://host.docker.internal:11435/inference/v1  # containers

Containers must use ``host.docker.internal`` because ``127.0.0.1`` inside a
container is the container itself.  That address only works when the proxy
listens on a non-loopback interface, which is why ``--allow-remote-bind`` is a
separate, explicit flag.

Limitation: responses are buffered before they are relayed, so a client that
sets ``stream: true`` still receives the full body but not incrementally.
``duration_ms`` therefore covers the whole generation, which is what the
benchmark wants.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import threading
import time
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_UPSTREAM = "https://api.fireworks.ai/inference/v1"
DEFAULT_LOG = "results/exp/api_proxy_log.jsonl"
DEFAULT_PORT = 11435

_LOOPBACK = {"127.0.0.1", "localhost", "::1", "::"}

# RFC 7230 hop-by-hop headers: never forwarded, never logged.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _request_meta(body: bytes) -> dict[str, Any]:
    """Extract model / stream from the request body without keeping the body."""
    meta: dict[str, Any] = {"model": None, "stream": None}
    if not body:
        return meta
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return meta
    if isinstance(payload, dict):
        model = payload.get("model")
        meta["model"] = model if isinstance(model, str) else None
        meta["stream"] = bool(payload.get("stream"))
    return meta


def usage_from_response(raw: bytes, content_type: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Return ``(usage, reported_model)`` from a JSON or SSE response.

    Only the ``usage`` object and the ``model`` string are copied out; the rest
    of the body is discarded.
    """
    if not raw:
        return None, None
    text = raw.decode("utf-8", "replace")

    if "event-stream" in (content_type or "").lower():
        usage: dict[str, Any] | None = None
        model: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if isinstance(obj.get("usage"), dict):
                usage = obj["usage"]
            if isinstance(obj.get("model"), str):
                model = obj["model"]
        return usage, model

    try:
        obj = json.loads(text)
    except Exception:
        return None, None
    if not isinstance(obj, dict):
        return None, None
    usage = obj.get("usage") if isinstance(obj.get("usage"), dict) else None
    model = obj.get("model") if isinstance(obj.get("model"), str) else None
    return usage, model


class ProxyConfig:
    """Immutable settings plus a serialized JSONL writer."""

    def __init__(self, upstream: str, log_path: Path, timeout: float) -> None:
        self.upstream = upstream
        self.log_path = log_path
        self.timeout = timeout
        self._lock = threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "stage2-api-proxy/1.0"

    #: The default handler logs the request line; keep the proxy silent so the
    #: log file is the single source of truth.
    def log_message(self, *_args: Any) -> None:
        return

    # Every method takes the same path.
    def do_GET(self) -> None:      self._forward()
    def do_HEAD(self) -> None:     self._forward()
    def do_POST(self) -> None:     self._forward()
    def do_PUT(self) -> None:      self._forward()
    def do_PATCH(self) -> None:    self._forward()
    def do_DELETE(self) -> None:   self._forward()
    def do_OPTIONS(self) -> None:  self._forward()

    @staticmethod
    def _upstream_path(request_path: str, upstream_url) -> str:
        """
        Keep a base path such as ``/inference/v1`` intact whether or not the
        client includes it.  ``OPENAI_BASE_URL`` is what decides this, so both
        `http://host:11435/inference/v1` and `http://host:11435` work.
        """
        base = (upstream_url.path or "").rstrip("/")
        if not base:
            return request_path
        if request_path.startswith(base):
            return request_path
        return base + "/" + request_path.lstrip("/")

    def _forward(self) -> None:
        cfg: ProxyConfig = self.server.cfg          # type: ignore[attr-defined]
        started = time.monotonic()
        ts = _now_iso()

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""
        meta = _request_meta(body)
        request_sha = hashlib.sha256(body).hexdigest() if body else None

        upstream_url = urlsplit(cfg.upstream)
        upstream_path = self._upstream_path(self.path, upstream_url)

        # Headers are forwarded (Authorization included) but never inspected,
        # stored or logged.
        forward_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _HOP_BY_HOP
        }
        if body:
            forward_headers["Content-Length"] = str(len(body))

        status = 0
        raw = b""
        response_headers: dict[str, str] = {}
        content_type = ""
        error: str | None = None

        try:
            conn_cls = HTTPSConnection if upstream_url.scheme == "https" else HTTPConnection
            conn = conn_cls(upstream_url.hostname, upstream_url.port, timeout=cfg.timeout)
            conn.request(self.command, upstream_path, body=body or None,
                         headers=forward_headers)
            response = conn.getresponse()
            status = response.status
            raw = response.read()
            for key, value in response.getheaders():
                if key.lower() in _HOP_BY_HOP:
                    continue
                response_headers[key] = value
                if key.lower() == "content-type":
                    content_type = value
            conn.close()
        except Exception as exc:
            status = 502
            error = f"{type(exc).__name__}: {exc}"
            raw = json.dumps({"error": "api_proxy upstream failure"}).encode("utf-8")
            response_headers = {"Content-Type": "application/json"}
            content_type = "application/json"

        usage, reported_model = usage_from_response(raw, content_type)

        entry: dict[str, Any] = {
            "ts": ts,
            "method": self.command,
            "path": self.path,
            "upstream_path": upstream_path,
            "status": status,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "request_bytes": len(body),
            "request_sha256": request_sha,
            "response_bytes": len(raw),
            "model_requested": meta["model"],
            "model_reported": reported_model,
            "stream": meta["stream"],
            "usage": usage,
            "prompt_tokens": (usage or {}).get("prompt_tokens"),
            "completion_tokens": (usage or {}).get("completion_tokens"),
            "total_tokens": (usage or {}).get("total_tokens"),
            "error": error,
        }
        cfg.write(entry)

        try:
            self.send_response_only(status)
            for key, value in response_headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            # Client gave up: already logged, nothing else to do.
            pass


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], cfg: ProxyConfig) -> None:
        super().__init__(address, ProxyHandler)
        self.cfg = cfg


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Timing reverse proxy for OpenAI-compatible LLM endpoints",
    )
    p.add_argument("--bind", default="127.0.0.1",
                   help="Listen address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"Listen port (default: {DEFAULT_PORT})")
    p.add_argument("--upstream",
                   default=os.environ.get("OPENAI_BASE_URL", DEFAULT_UPSTREAM),
                   help="Upstream base URL (default: $OPENAI_BASE_URL, else Fireworks)")
    p.add_argument("--log", default=DEFAULT_LOG,
                   help=f"JSONL log path (default: {DEFAULT_LOG})")
    p.add_argument("--timeout", type=float, default=300.0,
                   help="Upstream timeout in seconds (default: 300)")
    p.add_argument("--allow-remote-bind", action="store_true",
                   help="Required to bind a non-loopback address (container access)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.bind not in _LOOPBACK and not args.allow_remote_bind:
        print(
            f"ERROR: refusing to bind {args.bind} without --allow-remote-bind.\n"
            "       Containers reach the host as host.docker.internal, which needs a\n"
            "       non-loopback bind. Pass --allow-remote-bind on a trusted machine only.",
            file=sys.stderr,
        )
        return 2

    upstream = urlsplit(args.upstream)
    if not upstream.scheme or not upstream.hostname:
        print(f"ERROR: --upstream must be an absolute URL, got {args.upstream!r}", file=sys.stderr)
        return 2

    cfg = ProxyConfig(args.upstream, Path(args.log), args.timeout)
    server = ProxyServer((args.bind, args.port), cfg)

    print(f"api_proxy: {args.bind}:{args.port} -> {args.upstream}")
    print(f"api_proxy: log {cfg.log_path}")
    print("api_proxy: Authorization headers and bodies are never logged "
          "(request body is recorded only as SHA-256).")
    print("api_proxy: point a host client at  http://127.0.0.1:"
          f"{args.port}{upstream.path}")
    print("api_proxy: point a container at   http://host.docker.internal:"
          f"{args.port}{upstream.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\napi_proxy: stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
