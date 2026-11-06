#!/usr/bin/env python3
"""Periodic, minimal OpenAI-compatible chat-completion probe."""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "results" / "api_probe.csv"
STOP_PATH = REPO_ROOT / "results" / "STOP_PROBE"
CSV_FIELDS = ("iso_timestamp", "http_status", "latency_s", "error_type")
Opener = Callable[..., Any]


def _read_dotenv_key(path: Path, key: str) -> str | None:
    """Read one requested KEY=VALUE entry without exposing dotenv contents."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip("\"'")
    except OSError:
        return None
    return None


def _setting(name: str) -> str | None:
    return os.getenv(name) or _read_dotenv_key(REPO_ROOT / ".env", name)


def _completion_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/chat/completions"


def _append_row(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def probe_once(
    *,
    api_key: str,
    base_url: str,
    model: str,
    output_path: Path = OUTPUT_PATH,
    opener: Opener = urllib.request.urlopen,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, str]:
    """Send one probe and append its non-secret outcome to the CSV."""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 16,
        "temperature": 0.2,
    }).encode("utf-8")
    request = urllib.request.Request(
        _completion_url(base_url),
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = clock()
    status = ""
    error_type = ""
    try:
        with opener(request, timeout=60) as response:
            status = str(response.status)
            response.read()
    except urllib.error.HTTPError as exc:
        status = str(exc.code)
        error_type = type(exc).__name__
    except Exception as exc:
        error_type = type(exc).__name__
    row = {
        "iso_timestamp": datetime.now(timezone.utc).isoformat(),
        "http_status": status,
        "latency_s": f"{clock() - started:.3f}",
        "error_type": error_type,
    }
    _append_row(output_path, row)
    return row


def main() -> int:
    api_key = _setting("OPENAI_API_KEY")
    base_url = _setting("OPENAI_BASE_URL")
    model = _setting("MODEL")
    missing = [
        name for name, value in (
            ("OPENAI_API_KEY", api_key),
            ("OPENAI_BASE_URL", base_url),
            ("MODEL", model),
        ) if not value
    ]
    if missing:
        print(f"ERROR: missing required setting(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    try:
        while not STOP_PATH.exists():
            probe_once(api_key=api_key, base_url=base_url, model=model)
            for _ in range(30):
                if STOP_PATH.exists():
                    return 0
                time.sleep(1)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
