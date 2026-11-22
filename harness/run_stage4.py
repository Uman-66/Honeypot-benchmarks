#!/usr/bin/env python3
"""
harness/run_stage4.py
Stage 4 driver: 20-run pass with shuffled target order.

Usage:
    python harness/run_stage4.py --runs 20 --timing prompt --seed 2026
    python harness/run_stage4.py --runs 1  --timing prompt --seed 2026 --out results/exp/stage4_smoke
    python harness/run_stage4.py --dry-run --runs 20 --timing prompt --seed 2026
    python harness/run_stage4.py --preflight

Default targets (in --dry-run order):
    groundtruth_ssh, cowrie, llmhoneypot, deceive, beelzebub, vellmes, advshellm,
    groundtruth_http, galah

Output layout (all files under --out):
    raw/                   SSH JSONL  ({target}_run{N:02d}.jsonl)
    raw_http/              HTTP JSONL ({target}_run{N:02d}.jsonl)
    manifest.jsonl         one line per slot (run, position, target, mode, planned_start_utc)
    status.json            last-written status of every slot
    driver.log             human-readable progress log
    api_proxy_log.jsonl    forwarded from api_proxy; slot boundaries written here too
    containers.json        per-slot image IDs and container names

Schema additions vs run_ssh.py row schema:
    run, position, order_seed, timing_mode, wall_clock_start (UTC ISO),
    harness_version (git commit hash), proxy_slot_marker.
See docs/STAGE4_NOTES.md for the full documented schema.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))

# Imported lazily to avoid circular issues and to allow --dry-run / --preflight
# to work without all deps.
import run_ssh        # noqa: E402
import run_http       # noqa: E402

ENCODING = "utf-8"

DEFAULT_TARGETS = [
    "groundtruth_ssh",
    "cowrie",
    "llmhoneypot",
    "deceive",
    "beelzebub",
    "vellmes",
    "advshellm",
    "groundtruth_http",
    "galah",
]

# LLM SSH targets that use the proxy overlay (need --force-recreate per slot)
LLM_SSH_TARGETS = {"deceive", "beelzebub", "vellmes", "advshellm"}
# galah also supports the proxy via OPENAI_BASE_URL → LLM_SERVER_URL mapping
LLM_HTTP_TARGETS = {"galah"}

# Docker Compose project files; keyed by target name
# (the driver uses docker compose -f <base> [-f <proxy>] ...)
_COMPOSE_FILES: dict[str, dict[str, str]] = {
    "groundtruth_ssh": {"base": "docker/groundtruth_ssh.compose.yaml"},
    "cowrie":          {"base": "docker/cowrie.compose.yaml"},
    "llmhoneypot":     {"base": "docker/llmhoneypot.compose.yaml"},
    "deceive":         {"base": "docker/deceive.compose.yaml",
                        "proxy": "docker/deceive.proxy.yaml"},
    "beelzebub":       {"base": "docker/beelzebub.compose.yaml",
                        "proxy": "docker/beelzebub.proxy.yaml"},
    "vellmes":         {"base": "docker/vellmes.compose.yaml",
                        "proxy": "docker/vellmes.proxy.yaml"},
    "advshellm":       {"base": "docker/advshellm.compose.yaml",
                        "proxy": "docker/advshellm.proxy.yaml"},
    "groundtruth_http": {"base": "docker/groundtruth_http.compose.yaml"},
    "galah":           {"base": "docker/galah.compose.yaml",
                        "proxy": "docker/galah.proxy.yaml"},  # created by this driver
}

# Port each target listens on (host side)
_TARGET_PORT: dict[str, int] = {
    "groundtruth_ssh": 2225,
    "cowrie":          2223,
    "llmhoneypot":     2227,
    "deceive":         8022,
    "beelzebub":       2222,
    "vellmes":         2228,
    "advshellm":       2224,
    "groundtruth_http": 2226,
    "galah":           8088,
}

HTTP_TARGETS = {"groundtruth_http", "galah"}
SSH_TARGETS  = set(DEFAULT_TARGETS) - HTTP_TARGETS

# Safety thresholds
SAFETY_HTTP_ERR_RATE   = 0.20   # Fireworks HTTP error rate over last 50 proxy requests
SAFETY_TIMEOUT_FRAC    = 0.50   # LLM SSH target: fraction of commands that may time out
SAFETY_CONSEC_SLOTS    = 3      # consecutive slots above SAFETY_TIMEOUT_FRAC → stop
SAFETY_DISK_MIN_GB     = 5.0
SAFETY_COST_CAP_DEFAULT = 6.0   # USD with the corrected model below
COST_PER_PROMPT_TOKEN  = 0.15 / 1_000_000         # uncached input
COST_PER_CACHED_PROMPT_TOKEN = 0.03 / 1_000_000   # cached (cache-hit) input
COST_PER_COMPL_TOKEN   = 0.50 / 1_000_000         # output

# Per-slot call sanity guard. One slot runs the command list once, so an LLM
# SSH slot measured 36-39 provider calls and a galah slot 20 in run 1. Anything
# far above that means the slot replayed the list (the --runs multiplier bug).
SAFETY_SLOT_CALLS_LLM_SSH = 80
SAFETY_SLOT_CALLS_GALAH   = 45
EXPECTED_MODEL         = "accounts/fireworks/models/glm-5p3-flash"

# Port-ready poll
_PORT_POLL_INTERVAL = 1.0   # seconds between readiness polls
_PORT_READY_TIMEOUT = 120   # seconds to wait for port to open
_BANNER_CHECK_TIMEOUT = 15  # seconds to wait for SSH banner after port opens

logger = logging.getLogger("stage4")

# Subdirectory holding quiet-mode check rows. Quiet and prompt sessions must
# never share a file name: run_ssh.py --force copies the old file to .bak and
# rewrites the canonical name, which would silently move prompt rows into .bak.
QUIET_SUBDIR = "raw_quiet"


# -- Console-safe output -------------------------------------------------------
#
# A stray non-ASCII character in any print() raised UnicodeEncodeError on a
# Windows cp1252 console and aborted the whole slot loop (skipping every
# remaining slot). All driver output now goes through _safe_print(), and the
# stdio streams are reconfigured with errors="replace" at start-up so prints
# coming from run_ssh.py / run_http.py cannot abort a slot either.

def _safe_print(*args: Any, **kwargs: Any) -> None:
    """print() that can never raise UnicodeEncodeError."""
    stream = kwargs.pop("file", None) or sys.stdout
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    flush = kwargs.pop("flush", False)
    text = sep.join(str(a) for a in args) + end
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding, "strict")
    except (UnicodeEncodeError, LookupError):
        try:
            text = text.encode(encoding, "replace").decode(encoding, "replace")
        except LookupError:
            text = text.encode("ascii", "replace").decode("ascii")
    try:
        stream.write(text)
    except UnicodeEncodeError:
        try:
            stream.write(text.encode("ascii", "replace").decode("ascii"))
        except Exception:
            return
    except Exception:
        return
    if flush:
        try:
            stream.flush()
        except Exception:
            pass


def _reconfigure_stdio() -> None:
    """Make stdout/stderr tolerate any unencodable character (cp1252 consoles)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def _mode_output_dir(out_root: Path, target: str, mode: str) -> Path:
    """Directory that holds the JSONL for (target, mode).

    HTTP targets write to raw_http/; quiet-check SSH sessions write to
    raw_quiet/; everything else writes to raw/.
    """
    if target in HTTP_TARGETS:
        return out_root / "raw_http"
    if mode == "quiet":
        return out_root / QUIET_SUBDIR
    return out_root / "raw"


