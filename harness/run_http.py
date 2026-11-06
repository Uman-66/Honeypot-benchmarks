#!/usr/bin/env python3
"""
harness/run_http.py
Scripted HTTP benchmark attacker using the standard library only.

Usage:
    python harness/run_http.py [options]

Options:
    --targets   Path to targets.yaml   (default: harness/targets.yaml)
    --requests  Path to http_requests.yaml (default: harness/http_requests.yaml)
    --runs      Number of runs per target (default: 5)
    --out       Output directory        (default: results/raw_http)
    --timeout   Per-request timeout in seconds (default: 30)
    --dry-run   Validate YAML only, do not connect
    --target    Comma-separated target names to run (default: all http targets)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

try:
    csv.field_size_limit(2**31 - 1)
except OverflowError:
    csv.field_size_limit(2**30)

ENCODING = "utf-8"
MAX_BODY_BYTES = 20_000

# Safety: refuse any host that is not 127.0.0.1
_ALLOWED_HOSTS = {"127.0.0.1"}

# Documentation-example secret patterns to flag
_SECRET_PATTERNS = [
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "EXAMPLE",
]

_CSV_FIELDS = [
    "target", "run", "id", "method", "path",
    "status", "reason", "server_header", "content_length_header",
    "actual_body_length", "content_length_match",
    "chunked", "date_header", "date_drift_s",
    "latency_s", "timed_out", "error",
    "body_sha256", "body_snippet",
]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HTTP benchmark harness")
    p.add_argument("--targets",  default="harness/targets.yaml",
                   help="Target config path, or comma-separated target names")
    p.add_argument("--requests", default="harness/http_requests.yaml")
    p.add_argument("--runs",     type=int, default=5)
    p.add_argument("--out",      default="results/raw_http")
    p.add_argument("--timeout",  type=float, default=30.0)
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Back up and rerun already-complete target/run pairs")
    p.add_argument(
        "--target",
        default=None,
        help="Comma-separated target names (default: all HTTP targets)",
    )
    return p.parse_args(argv)


def _parse_http_date(date_str: str) -> float | None:
    """Parse an HTTP Date header (RFC 7231) and return a POSIX timestamp."""
    import email.utils
    try:
        return email.utils.parsedate_to_datetime(date_str).timestamp()
    except Exception:
        return None


def _do_request(
    host: str,
    port: int,
    req: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """
    Perform a single HTTP request and return a result dict.
    Only connects to 127.0.0.1 — raises ValueError otherwise.
    """
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"Refusing to connect to non-localhost host: {host!r}")

    method  = req.get("method", "GET").upper()
    path    = req.get("path", "/")
    body_s  = req.get("body")
    extra_headers = req.get("headers") or {}

    body_bytes = body_s.encode(ENCODING) if body_s else None

    record: dict[str, Any] = {
        "id":     req["id"],
        "method": method,
        "path":   path,
        "status": None,
        "reason": None,
        "response_headers": {},
        "server_header":    None,
        "content_length_header": None,
        "actual_body_length": None,
        "content_length_match": None,
        "chunked": False,
        "date_header": None,
        "date_drift_s": None,
        "latency_s": None,
        "timed_out": False,
        "error": None,
        "body": None,
        "body_sha256": None,
    }

    t0 = time.monotonic()
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        headers: dict[str, str] = {"Host": f"{host}:{port}"}
        headers.update(extra_headers)
        if body_bytes:
            headers.setdefault("Content-Length", str(len(body_bytes)))

        conn.request(method, path, body=body_bytes, headers=headers)
        resp = conn.getresponse()

        record["status"] = resp.status
        record["reason"] = resp.reason

        # Capture all response headers in order
        resp_headers: dict[str, str] = {}
        for name, value in resp.getheaders():
            resp_headers[name] = value
        record["response_headers"] = resp_headers

        record["server_header"] = resp.getheader("Server")
        cl_header = resp.getheader("Content-Length")
        record["content_length_header"] = cl_header

        # Transfer-Encoding: chunked?
        te = resp.getheader("Transfer-Encoding", "")
        record["chunked"] = "chunked" in te.lower()

        # Date header drift
        date_hdr = resp.getheader("Date")
        record["date_header"] = date_hdr
        if date_hdr:
            ts = _parse_http_date(date_hdr)
            if ts is not None:
                record["date_drift_s"] = round(time.time() - ts, 1)

        # Read body (limited)
        raw_body = resp.read(MAX_BODY_BYTES)
        record["actual_body_length"] = len(raw_body)

        if cl_header is not None:
            try:
                record["content_length_match"] = (int(cl_header) == len(raw_body))
            except ValueError:
                record["content_length_match"] = None

        body_text = raw_body.decode(ENCODING, "replace")
        record["body"] = body_text[:MAX_BODY_BYTES]
        record["body_sha256"] = hashlib.sha256(raw_body).hexdigest()

        conn.close()

    except TimeoutError:
        record["timed_out"] = True
        record["error"] = "timeout"
    except Exception as exc:
        record["error"] = str(exc)

    record["latency_s"] = round(time.monotonic() - t0, 3)
    return record


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=ENCODING) as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _append_csv(path: Path, rows: list[dict[str, Any]], target_name: str) -> None:
    write_header = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            row_out: dict[str, Any] = {
                "target": target_name,
                **{k: row.get(k, "") for k in _CSV_FIELDS if k != "target"},
            }
            row_out["body_snippet"] = (row.get("body") or "")[:200].replace("\n", " ")
            writer.writerow(row_out)


def _csv_without_pair(path: Path, target: str, run: int) -> None:
    if not path.exists():
        return
    temp_name: str | None = None
    try:
        with path.open("r", newline="", encoding=ENCODING) as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or _CSV_FIELDS
            rows = [
                row for row in reader
                if not (
                    row.get("target") == target
                    and str(row.get("run")) == str(run)
                )
            ]
        with tempfile.NamedTemporaryFile(
            mode="w",
            newline="",
            encoding=ENCODING,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            temp_name = fh.name
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, path)
        temp_name = None
    except Exception as exc:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
        print(
            f"ERROR: could not safely update CSV {path}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def _backup_pair(path: Path, csv_path: Path, target: str, run: int) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    if csv_path.exists():
        shutil.copy2(csv_path, csv_path.with_suffix(csv_path.suffix + ".bak"))
    _csv_without_pair(csv_path, target, run)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    targets_path = Path(args.targets) if Path(args.targets).is_file() else Path("harness/targets.yaml")
    with open(targets_path, encoding=ENCODING) as fh:
        targets_data = yaml.safe_load(fh)
    with open(args.requests, encoding=ENCODING) as fh:
        requests_data = yaml.safe_load(fh)

    all_targets  = targets_data.get("targets", [])
    all_requests = requests_data.get("requests", [])

    # Filter to HTTP targets
    http_targets = [t for t in all_targets if t.get("track") == "http"]
    selection = args.target
    if selection is None and not Path(args.targets).is_file():
        selection = args.targets
    if selection:
        requested = {n.strip() for n in selection.split(",")}
        http_targets = [t for t in http_targets if t["name"] in requested]

    if not http_targets:
        print("No HTTP targets selected.", file=sys.stderr)
        return 1

    # Safety: verify all hosts are 127.0.0.1
    for t in http_targets:
        if t.get("host") not in _ALLOWED_HOSTS:
            print(f"ERROR: target {t['name']} has non-localhost host.", file=sys.stderr)
            return 1

    if args.dry_run:
        print("Dry-run: YAML validated OK")
        print(f"  HTTP targets : {[t['name'] for t in http_targets]}")
        print(f"  Requests     : {len(all_requests)}")
        print(f"  Runs         : {args.runs}")
        return 0

    out_dir  = Path(args.out)
    csv_path = Path("results") / "http_requests_long.csv"
    expected_records = len(all_requests)
    planned: list[tuple[str, int, str]] = []
    for target in http_targets:
        for run_idx in range(1, args.runs + 1):
            pair = out_dir / f"{target['name']}_run{run_idx:02d}.jsonl"
            complete = pair.exists() and sum(
                1 for _ in pair.open(encoding=ENCODING)
            ) == expected_records
            planned.append((target["name"], run_idx, "run" if args.force or not complete else "skip"))
    print("Plan: " + ", ".join(f"{name}/run{run:02d}={action}"
                               for name, run, action in planned))

    for target in http_targets:
        tname = target["name"]
        host  = target["host"]
        port  = int(target["port"])
        print(f"\n=== HTTP Target: {tname} ({host}:{port}) ===")

        for run_idx in range(1, args.runs + 1):
            plan = next(item for item in planned if item[0] == tname and item[1] == run_idx)
            jsonl_path = out_dir / f"{tname}_run{run_idx:02d}.jsonl"
            if plan[2] == "skip":
                print(f"  Run {run_idx}/{args.runs} ... skipped (complete)")
                continue
            if args.force and jsonl_path.exists():
                _backup_pair(jsonl_path, csv_path, tname, run_idx)
            else:
                _csv_without_pair(csv_path, tname, run_idx)
            print(f"  Run {run_idx}/{args.runs} ...", end=" ", flush=True)
            t0 = time.monotonic()
            run_records: list[dict[str, Any]] = []

            for req in all_requests:
                rec = _do_request(host, port, req, args.timeout)
                rec["target"] = tname
                rec["run"]    = run_idx
                run_records.append(rec)

            elapsed = time.monotonic() - t0
            n_err = sum(1 for r in run_records if r.get("error"))
            print(f"done ({elapsed:.1f}s, {len(run_records)} reqs, {n_err} errors)")

            _write_jsonl(jsonl_path, run_records)
            _append_csv(csv_path, run_records, tname)

    print(f"\nDone. CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
