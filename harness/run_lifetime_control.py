#!/usr/bin/env python3
"""
harness/run_lifetime_control.py
Container-lifetime control: start Beelzebub ONCE and run N consecutive SSH
sessions against the SAME container (no recreate between runs).

Purpose: compare a persistent-container series with the Stage 4 fresh-container
slots. This script records evidence that the container is not recreated
(container id + State.StartedAt identical before and after every run) and
per-run metrics.

Usage:
    python harness/run_lifetime_control.py --runs 10
    python harness/run_lifetime_control.py --runs 10 --cost-cap 1.5 \
        --call-limit 45 --out results/exp/lifetime_control/beelzebub_persistent

Outputs (under --out):
    raw/beelzebub_runNN.jsonl     one file per session (run_ssh.py --run-index)
    api_proxy_log.jsonl           proxy requests + one slot_start marker per run
    manifest.jsonl                one line per run (container + metrics)
    status.json                   {"beelzebub:runNN:prompt": "complete"|...}
    lifetime.json                 summary incl. before/after container state
    driver.log                    human-readable log

Stops and tears everything down on completion, on a safety stop (call guard,
cost cap, container recreation) or on error. Never restarts the container
between runs.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_ssh  # noqa: E402
import run_stage4 as s4  # noqa: E402

ENCODING = "utf-8"
TARGET = "beelzebub"
DEFAULT_OUT = Path("results/exp/lifetime_control/beelzebub_persistent")
CALL_LIMIT_DEFAULT = 45
COST_CAP_DEFAULT = 1.5
TOTAL_CALL_CAP = 450

PROMPT_LINE_RE = __import__("re").compile(
    r"(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s+\S")

log = logging.getLogger("lifetime")


# ── pure helpers (unit tested) ────────────────────────────────────────────────

def parse_started_at(inspect_output: str) -> str:
    """`docker inspect -f '{{.Id}} {{.State.StartedAt}}'` → StartedAt field."""
    parts = inspect_output.strip().split()
    return parts[1] if len(parts) >= 2 else ""


def parse_inspect_id(inspect_output: str) -> str:
    parts = inspect_output.strip().split()
    return parts[0] if parts else ""


def parse_stats_mem(stats_output: str) -> str:
    """`docker stats --no-stream --format '{{.MemUsage}}'` → e.g. '12.3MiB / 1GiB'."""
    line = stats_output.strip().splitlines()[0] if stats_output.strip() else ""
    return line.strip()


def row_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-run metrics from one session's JSONL rows."""
    cmds = [r for r in records if r.get("cmd_id") and r["cmd_id"] != "exit"]
    lat = [r["latency_s"] for r in cmds
           if r.get("latency_s") is not None and not r.get("timed_out")]
    outs = [r.get("cleaned_output") or "" for r in cmds]
    return {
        "n_commands": len(cmds),
        "timeouts": sum(1 for r in cmds if r.get("timed_out")),
        "median_latency_s": round(statistics.median(lat), 4) if lat else None,
        "p95_latency_s": round(s4_percentile(lat, 95), 4) if lat else None,
        "oversized": sum(1 for o in outs if len(o) > 20_000),
        "leakage": sum(1 for o in outs if PROMPT_LINE_RE.search(o)),
    }


def s4_percentile(vals: list[float], p: float) -> float:
    if not vals:
        return float("nan")
    v = sorted(vals)
    k = p / 100.0 * (len(v) - 1)
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def guard_message(calls: int, limit: int = CALL_LIMIT_DEFAULT) -> str | None:
    if calls > limit:
        return f"slot_call_anomaly: {TARGET} {calls} calls"
    return None


def container_unchanged(before: dict[str, str], after: dict[str, str]) -> bool:
    return bool(before.get("id")) and before.get("id") == after.get("id") \
        and before.get("started_at") == after.get("started_at")


# ── docker helpers ────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding=ENCODING, errors="replace")


def _container_id() -> str:
    cmd = s4._compose_cmd(TARGET, use_proxy=True) + ["ps", "-q"]
    out = _run(cmd).stdout.strip()
    return out.splitlines()[0] if out else ""