# -- Pure safety-stop predicates ----------------------------------------------
#
# Each returns the message to record in status.json["safety_stop"], or None when
# the condition is not met. Pure so they can be unit-tested without Docker or
# API access.

def _cost_stop_message(cost_usd: float, cap: float, n_calls: int) -> str | None:
    if cost_usd > cap:
        return (f"cost_cap_exceeded: ${cost_usd:.4f} > ${cap} "
                f"after {n_calls} calls")
    return None


def _disk_stop_message(free_gb: float) -> str | None:
    if free_gb < SAFETY_DISK_MIN_GB:
        return f"disk_too_low: {free_gb:.2f} GB < {SAFETY_DISK_MIN_GB} GB"
    return None


def _error_rate_stop_message(err_rate: float) -> str | None:
    if err_rate > SAFETY_HTTP_ERR_RATE:
        return f"high_fireworks_error_rate: {err_rate:.1%} > {SAFETY_HTTP_ERR_RATE:.0%}"
    return None


def _model_stop_message(bad_model: str | None) -> str | None:
    if bad_model:
        return f"unexpected_model: {bad_model!r}"
    return None


def _consec_timeout_stop(status: dict[str, Any], target: str,
                         n_cmds: int, n_to: int) -> str | None:
    """Update the consecutive-timeout counter; return a stop message if hit."""
    if (target in LLM_SSH_TARGETS
            and n_cmds > 0
            and (n_to / n_cmds) > SAFETY_TIMEOUT_FRAC):
        consec = int(status.get(f"_consec_timeout_{target}", 0) + 1)
        status[f"_consec_timeout_{target}"] = consec
        if consec >= SAFETY_CONSEC_SLOTS:
            return (f"consec_timeout_stop: {target} has {consec} consecutive "
                    f"slots above {SAFETY_TIMEOUT_FRAC:.0%} timeout rate")
        return None
    status[f"_consec_timeout_{target}"] = 0
    return None

# ── Helper: get git HEAD hash ─────────────────────────────────────────────────

def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, encoding=ENCODING, errors="replace", check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


# ── Helper: safe JSON write ───────────────────────────────────────────────────

def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        with os.fdopen(fd, "w", encoding=ENCODING) as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding=ENCODING) as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Helper: slot key ─────────────────────────────────────────────────────────

def _slot_key(target: str, run: int, mode: str) -> str:
    return f"{target}:run{run:02d}:{mode}"


def _mode_jsonl_path(mode_dir: Path, target: str, run: int) -> Path:
    """JSONL path for one (target, run) inside its mode directory."""
    return mode_dir / f"{target}_run{run:02d}.jsonl"


# ── Shuffle ───────────────────────────────────────────────────────────────────

def shuffle_targets(targets: list[str], seed: int, run: int) -> list[str]:
    """Return *targets* in a deterministic shuffled order for (seed, run)."""
    rng = random.Random(seed * 1000 + run)
    order = list(targets)
    rng.shuffle(order)
    return order


# ── Docker helpers ─────────────────────────────────────────────────────────────

def _compose_cmd(target: str, use_proxy: bool = True) -> list[str]:
    """Return the base `docker compose -f ... -f ...` prefix for *target*."""
    files = _COMPOSE_FILES.get(target, {})
    base = files.get("base")
    if not base:
        raise ValueError(f"No compose file registered for target {target!r}")
    cmd = ["docker", "compose", "-f", base]
    proxy_file = files.get("proxy")
    if use_proxy and proxy_file:
        proxy_path = Path(proxy_file)
        if proxy_path.exists():
            cmd += ["-f", proxy_file]
    return cmd