def _container_state() -> dict[str, str]:
    cid = _container_id()
    if not cid:
        return {"id": "", "started_at": ""}
    r = _run(["docker", "inspect", "-f", "{{.Id}} {{.State.StartedAt}}", cid])
    return {"id": parse_inspect_id(r.stdout), "started_at": parse_started_at(r.stdout)}


def _mem_usage(cid: str) -> str:
    if not cid:
        return ""
    r = _run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", cid])
    return parse_stats_mem(r.stdout)


def _log_bytes(cid: str) -> int:
    if not cid:
        return 0
    r = _run(["docker", "logs", cid])
    return len((r.stdout or "").encode("utf-8", "replace")) + \
        len((r.stderr or "").encode("utf-8", "replace"))


def _docker_ps() -> str:
    return _run(["docker", "ps", "-q"]).stdout.strip()


# ── main flow ─────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--call-limit", type=int, default=CALL_LIMIT_DEFAULT,
                   help="abort when one run makes more proxy calls than this")
    p.add_argument("--cost-cap", type=float, default=COST_CAP_DEFAULT)
    p.add_argument("--targets-yaml", default="harness/targets.yaml")
    p.add_argument("--commands-yaml", default="harness/commands.yaml")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def _setup_logging(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s lifetime: %(message)s")
    fh = logging.FileHandler(out / "driver.log", encoding=ENCODING)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.handlers[:] = [fh, sh]


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding=ENCODING).splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def run(argv: list[str] | None = None) -> int:  # noqa: C901
    args = parse_args(argv)
    out = Path(args.out)
    if args.dry_run:
        print(f"would run {args.runs} sessions of {TARGET} against one container,")
        print(f"out={out} call_limit={args.call_limit} cost_cap={args.cost_cap}")
        return 0

    _setup_logging(out)
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    proxy_log = out / "api_proxy_log.jsonl"
    status: dict[str, Any] = {}
    manifest: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"target": TARGET, "runs": args.runs,
                               "call_limit": args.call_limit,
                               "cost_cap": args.cost_cap, "runs_data": []}
    proxy = None
    exit_code = 0
    stop_reason = ""

    if not out.exists():
        out.mkdir(parents=True, exist_ok=True)

    try:
        if s4._proxy_reachable():
            raise RuntimeError("port 11435 already in use; refusing to start")
        if _docker_ps():
            log.warning("containers already running; beelzebub must be alone for "
                        "a clean lifetime control: %s", _docker_ps().split())

        proxy = s4._start_proxy(proxy_log, log)
        if not s4._proxy_reachable():
            raise RuntimeError("proxy did not start")
        log.info("proxy ready")

        s4._docker_down(TARGET, log)
        s4._docker_up(TARGET, log, use_proxy=True)
        if not s4._wait_ssh_banner("127.0.0.1", s4._TARGET_PORT[TARGET], 60.0, log):
            raise RuntimeError("beelzebub SSH banner not received")

        state0 = _container_state()
        log.info("container started: id=%s started_at=%s", state0["id"][:12],
                 state0["started_at"])
        summary["container_initial"] = state0
        summary["container_image"] = s4._get_image_id(TARGET)

        for k in range(1, args.runs + 1):
            before = _container_state()
            if not container_unchanged(state0, before):
                stop_reason = "container_recreated"
                log.error("SAFETY STOP: container changed before run %d", k)
                exit_code = 3
                break

            calls_before = s4._proxy_request_count(proxy_log)
            cost_before, _ = s4._estimate_cost_from_proxy_log(proxy_log)
            s4._write_slot_boundary(proxy_log, k, 1, TARGET, "prompt")
            wall = datetime.datetime.now(datetime.timezone.utc).isoformat()

            argv_ssh = [
                "--targets", args.targets_yaml,
                "--commands", args.commands_yaml,
                "--runs", "1", "--run-index", str(k),
                "--out", str(raw_dir),
                "--timeout", str(int(args.timeout)),
                "--timing", "prompt",
                "--target", TARGET,
                "--force",
                "--csv-dir", str(raw_dir),
            ]
            log.info("run %d/%d: run_ssh.main %s", k, args.runs, " ".join(argv_ssh))
            rc = run_ssh.main(argv_ssh)

            jsonl = raw_dir / f"{TARGET}_run{k:02d}.jsonl"
            s4._inject_stage4_fields(jsonl, {
                "s4_run": k, "s4_position": 1, "s4_order_seed": 0,
                "s4_timing_mode": "prompt", "s4_wall_start": wall,
                "s4_harness_ver": "lifetime-control",
            })
            metrics = row_metrics(_jsonl_rows(jsonl))

            after = _container_state()
            calls = s4._proxy_request_count(proxy_log) - calls_before
            cost_total, _ = s4._estimate_cost_from_proxy_log(proxy_log)
            cumulative_calls = sum(r["calls"] for r in summary["runs_data"]) + calls
            rec = {
                "run": k, "rc": rc, **metrics, "calls": calls,
                "cost_run_usd": round(cost_total - cost_before, 6),
                "cost_cum_usd": round(cost_total, 6),
                "container_before": before, "container_after": after,
                "container_unchanged": container_unchanged(state0, after),
                "mem_usage": _mem_usage(after["id"]),
                "log_bytes": _log_bytes(after["id"]),
                "wall_start_utc": wall,
            }
            summary["runs_data"].append(rec)
            manifest.append({"run": k, "position": 1, "target": TARGET,
                             "modes": ["prompt"], "modes_run": ["prompt"],
                             "resumed": False, "order_seed": 0,
                             "planned_start_utc": wall})
            status[f"{TARGET}:run{k:02d}:prompt"] = "complete" if rc == 0 else f"rc={rc}"
            log.info("run %d: rc=%d cmds=%d timeouts=%d median=%ss calls=%d "
                     "mem=%s log=%dB unchanged=%s", k, rc, metrics["n_commands"],
                     metrics["timeouts"], metrics["median_latency_s"], calls,
                     rec["mem_usage"], rec["log_bytes"], rec["container_unchanged"])

            msg = guard_message(calls, args.call_limit)
            if msg:
                stop_reason = msg
                status["safety_stop"] = msg
                log.error("SAFETY STOP: %s", msg)
                exit_code = 3
                break
            if cumulative_calls > TOTAL_CALL_CAP:
                stop_reason = f"total_calls {cumulative_calls} > {TOTAL_CALL_CAP}"
                status["safety_stop"] = stop_reason
                log.error("SAFETY STOP: %s", stop_reason)
                exit_code = 3
                break
            if cost_total > args.cost_cap:
                stop_reason = f"cost ${cost_total:.4f} > cap ${args.cost_cap:.2f}"
                status["safety_stop"] = stop_reason
                log.error("SAFETY STOP: %s", stop_reason)
                exit_code = 3
                break
            if not rec["container_unchanged"]:
                stop_reason = "container_recreated"
                status["safety_stop"] = stop_reason
                log.error("SAFETY STOP: container changed during run %d", k)
                exit_code = 3
                break

        state_end = _container_state()
        summary["container_final"] = state_end
        summary["container_never_recreated"] = container_unchanged(state0, state_end)
        summary["stop_reason"] = stop_reason
        summary["total_calls"] = sum(r["calls"] for r in summary["runs_data"])
        summary["total_cost_usd"] = round(
            s4._estimate_cost_from_proxy_log(proxy_log)[0], 6)
        log.info("container at end: id=%s started_at=%s never_recreated=%s",
                 state_end["id"][:12], state_end["started_at"],
                 summary["container_never_recreated"])
    except Exception as exc:  # noqa: BLE001 — always tear down
        exit_code = 1
        log.exception("control run failed: %s", exc)
        summary["error"] = str(exc)
    finally:
        try:
            if _container_id():
                s4._docker_down(TARGET, log)
        except Exception:
            log.warning("teardown: docker down failed", exc_info=True)
        if proxy is not None:
            log.info("Stopping proxy ...")
            proxy.terminate()
            try:
                proxy.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proxy.kill()
        (out / "lifetime.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding=ENCODING)
        (out / "status.json").write_text(json.dumps(status, indent=2), encoding=ENCODING)
        with open(out / "manifest.jsonl", "w", encoding=ENCODING) as fh:
            for m in manifest:
                fh.write(json.dumps(m) + "\n")
        log.info("Driver exiting with code %d.", exit_code)

    return exit_code


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