def _docker_down(target: str, log: logging.Logger) -> None:
    """Bring down compose project for *target* without touching volumes."""
    cmd = _compose_cmd(target, use_proxy=False) + ["down", "--remove-orphans"]
    log.debug("docker down: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, encoding=ENCODING, errors="replace")
    if result.returncode != 0:
        log.warning("docker down warning for %s: %s", target, result.stderr.strip())


def _docker_up(target: str, log: logging.Logger, use_proxy: bool = True) -> None:
    """Start compose project for *target*, force-recreating the main service."""
    cmd = _compose_cmd(target, use_proxy=use_proxy) + [
        "up", "-d", "--force-recreate",
    ]
    log.debug("docker up: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, encoding=ENCODING, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(
            f"docker up failed for {target}: {result.stderr.strip()}"
        )


def _get_image_id(target: str) -> str:
    """Return the image ID of the running container for *target*."""
    # Service name may differ from target name (e.g. beelzebub-ssh)
    # We ask docker compose for the container id, then inspect it.
    cmd = _compose_cmd(target, use_proxy=False) + ["ps", "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding=ENCODING, errors="replace")
    cid = result.stdout.strip().split()[0] if result.stdout.strip() else ""
    if not cid:
        return "unknown"
    r2 = subprocess.run(
        ["docker", "inspect", "--format", "{{.Image}}", cid],
        capture_output=True, text=True, encoding=ENCODING, errors="replace",
    )
    return r2.stdout.strip() or "unknown"


def _get_container_name(target: str) -> str:
    cmd = _compose_cmd(target, use_proxy=False) + ["ps", "--format", "{{.Name}}"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding=ENCODING, errors="replace")
    return result.stdout.strip().split()[0] if result.stdout.strip() else "unknown"


def _clear_galah_cache(log: logging.Logger) -> str:
    """
    Clear galah's SQLite cache (cache.db in the galah_logs named volume).

    Strategy: recreate the galah_logs volume by running `docker compose down`
    with --volumes for the galah project (removes only declared volumes for
    that project), then `docker compose up`.  The driver then verifies the
    cache is absent/empty after startup.

    Returns a human-readable status string for the log.
    """
    # Down with volume removal for galah project only
    cmd_down = ["docker", "compose", "-f", "docker/galah.compose.yaml",
                 "down", "--volumes", "--remove-orphans"]
    log.info("Clearing galah cache: %s", " ".join(cmd_down))
    r = subprocess.run(cmd_down, capture_output=True, text=True, encoding=ENCODING, errors="replace")
    if r.returncode != 0:
        log.warning("galah down --volumes warning: %s", r.stderr.strip())
    return f"galah_logs volume removed (rc={r.returncode})"


GALAH_VOLUME = "galah_galah_logs"


def _galah_volume_created_utc() -> datetime.datetime | None:
    """Creation time of the galah_logs volume, or None if it is missing."""
    r = subprocess.run(
        ["docker", "volume", "inspect", GALAH_VOLUME, "--format", "{{.CreatedAt}}"],
        capture_output=True, text=True, encoding=ENCODING, errors="replace",
    )
    raw = r.stdout.strip()
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _volume_is_fresh(created_utc: datetime.datetime,
                     slot_start_utc: datetime.datetime,
                     tolerance_s: float = 5.0) -> bool:
    """True when the volume was created at (or after) the slot start."""
    return created_utc >= slot_start_utc - datetime.timedelta(seconds=tolerance_s)


def _galah_cache_db_size(log: logging.Logger) -> str:
    cmd = _compose_cmd("galah", use_proxy=False) + ["ps", "-q"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding=ENCODING,
                       errors="replace")
    cid = r.stdout.strip().split()[0] if r.stdout.strip() else ""
    if not cid:
        return "container-not-found"
    r2 = subprocess.run(
        ["docker", "exec", cid, "sh", "-c",
         "test -f /galah/logs/cache.db && stat -c%s /galah/logs/cache.db || echo 0"],
        capture_output=True, text=True, encoding=ENCODING, errors="replace",
    )
    return f"{r2.stdout.strip()} bytes"


def _verify_galah_cache_empty(
    log: logging.Logger,
    slot_start_utc: datetime.datetime | None = None,
) -> tuple[bool, str]:
    """Confirm the galah_logs volume was recreated for this slot.

    galah creates cache.db (with its schema) at startup, so a fresh DB is ~12 KB
    and a size test cannot show whether the cache holds entries. The volume's
    creation time can: `docker compose down --volumes` removes the volume, and
    the next `up` creates a new one after the slot started.
    """
    created = _galah_volume_created_utc()
    if created is None:
        log.warning("galah volume %s not found", GALAH_VOLUME)
        return False, "volume not found"
    start = slot_start_utc or datetime.datetime.now(datetime.timezone.utc)
    age_s = (datetime.datetime.now(datetime.timezone.utc) - created).total_seconds()
    fresh = _volume_is_fresh(created, start)
    detail = (f"volume created {created.isoformat()} ({age_s:.0f} s ago, "
              f"slot start {start.isoformat()}), fresh={fresh}, "
              f"cache.db={_galah_cache_db_size(log)}")
    return fresh, detail



# ── Port readiness check ──────────────────────────────────────────────────────

def _wait_port(host: str, port: int, timeout: float, log: logging.Logger) -> bool:
    """Block until TCP port answers or timeout expires. Returns True on success."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(_PORT_POLL_INTERVAL)
    log.warning("Port %d not ready after %.0f s", port, timeout)
    return False


def _wait_ssh_banner(host: str, port: int, timeout: float, log: logging.Logger) -> bool:
    """Read the SSH banner from (host, port). Returns True if banner found."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0) as sock:
                sock.settimeout(2.0)
                banner = sock.recv(256)
                if banner.startswith(b"SSH-"):
                    log.debug("SSH banner: %s", banner[:60])
                    return True
        except Exception:
            pass
        time.sleep(_PORT_POLL_INTERVAL)
    log.warning("SSH banner not received on port %d after %.0f s", port, timeout)
    return False


# ── Proxy helpers ─────────────────────────────────────────────────────────────

def _start_proxy(log_path: Path, log: logging.Logger) -> subprocess.Popen[str]:  # type: ignore[type-arg]
    """Start api_proxy.py in a subprocess, binding on 0.0.0.0 for containers."""
    cmd = [
        sys.executable,
        str(HARNESS_DIR / "api_proxy.py"),
        "--bind", "0.0.0.0",
        "--allow-remote-bind",
        "--log", str(log_path),
    ]
    log.info("Starting proxy: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=ENCODING,
        errors="replace",
    )
    # Give it a moment to bind
    time.sleep(1.5)
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        raise RuntimeError(
            f"api_proxy.py exited immediately: rc={proc.returncode}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )
    return proc


def _proxy_reachable(port: int = 11435) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0):
            return True
    except OSError:
        return False


def _write_slot_boundary(proxy_log_path: Path, run: int, position: int,
                         target: str, mode: str) -> None:
    """Append a slot-boundary marker to the proxy log so rows can be joined to slots."""
    _append_jsonl(proxy_log_path, {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "slot_start",
        "run": run,
        "position": position,
        "target": target,
        "mode": mode,
    })


# ── Cost estimation ───────────────────────────────────────────────────────────

def _estimate_cost_from_proxy_log(proxy_log_path: Path) -> tuple[float, int]:
    """
    Read proxy log and return (cumulative_cost_usd, n_requests).
    Counts only real request rows (not slot_start markers).
    """
    if not proxy_log_path.exists():
        return 0.0, 0
    cost = 0.0
    n = 0
    with open(proxy_log_path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") == "slot_start":
                continue
            n += 1
            pt = entry.get("prompt_tokens") or 0
            ct = entry.get("completion_tokens") or 0
            cached = _cached_prompt_tokens(entry)
            if cached is None:
                # No cache breakdown in this row: bill the whole prompt at the
                # uncached rate (conservative, never undercounts).
                cost += pt * COST_PER_PROMPT_TOKEN
            else:
                cached = min(cached, pt)
                cost += ((pt - cached) * COST_PER_PROMPT_TOKEN
                         + cached * COST_PER_CACHED_PROMPT_TOKEN)
            cost += ct * COST_PER_COMPL_TOKEN
    return cost, n


def _cached_prompt_tokens(entry: dict[str, Any]) -> int | None:
    """Cache-hit prompt tokens the provider reported, or None if absent.

    Cached prompt tokens are billed at a fraction of the uncached rate; billing
    every prompt token at $0.15/M overestimated the first Stage 4 batch by
    about 3.8x because 95.6% of its prompt tokens were cache hits.
    """
    usage = entry.get("usage")
    if not isinstance(usage, dict):
        return None
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        return None
    cached = details.get("cached_tokens")
    if isinstance(cached, (int, float)):
        return int(cached)
    return None


def _recent_http_error_rate(proxy_log_path: Path, window: int = 50) -> float:
    """Return HTTP error rate (5xx / total) over the last *window* real requests."""
    if not proxy_log_path.exists():
        return 0.0
    rows: list[dict[str, Any]] = []
    with open(proxy_log_path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") == "slot_start":
                continue
            rows.append(entry)
    recent = rows[-window:]
    if not recent:
        return 0.0
    errors = sum(1 for r in recent if (r.get("status") or 0) >= 500)
    return errors / len(recent)


def _proxy_request_count(proxy_log_path: Path) -> int:
    """Number of real request rows in the proxy log (slot markers excluded)."""
    if not proxy_log_path.exists():
        return 0
    n = 0
    with open(proxy_log_path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") == "slot_start":
                continue
            n += 1
    return n


def _slot_call_limit(target: str) -> int | None:
    """Maximum plausible provider calls for one slot of *target*."""
    if target == "galah":
        return SAFETY_SLOT_CALLS_GALAH
    if target in LLM_SSH_TARGETS:
        return SAFETY_SLOT_CALLS_LLM_SSH
    return None


def _slot_call_anomaly_message(target: str, n_calls: int) -> str | None:
    """Flag a slot that made far more provider calls than its list explains."""
    limit = _slot_call_limit(target)
    if limit is not None and n_calls > limit:
        return f"slot_call_anomaly: {target} {n_calls} calls"
    return None


def _unexpected_model_seen(proxy_log_path: Path) -> str | None:
    """Return the first unexpected model string seen in the proxy log, or None."""
    if not proxy_log_path.exists():
        return None
    with open(proxy_log_path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") == "slot_start":
                continue
            m = entry.get("model_reported")
            if m and m != EXPECTED_MODEL:
                return m
    return None


# ── Disk space check ──────────────────────────────────────────────────────────

def _free_disk_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


# ── Duplicate guard (extend run_ssh.py's logic to include mode) ───────────────

def _is_complete_ssh(out_dir: Path, target: str, run: int, timing: str) -> bool:
    """True if the SSH JSONL for (target, run, timing) is complete."""
    path = out_dir / f"{target}_run{run:02d}.jsonl"
    if not path.exists():
        return False
    # For quiet-check a separate file is used (see naming convention below)
    # Count lines; expect 37 (all commands including exit)
    try:
        n = sum(1 for _ in path.open(encoding=ENCODING))
        return n == 37  # 36 scored + exit
    except OSError:
        return False


def _is_complete_http(out_dir: Path, target: str, run: int) -> bool:
    path = out_dir / f"{target}_run{run:02d}.jsonl"
    if not path.exists():
        return False
    try:
        n = sum(1 for _ in path.open(encoding=ENCODING))
        return n == 20
    except OSError:
        return False


def _backup_partial(path: Path) -> None:
    """Rename a partial JSONL to .partial.bak (overwrite any previous backup)."""
    bak = path.with_suffix(".partial.bak")
    try:
        path.rename(bak)
        logger.debug("Backed up partial slot: %s -> %s", path.name, bak.name)
    except OSError as exc:
        logger.warning("Could not back up partial %s: %s", path, exc)


# ── Run a single SSH slot ─────────────────────────────────────────────────────

def _run_ssh_slot(
    target_cfg: dict[str, Any],
    run: int,
    out_dir: Path,
    timing: str,
    seed: int,
    position: int,
    harness_ver: str,
    timeout: float,
    targets_yaml: str,
    commands_yaml: str,
    log: logging.Logger,
) -> dict[str, Any]:
    """
    Run one SSH target for one run via run_ssh.main().

    Returns a status dict: completed, timeouts, n_commands.
    Injects extra fields (run, position, order_seed, etc.) into every JSONL row
    post-write by rewriting the file once.
    """
    tname = target_cfg["name"]
    jsonl_path = out_dir / f"{tname}_run{run:02d}.jsonl"

    wall_start = datetime.datetime.now(datetime.timezone.utc).isoformat()

    argv = [
        "--targets", targets_yaml,
        "--commands", commands_yaml,
        "--runs", "1",
        "--run-index", str(run),
        "--out", str(out_dir),
        "--timeout", str(int(timeout)),
        "--timing", timing,
        "--target", tname,
        "--force",
        "--csv-dir", str(out_dir),
    ]
    log.debug("run_ssh.main argv: %s", argv)

    rc = run_ssh.main(argv)

    if rc != 0:
        log.warning("run_ssh.main returned %d for %s run %d", rc, tname, run)

    # Inject stage4 extra fields into every row in the JSONL
    _inject_stage4_fields(jsonl_path, {
        "s4_run":         run,
        "s4_position":    position,
        "s4_order_seed":  seed,
        "s4_timing_mode": timing,
        "s4_wall_start":  wall_start,
        "s4_harness_ver": harness_ver,
    })

    # Collect stats
    n_commands = 0
    n_timeouts = 0
    if jsonl_path.exists():
        with open(jsonl_path, encoding=ENCODING) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("cmd_id") and rec["cmd_id"] != "exit":
                    n_commands += 1
                    if rec.get("timed_out"):
                        n_timeouts += 1

    return {
        "rc": rc,
        "n_commands": n_commands,
        "n_timeouts": n_timeouts,
        "completed": (rc == 0),
    }


def _run_http_slot(
    target_cfg: dict[str, Any],
    run: int,
    out_dir: Path,
    seed: int,
    position: int,
    harness_ver: str,
    timeout: float,
    targets_yaml: str,
    requests_yaml: str,
    log: logging.Logger,
) -> dict[str, Any]:
    """Run one HTTP target for one run via run_http.main()."""
    tname = target_cfg["name"]
    jsonl_path = out_dir / f"{tname}_run{run:02d}.jsonl"
    wall_start = datetime.datetime.now(datetime.timezone.utc).isoformat()

    argv = [
        "--targets", targets_yaml,
        "--requests", requests_yaml,
        "--runs", "1",
        "--run-index", str(run),
        "--out", str(out_dir),
        "--timeout", str(int(timeout)),
        "--target", tname,
        "--force",
        "--csv-dir", str(out_dir),
    ]
    log.debug("run_http.main argv: %s", argv)

    rc = run_http.main(argv)

    _inject_stage4_fields(jsonl_path, {
        "s4_run":         run,
        "s4_position":    position,
        "s4_order_seed":  seed,
        "s4_timing_mode": "http",
        "s4_wall_start":  wall_start,
        "s4_harness_ver": harness_ver,
    })

    n_requests = 0
    if jsonl_path.exists():
        with open(jsonl_path, encoding=ENCODING) as fh:
            n_requests = sum(1 for l in fh if l.strip())

    return {
        "rc": rc,
        "n_commands": n_requests,
        "n_timeouts": 0,
        "completed": (rc == 0),
    }


def _inject_stage4_fields(jsonl_path: Path, extra: dict[str, Any]) -> None:
    """Rewrite *jsonl_path* adding *extra* keys to every JSONL row (in-place)."""
    if not jsonl_path.exists():
        return
    rows: list[str] = []
    with open(jsonl_path, encoding=ENCODING) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec.update(extra)
                rows.append(json.dumps(rec, ensure_ascii=False))
            except json.JSONDecodeError:
                rows.append(line)
    with open(jsonl_path, "w", encoding=ENCODING) as fh:
        for row in rows:
            fh.write(row + "\n")


# ── Preflight ─────────────────────────────────────────────────────────────────

def preflight(out_dir: Path, log: logging.Logger) -> bool:
    """
    Run pre-flight checks. Prints results to stdout.
    Returns True if everything passes (may still warn).
    """
    ok = True
    _safe_print("\n-- Stage 4 Preflight --------------------------------------------------")

    # 1. Docker daemon
    r = subprocess.run(["docker", "info"], capture_output=True, text=True, encoding=ENCODING, errors="replace")
    if r.returncode != 0:
        _safe_print("FAIL  Docker daemon not reachable. Start Docker Desktop.")
        ok = False
    else:
        _safe_print("PASS  Docker daemon reachable.")

    # 2. .env present and key set (report only present/absent)
    env_path = Path(".env")
    if not env_path.exists():
        _safe_print("FAIL  .env not found in current directory.")
        ok = False
    else:
        with open(env_path, encoding=ENCODING) as fh:
            content = fh.read()
        # Check presence of OPENAI_API_KEY= (do NOT print the value)
        if "OPENAI_API_KEY=" in content:
            # Verify it has a non-empty value (don't print it)
            m = re.search(r"OPENAI_API_KEY=(.+)", content)
            has_value = bool(m and m.group(1).strip())
            _safe_print(f"{'PASS' if has_value else 'FAIL'}  OPENAI_API_KEY {'set' if has_value else 'empty'} in .env.")
            if not has_value:
                ok = False
        else:
            _safe_print("FAIL  OPENAI_API_KEY not found in .env.")
            ok = False

    # 3. Compose files and images
    for target, files in _COMPOSE_FILES.items():
        base = files.get("base", "")
        if base and not Path(base).exists():
            _safe_print(f"FAIL  Missing compose file: {base}")
            ok = False

    # Check images exist for a few key targets
    r2 = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True, encoding=ENCODING, errors="replace",
    )
    images = set(r2.stdout.splitlines())
    # We only warn if no honeypot-related images exist at all
    hpot_images = [i for i in images if any(
        kw in i for kw in ("honeypot", "cowrie", "galah", "beelzebub", "advshellm")
    )]
    if not hpot_images:
        _safe_print("WARN  No honeypot images found. Run docker compose build for each target first.")
    else:
        _safe_print(f"PASS  At least {len(hpot_images)} honeypot-related image(s) present.")

    # 4. Ports free (none of the target ports should be open before we start)
    busy_ports = []
    for target, port in _TARGET_PORT.items():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                busy_ports.append(f"{target}:{port}")
        except OSError:
            pass
    if busy_ports:
        _safe_print(f"WARN  These ports appear occupied (containers running?): {busy_ports}")
    else:
        _safe_print("PASS  All target ports free.")

    # 5. Proxy reachability (should NOT be running yet, or if it is, it's fine)
    # We just note whether port 11435 is already occupied
    if _proxy_reachable():
        _safe_print("WARN  Port 11435 already in use. The driver will start its own proxy.")
    else:
        _safe_print("PASS  Proxy port 11435 free.")

    # 6. Free RAM (psutil not required; use wmic on Windows)
    try:
        r3 = subprocess.run(
            ["wmic", "OS", "get", "FreePhysicalMemory", "/Value"],
            capture_output=True, text=True, encoding=ENCODING, errors="replace", timeout=10,
        )
        m = re.search(r"FreePhysicalMemory=(\d+)", r3.stdout)
        if m:
            free_mb = int(m.group(1)) / 1024
            warn = free_mb < 1500
            _safe_print(f"{'WARN' if warn else 'PASS'}  Free RAM: {free_mb:.0f} MB"
                  + (" (< 1500 MB, may OOM during heavy LLM slots)" if warn else ""))
        else:
            _safe_print("INFO  Could not read free RAM (wmic unavailable).")
    except Exception:
        _safe_print("INFO  Could not read free RAM.")

    # 7. Free disk
    free_gb = _free_disk_gb(out_dir.parent if out_dir.exists() else Path("."))
    warn = free_gb < SAFETY_DISK_MIN_GB
    _safe_print(f"{'WARN' if warn else 'PASS'}  Free disk: {free_gb:.1f} GB"
          + (f" (< {SAFETY_DISK_MIN_GB} GB - safety stop would trigger)" if warn else ""))

    # 8. Sleep/hibernate timeouts — warn but do not run powercfg ourselves
    _safe_print("\nINFO  To prevent sleep/hibernate during the run, execute these commands")
    _safe_print("      in an elevated PowerShell before starting the driver:")
    _safe_print("        powercfg /change standby-timeout-ac 0")
    _safe_print("        powercfg /change hibernate-timeout-ac 0")
    _safe_print("      To restore defaults afterwards:")
    _safe_print("        powercfg /change standby-timeout-ac 30")
    _safe_print("        powercfg /change hibernate-timeout-ac 180")
    _safe_print("      Check current settings:")
    _safe_print("        powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE")

    _safe_print("----------------------------------------------------------------------\n")
    return ok


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage 4 driver: 20-run shuffled benchmark pass",
    )
    p.add_argument("--runs",    type=int, default=20,
                   help="Total number of runs (default: 20)")
    p.add_argument("--start-run", type=int, default=1,
                   help="First run number (default: 1; use >1 to extend an existing pass)")
    p.add_argument("--timing",  choices=("prompt", "quiet"), default="prompt",
                   help="Timing mode for SSH targets (default: prompt)")
    p.add_argument("--seed",    type=int, default=2026,
                   help="Shuffle seed (default: 2026)")
    p.add_argument("--targets", default=None,
                   help="Comma-separated target names (default: all 9 default targets)")
    p.add_argument("--out",     default="results/exp/stage4",
                   help="Output root directory (default: results/exp/stage4)")
    p.add_argument("--quiet-check-runs", type=int, default=2,
                   help="For runs 1..N also run LLM SSH targets in quiet mode "
                        "(default: 2)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the run plan and exit without connecting")
    p.add_argument("--preflight", action="store_true",
                   help="Run preflight checks and exit")
    p.add_argument("--timeout",  type=float, default=120.0,
                   help="Per-command timeout for SSH (default: 120)")
    p.add_argument("--http-timeout", type=float, default=30.0,
                   help="Per-request timeout for HTTP (default: 30)")
    p.add_argument("--targets-yaml", default="harness/targets.yaml",
                   help="Targets YAML path (default: harness/targets.yaml)")
    p.add_argument("--commands-yaml", default="harness/commands.yaml",
                   help="Commands YAML path (default: harness/commands.yaml)")
    p.add_argument("--requests-yaml", default="harness/http_requests.yaml",
                   help="HTTP requests YAML path")
    p.add_argument("--cost-cap", type=float, default=SAFETY_COST_CAP_DEFAULT,
                   help=f"Safety stop if estimated cost exceeds this USD (default: {SAFETY_COST_CAP_DEFAULT})")
    return p.parse_args(argv)


# ── Main driver ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:  # noqa: C901 (complexity OK for a driver)
    _reconfigure_stdio()
    args = parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Logging: file + stderr
    # Use errors="replace" on the stderr handler so Windows cp1252 consoles
    # don't blow up on any stray unicode in messages.
    log_path = out_dir / "driver.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding=ENCODING),
            logging.StreamHandler(sys.stderr),
        ],
    )
    log = logging.getLogger("stage4")

    if args.preflight:
        preflight(out_dir, log)
        return 0

    # Target list
    if args.targets:
        targets = [t.strip() for t in args.targets.split(",")]
        for t in targets:
            if t not in _TARGET_PORT:
                log.error("Unknown target: %r. Known: %s", t, sorted(_TARGET_PORT))
                return 1
    else:
        targets = list(DEFAULT_TARGETS)

    if args.dry_run:
        _safe_print(f"Stage 4 dry-run: runs={args.runs}, seed={args.seed}, "
              f"timing={args.timing}, targets={targets}")
        for run in range(args.start_run, args.runs + 1):
            order = shuffle_targets(targets, args.seed, run)
            for pos, t in enumerate(order):
                is_http = t in HTTP_TARGETS
                modes = ["http" if is_http else args.timing]
                if run <= args.quiet_check_runs and t in LLM_SSH_TARGETS:
                    modes.append("quiet")
                for m in modes:
                    _safe_print(f"  run={run:02d} pos={pos+1:02d} target={t} mode={m}")
        return 0

    # Run preflight automatically before the real pass
    preflight(out_dir, log)

    harness_ver = _git_head()
    log.info("Stage 4 driver starting. harness_version=%s, runs=%d, seed=%d, "
             "timing=%s, out=%s", harness_ver, args.runs, args.seed, args.timing, out_dir)

    # Subdirectories
    raw_dir   = out_dir / "raw"
    rawh_dir  = out_dir / "raw_http"
    quiet_dir = out_dir / QUIET_SUBDIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    rawh_dir.mkdir(parents=True, exist_ok=True)
    quiet_dir.mkdir(parents=True, exist_ok=True)

    manifest_path    = out_dir / "manifest.jsonl"
    status_path      = out_dir / "status.json"
    proxy_log_path   = out_dir / "api_proxy_log.jsonl"
    containers_path  = out_dir / "containers.json"

    # Load or initialize status
    status: dict[str, Any] = {}
    if status_path.exists():
        try:
            with open(status_path, encoding=ENCODING) as fh:
                status = json.load(fh)
        except Exception:
            status = {}

    # Start the proxy
    log.info("Starting api_proxy ...")
    try:
        proxy_proc = _start_proxy(proxy_log_path, log)
    except RuntimeError as exc:
        log.error("Could not start proxy: %s", exc)
        status["safety_stop"] = f"proxy_start_failed: {exc}"
        _write_json_atomic(status_path, status)
        return 2

    if not _proxy_reachable():
        log.error("Proxy not reachable after start. Aborting.")
        proxy_proc.terminate()
        status["safety_stop"] = "proxy_unreachable_after_start"
        _write_json_atomic(status_path, status)
        return 2

    log.info("Proxy running (pid=%d).", proxy_proc.pid)

    # Containers log
    containers_log: list[dict[str, Any]] = []

    # ETA tracking
    slot_durations: list[float] = []
    _interrupted = False

    def _handle_sigint(sig: int, frame: Any) -> None:
        nonlocal _interrupted
        log.warning("SIGINT received; will finish current slot and exit cleanly.")
        _interrupted = True

    signal.signal(signal.SIGINT, _handle_sigint)

    exit_code = 0
    _last_up_target: str | None = None

    try:
        for run in range(args.start_run, args.runs + 1):
            if _interrupted:
                break

            order = shuffle_targets(targets, args.seed, run)

            for pos, target in enumerate(order):
                if _interrupted:
                    break

                is_http  = target in HTTP_TARGETS
                is_llm   = target in LLM_SSH_TARGETS or target in LLM_HTTP_TARGETS
                use_proxy_overlay = is_llm

                # Determine modes to run for this slot
                modes = [args.timing if not is_http else "http"]
                if (run <= args.quiet_check_runs
                        and target in LLM_SSH_TARGETS
                        and args.timing != "quiet"):
                    modes.append("quiet")  # quiet-check run AFTER the prompt run
                def _mode_dir(mode: str) -> Path:
                    return _mode_output_dir(out_dir, target, mode)

                # Determine which modes still need to run. Each mode has its own
                # file and its own status key, so a killed quiet session never
                # hides a finished prompt session (and vice versa).
                modes_to_run: list[str] = []
                for mode in modes:
                    key = _slot_key(target, run, mode)
                    mdir = _mode_dir(mode)
                    complete = (
                        _is_complete_http(mdir, target, run) if is_http
                        else _is_complete_ssh(mdir, target, run, mode)
                    )
                    if complete and status.get(key) == "complete":
                        continue
                    path = _mode_jsonl_path(mdir, target, run)
                    if path.exists() and not complete:
                        log.info("Backing up partial slot: %s", path)
                        _backup_partial(path)
                    modes_to_run.append(mode)

                if not modes_to_run:
                    log.info("SKIP run=%d pos=%d target=%s modes=%s (complete)",
                             run, pos + 1, target, modes)
                    continue

                slot_key_primary = _slot_key(target, run, modes_to_run[0])
                slot_start = time.monotonic()
                wall_start = datetime.datetime.now(datetime.timezone.utc).isoformat()

                # ── Manifest entry ──────────────────────────────────────────
                manifest_entry = {
                    "run": run,
                    "position": pos + 1,
                    "target": target,
                    "modes": modes,
                    "modes_run": modes_to_run,
                    "resumed": modes_to_run != modes,
                    "order_seed": args.seed,
                    "planned_start_utc": wall_start,
                }
                _append_jsonl(manifest_path, manifest_entry)

                log.info("-- run=%d/%d  pos=%d/%d  target=%s  modes=%s",
                         run, args.runs, pos + 1, len(order), target, modes)

                # ── Safety checks (before starting containers) ──────────────
                cost_usd, n_calls = _estimate_cost_from_proxy_log(proxy_log_path)
                log.info("slot start: calls=%d est_cost=$%.3f cap=$%.2f",
                         n_calls, cost_usd, args.cost_cap)
                msg = _cost_stop_message(cost_usd, args.cost_cap, n_calls)
                if msg:
                    log.error("SAFETY STOP: %s", msg)
                    status["safety_stop"] = msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                free_gb = _free_disk_gb(out_dir)
                msg = _disk_stop_message(free_gb)
                if msg:
                    log.error("SAFETY STOP: %s", msg)
                    status["safety_stop"] = msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                err_rate = _recent_http_error_rate(proxy_log_path)
                msg = _error_rate_stop_message(err_rate)
                if msg:
                    log.error("SAFETY STOP: %s", msg)
                    status["safety_stop"] = msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                bad_model = _unexpected_model_seen(proxy_log_path)
                msg = _model_stop_message(bad_model)
                if msg:
                    log.error("SAFETY STOP: %s", msg)
                    status["safety_stop"] = msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                # Check proxy is still alive
                if not _proxy_reachable():
                    log.error("SAFETY STOP: proxy not reachable")
                    status["safety_stop"] = "proxy_unreachable"
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                # ── Tear down previous target ───────────────────────────────
                if _last_up_target and _last_up_target != target:
                    log.info("docker down: %s", _last_up_target)
                    _docker_down(_last_up_target, log)
                    _last_up_target = None

                # For galah: clear cache (down with volumes, then up)
                if target == "galah":
                    cache_status = _clear_galah_cache(log)
                    log.info("Galah cache clear: %s", cache_status)

                # ── Start target container ──────────────────────────────────
                log.info("docker up: %s (use_proxy=%s)", target, use_proxy_overlay)
                try:
                    _docker_up(target, log, use_proxy=use_proxy_overlay)
                    _last_up_target = target
                except RuntimeError as exc:
                    log.error("docker up failed for %s: %s", target, exc)
                    status[slot_key_primary] = "docker_up_failed"
                    _write_json_atomic(status_path, status)
                    continue

                # ── Wait for readiness ──────────────────────────────────────
                port = _TARGET_PORT[target]
                ready = _wait_port("127.0.0.1", port, _PORT_READY_TIMEOUT, log)
                if not ready:
                    log.error("Port %d not ready for %s. Skipping slot.", port, target)
                    status[slot_key_primary] = "port_not_ready"
                    _write_json_atomic(status_path, status)
                    continue

                if not is_http:
                    banner_ok = _wait_ssh_banner(
                        "127.0.0.1", port, _BANNER_CHECK_TIMEOUT, log
                    )
                    if not banner_ok:
                        log.warning("SSH banner not seen on %s:%d; continuing anyway.", target, port)

                # For galah: verify the cache volume was recreated for this slot
                if target == "galah":
                    cache_ok, cache_detail = _verify_galah_cache_empty(
                        log, datetime.datetime.fromisoformat(wall_start)
                    )
                    log.info("galah cache check: %s", cache_detail)
                    if not cache_ok:
                        log.warning("galah_logs volume does not look fresh; "
                                    "proceeding anyway")

                # ── Record image ID ─────────────────────────────────────────
                image_id = _get_image_id(target)
                container_name = _get_container_name(target)
                containers_log.append({
                    "run": run,
                    "position": pos + 1,
                    "target": target,
                    "image_id": image_id,
                    "container_name": container_name,
                    "started_utc": wall_start,
                })
                _write_json_atomic(containers_path, containers_log)

                # Execute run(s) - only the modes that are not complete yet
                slot_result: dict[str, Any] = {}
                log.info("slot modes to run: %s (planned %s)", modes_to_run, modes)

                calls_before_slot = _proxy_request_count(proxy_log_path)
                for mode in modes_to_run:
                    _write_slot_boundary(proxy_log_path, run, pos + 1, target, mode)
                    if is_http:
                        result = _run_http_slot(
                            {"name": target},
                            run, rawh_dir,
                            args.seed, pos + 1, harness_ver,
                            args.http_timeout,
                            args.targets_yaml, args.requests_yaml,
                            log,
                        )
                    else:
                        # quiet-check sessions write to raw_quiet/ so the prompt
                        # JSONL in raw/ is never overwritten (run_ssh --force
                        # copies the old file to .bak before rewriting).
                        result = _run_ssh_slot(
                            {"name": target},
                            run, _mode_dir(mode),
                            mode,
                            args.seed, pos + 1, harness_ver,
                            args.timeout,
                            args.targets_yaml, args.commands_yaml,
                            log,
                        )
                    slot_result[mode] = result
                    log.info("  mode=%s: rc=%d  cmds=%d  timeouts=%d",
                             mode, result["rc"], result["n_commands"], result["n_timeouts"])

                slot_calls = _proxy_request_count(proxy_log_path) - calls_before_slot
                msg = _slot_call_anomaly_message(target, slot_calls)
                if msg:
                    log.error("SAFETY STOP: %s", msg)
                    status["safety_stop"] = msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                primary_result = slot_result.get(modes_to_run[0], {})
                n_cmds = primary_result.get("n_commands", 0)
                n_to   = primary_result.get("n_timeouts", 0)
                stop_msg = _consec_timeout_stop(status, target, n_cmds, n_to)
                if stop_msg:
                    log.error("SAFETY STOP: %s", stop_msg)
                    status["safety_stop"] = stop_msg
                    _write_json_atomic(status_path, status)
                    exit_code = 3
                    _interrupted = True
                    break

                # ── Update status ───────────────────────────────────────────
                for mode in modes_to_run:
                    status[_slot_key(target, run, mode)] = "complete"
                _write_json_atomic(status_path, status)

                # ── ETA progress line ───────────────────────────────────────
                slot_elapsed = time.monotonic() - slot_start
                slot_durations.append(slot_elapsed)
                cost_usd, n_calls = _estimate_cost_from_proxy_log(proxy_log_path)
                avg_slot = (sum(slot_durations) / len(slot_durations))
                remaining_slots = (
                    (args.runs - run) * len(targets) + (len(order) - pos - 1)
                )
                eta_s = avg_slot * remaining_slots
                eta_str = str(datetime.timedelta(seconds=int(eta_s)))
                _safe_print(
                    f"[run {run:02d}/{args.runs} pos {pos+1:02d}/{len(order)}] "
                    f"{target:<20s} to={n_to}/{n_cmds}  "
                    f"calls={n_calls}  est_cost=${cost_usd:.3f}  "
                    f"slot={slot_elapsed:.0f}s  ETA~{eta_str}",
                    flush=True,
                )

    finally:
        log.info("Stopping proxy ...")
        proxy_proc.terminate()
        try:
            proxy_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proxy_proc.kill()

        # Tear down last target
        if _last_up_target:
            log.info("Final docker down: %s", _last_up_target)
            _docker_down(_last_up_target, log)

        _write_json_atomic(status_path, status)
        log.info("Driver exiting with code %d.", exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
