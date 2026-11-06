#!/usr/bin/env python3
"""
harness/run_ssh.py
Scripted SSH benchmark attacker using Paramiko.

Usage:
    python harness/run_ssh.py [options]

Options:
    --targets   Path to targets.yaml   (default: harness/targets.yaml)
    --commands  Path to commands.yaml  (default: harness/commands.yaml)
    --runs      Number of runs per target (default: 5)
    --out       Output directory        (default: results/raw)
    --timeout   Per-command timeout in seconds (default: 90)
    --dry-run   Validate YAML only, do not connect
    --target    Comma-separated target names to run (default: all ssh targets)
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import select
import socket
import sys
import time
import traceback
import shutil
import tempfile
from pathlib import Path
from typing import Any

import paramiko
import yaml

try:
    csv.field_size_limit(2**31 - 1)
except OverflowError:
    csv.field_size_limit(2**30)

# ── Constants ────────────────────────────────────────────────────────────────

BANNER_TIMEOUT = 60       # seconds to wait for initial SSH banner
AUTH_TIMEOUT   = 60       # seconds to wait for auth to complete
QUIET_PERIOD   = 0.5      # seconds of silence before a prompt is confirmed
EXIT_WAIT      = 10       # seconds to wait for server to close channel after exit
RECV_CHUNK     = 4096     # bytes per recv() call
ENCODING       = "utf-8"
ENCODING_ERRORS = "replace"

# Trap markers used by the llm-honeypot detector target.
# The harness NEVER follows these instructions.
TRAP_MARKERS = [
    "Filesystem locked",
    "Identity service locked",
    "Process manager locked",
    "System not initialized",
    "Disk subsystem offline",
]

# Recovery commands the harness must NEVER send (safety rule).
_FORBIDDEN_COMMANDS = {
    "fsck-repair", "sysctl-recovery", "server-init",
    "id-service", "disk-recover", "cat8193",
}

# ── ANSI / escape-code stripping ─────────────────────────────────────────────

# Matches real ANSI escape sequences: ESC [ ... m  (and other final bytes)
_REAL_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]|\x1b\[[0-9;]*m')

# Matches LITERAL backslash-escape text as printed by some LLMs:
#   \x1b[01;32m   \u001b[0m   \033[1;34m
_LIT_ANSI_RE = re.compile(
    r'(?:\\x1b|\\u001b|\\033)\[[0-9;]*[A-Za-z]'
)

def _strip_ansi(text: str) -> str:
    """Remove both real ANSI escape sequences and literal escape text."""
    text = _REAL_ANSI_RE.sub('', text)
    text = _LIT_ANSI_RE.sub('', text)
    return text

def _has_literal_escape(text: str) -> bool:
    """Return True if the text contains literal escape-code strings."""
    return bool(_LIT_ANSI_RE.search(text))

# ── Prompt detection ─────────────────────────────────────────────────────────

# Matches a shell prompt on the last non-empty line after stripping ANSI.
#   user@host:path$   user@host:path#   user@host:/some/dir$
_PROMPT_RE = re.compile(r'^[^\s@]+@[^\s:]+:[^\n]*[\$#]\s*$', re.MULTILINE)
# Fallback: any line ending with $ or # (possibly preceded by space)
_PROMPT_FALLBACK_RE = re.compile(r'[\$#]\s*$', re.MULTILINE)

def _detect_prompt(text: str) -> str | None:
    """
    Return the matched prompt string if a shell prompt is detected in *text*,
    else None.  The text is stripped of ANSI before matching.
    """
    clean = _strip_ansi(text)
    # Look at the last non-empty line only
    lines = [l for l in clean.splitlines() if l.strip()]
    if not lines:
        return None
    last = lines[-1].rstrip()
    if _PROMPT_RE.match(last):
        return last
    if _PROMPT_FALLBACK_RE.search(last):
        return last
    return None

# ── Output cleaning ──────────────────────────────────────────────────────────

def _clean_output(raw: str, command_text: str, prompt: str | None) -> str:
    """
    Return the cleaned output of a command:
    - Strip real ANSI sequences and literal escape text
    - Remove the echoed command (first line if it matches)
    - Remove the final prompt line
    - Convert CRLF to LF
    """
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    text = _strip_ansi(text)
    lines = text.split('\n')

    # Remove echoed command (shell PTY typically echoes it back)
    if lines and lines[0].strip() == command_text.strip():
        lines = lines[1:]

    # Remove final prompt line
    if lines and prompt and lines[-1].rstrip() == prompt.rstrip():
        lines = lines[:-1]
    elif lines:
        # Try stripping any trailing prompt-like line even if prompt string differs
        last = lines[-1].rstrip()
        if _PROMPT_RE.match(last) or _PROMPT_FALLBACK_RE.search(last):
            lines = lines[:-1]

    # Strip leading/trailing blank lines
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]

    return '\n'.join(lines)

# ── Transport fingerprint ─────────────────────────────────────────────────────

def _transport_fingerprint(transport: paramiko.Transport) -> dict[str, Any]:
    """Extract connection metadata from a Paramiko Transport."""
    host_key = transport.get_remote_server_key()

    # local_cipher / local_mac are set after key exchange negotiation.
    # They may not exist on all Paramiko versions; fall back gracefully.
    cipher = getattr(transport, "local_cipher", None) or None
    mac    = getattr(transport, "local_mac", None) or None

    return {
        "remote_version":    transport.remote_version,
        "cipher":            cipher,
        "mac":               mac,
        "host_key_type":     host_key.get_name() if host_key else None,
        "host_key_fingerprint": (
            hashlib.md5(host_key.asbytes()).hexdigest() if host_key else None
        ),
        "auth_methods":      None,  # not populated here; informational field
    }

# ── Banner / initial-prompt reader ───────────────────────────────────────────

def _read_until_prompt(
    chan: paramiko.Channel,
    timeout: float,
    quiet: float = QUIET_PERIOD,
) -> tuple[str, str | None]:
    """
    Read from *chan* until a shell prompt is detected followed by *quiet* seconds
    of silence, or *timeout* seconds total.

    Returns (raw_data, prompt_string_or_None).
    """
    buf = ""
    last_recv_time = time.monotonic()
    deadline = time.monotonic() + timeout
    last_prompt: str | None = None
    last_prompt_time: float | None = None

    chan.settimeout(0.0)  # non-blocking

    while True:
        now = time.monotonic()
        if now > deadline:
            break

        try:
            chunk = chan.recv(RECV_CHUNK)
        except socket.timeout:
            chunk = b""
        except (EOFError, paramiko.SSHException):
            raise
        except Exception:
            raise

        if chunk:
            buf += chunk.decode(ENCODING, ENCODING_ERRORS)
            last_recv_time = now
            candidate = _detect_prompt(buf)
            if candidate:
                last_prompt = candidate
                last_prompt_time = now
        else:
            # No data; check quiet period
            if last_prompt_time is not None:
                if (now - last_prompt_time) >= quiet:
                    break
            # Avoid tight spin
            remaining = min(deadline - now, quiet)
            if remaining > 0:
                try:
                    select.select([chan], [], [], min(0.1, remaining))
                except (EOFError, paramiko.SSHException):
                    raise
                except Exception:
                    raise

    return buf, last_prompt

# ── SSH "none" authentication ─────────────────────────────────────────────────

def _auth_none(transport: paramiko.Transport, username: str) -> bool:
    """
    Attempt SSH 'none' authentication via Transport.auth_none().
    Returns True if the server accepted it (no further auth required).
    RFC 4252 §5.2: the server may return a list of allowed methods or accept.
    """
    try:
        remaining = transport.auth_none(username)
        # auth_none returns a list of remaining auth methods.
        # If the list is empty, auth succeeded.
        return len(remaining) == 0
    except paramiko.AuthenticationException:
        return False
    except (EOFError, paramiko.SSHException):
        raise
    except Exception:
        raise

def _failure_meta(run_meta: dict[str, Any], exc: BaseException, stage: str) -> None:
    """Store a non-empty, typed failure description and its traceback."""
    run_meta["connection_error"] = (
        f"{type(exc).__name__}: {exc!r}"
    )
    run_meta["error_stage"] = stage
    run_meta["exception_type"] = type(exc).__name__
    run_meta["error_message"] = repr(exc)
    run_meta["error_traceback"] = traceback.format_exc()

def _error_record(
    target: dict[str, Any],
    run_index: int,
    run_meta: dict[str, Any],
) -> dict[str, Any]:
    """Create a JSONL record when a run fails before a command result exists."""
    return {
        "target": target["name"],
        "run": run_index,
        "cmd_id": "",
        "text": "",
        "raw_output": "",
        "cleaned_output": "",
        "latency_s": 0.0,
        "timed_out": False,
        "bytes": 0,
        "prompt": None,
        "literal_escape_text_present": False,
        "trap_markers_found": [],
        "error": run_meta.get("connection_error", "unknown run failure"),
        "error_stage": run_meta.get("error_stage", "unknown"),
        "exception_type": run_meta.get("exception_type", "UnknownError"),
        "error_message": run_meta.get("error_message", "unknown run failure"),
    }

# ── Single run ────────────────────────────────────────────────────────────────

def _run_once(
    target: dict[str, Any],
    commands: list[dict[str, Any]],
    run_index: int,
    timeout: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """
    Connect to *target*, execute all commands, disconnect.

    Returns:
        (command_results, fingerprint, run_meta)
    run_meta has keys: auth_method_used, connection_error, banner_raw.
    """
    host     = target["host"]
    port     = int(target["port"])
    username = target["username"]
    password = target.get("password", "")
    auth_pref = target.get("auth", "password")
    kind      = target.get("kind", "llm")

    run_meta: dict[str, Any] = {
        "auth_method_used": None,
        "connection_error":  None,
        "banner_raw":        None,
        "error_stage":       None,
        "exception_type":    None,
        "error_message":     None,
        "error_traceback":   None,
    }
    fingerprint: dict[str, Any] = {}
    results: list[dict[str, Any]] = []

    # ── Connect ──────────────────────────────────────────────────────────────
    try:
        sock = socket.create_connection((host, port), timeout=BANNER_TIMEOUT)
        transport = paramiko.Transport(sock)
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "connect")
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "connect")
        return results, fingerprint, run_meta
    transport.banner_timeout   = BANNER_TIMEOUT
    transport.auth_timeout     = AUTH_TIMEOUT
    transport.set_log_channel("paramiko.transport")

    try:
        transport.start_client(timeout=BANNER_TIMEOUT)
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "connect")
        run_meta["connection_error"] = f"connect: {run_meta['connection_error']}"
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "connect")
        run_meta["connection_error"] = f"connect: {run_meta['connection_error']}"
        transport.close()
        sock.close()
        return results, fingerprint, run_meta

    try:
        fingerprint = _transport_fingerprint(transport)
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "connect")
        transport.close()
        sock.close()
        return results, fingerprint, run_meta

    # ── Authenticate ─────────────────────────────────────────────────────────
    authed = False
    if auth_pref == "none":
        try:
            authed = _auth_none(transport, username)
        except (EOFError, paramiko.SSHException) as exc:
            _failure_meta(run_meta, exc, "authenticate")
        except Exception as exc:
            _failure_meta(run_meta, exc, "authenticate")
        if authed:
            run_meta["auth_method_used"] = "none"
        else:
            # Fallback: empty password
            try:
                transport.auth_password(username, "", fallback=False)
                run_meta["auth_method_used"] = "password_empty"
                authed = True
            except paramiko.AuthenticationException:
                pass
            except (EOFError, paramiko.SSHException) as exc:
                _failure_meta(run_meta, exc, "authenticate")
            except Exception as exc:
                _failure_meta(run_meta, exc, "authenticate")
            if authed:
                run_meta["connection_error"] = None
    else:
        try:
            transport.auth_password(username, password, fallback=False)
            run_meta["auth_method_used"] = "password"
            authed = True
        except paramiko.AuthenticationException as exc:
            _failure_meta(run_meta, exc, "authenticate")
            run_meta["connection_error"] = f"authenticate: {run_meta['connection_error']}"
        except (EOFError, paramiko.SSHException) as exc:
            _failure_meta(run_meta, exc, "authenticate")
        except Exception as exc:
            _failure_meta(run_meta, exc, "authenticate")

    if not authed:
        if run_meta["connection_error"] is None:
            run_meta["connection_error"] = "authentication failed"
            run_meta["error_stage"] = "authenticate"
            run_meta["exception_type"] = "AuthenticationException"
            run_meta["error_message"] = "authentication failed"
            run_meta["error_traceback"] = ""
        transport.close()
        sock.close()
        return results, fingerprint, run_meta

    # ── Open interactive shell ────────────────────────────────────────────────
    try:
        chan = transport.open_session()
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "open_session")
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "open_session")
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    try:
        chan.get_pty(term="xterm", width=220, height=50)
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "get_pty")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "get_pty")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    try:
        chan.invoke_shell()
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "invoke_shell")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "invoke_shell")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta

    # Read login banner / initial prompt
    try:
        banner_raw, initial_prompt = _read_until_prompt(chan, timeout=timeout)
    except (EOFError, paramiko.SSHException) as exc:
        _failure_meta(run_meta, exc, "read_banner")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    except Exception as exc:
        _failure_meta(run_meta, exc, "read_banner")
        chan.close()
        transport.close()
        sock.close()
        return results, fingerprint, run_meta
    run_meta["banner_raw"] = banner_raw

    current_prompt = initial_prompt

    # ── Send commands one at a time ──────────────────────────────────────────
    for cmd in commands:
        cmd_id    = cmd["id"]
        cmd_text  = cmd["text"]
        is_exit   = (cmd_id == "exit")

        # Safety: refuse forbidden commands unconditionally
        if any(f in cmd_text for f in _FORBIDDEN_COMMANDS):
            results.append({
                "target":   target["name"],
                "run":      run_index,
                "cmd_id":   cmd_id,
                "text":     cmd_text,
                "raw_output":     "",
                "cleaned_output": "",
                "latency_s":      0.0,
                "timed_out":      False,
                "bytes":          0,
                "prompt":         None,
                "literal_escape_text_present": False,
                "trap_markers_found": [],
                "error": "FORBIDDEN command skipped",
            })
            continue

        t_send = time.monotonic()
        chan.sendall((cmd_text + "\n").encode(ENCODING))

        if is_exit:
            # Special handling: wait for channel close or timeout
            exit_closed = False
            exit_status = None
            deadline = time.monotonic() + EXIT_WAIT
            exit_buf = ""
            while time.monotonic() < deadline:
                try:
                    chunk = chan.recv(RECV_CHUNK)
                    if chunk:
                        exit_buf += chunk.decode(ENCODING, ENCODING_ERRORS)
                    else:
                        # EOF from server
                        exit_closed = True
                        break
                except socket.timeout:
                    pass
                except Exception:
                    exit_closed = True
                    break
                if chan.exit_status_ready():
                    exit_status = chan.recv_exit_status()
                    exit_closed = True
                    break
                time.sleep(0.05)

            latency = time.monotonic() - t_send
            results.append({
                "target":   target["name"],
                "run":      run_index,
                "cmd_id":   cmd_id,
                "text":     cmd_text,
                "raw_output":     exit_buf,
                "cleaned_output": "",
                "latency_s":      round(latency, 3),
                "timed_out":      not exit_closed,
                "bytes":          len(exit_buf),
                "prompt":         None,
                "literal_escape_text_present": _has_literal_escape(exit_buf),
                "trap_markers_found": (
                    [m for m in TRAP_MARKERS if m in exit_buf]
                    if kind == "detector" else []
                ),
                "exit_closes_session": exit_closed,
                "exit_status": exit_status,
            })
            break  # no more commands after exit

        # Normal command: read until prompt or timeout
        raw_buf = ""
        timed_out = False
        deadline_abs = time.monotonic() + timeout
        last_recv = time.monotonic()
        prompt_found: str | None = None
        prompt_found_at: float | None = None
        chan.settimeout(0.0)

        while True:
            now = time.monotonic()
            if now > deadline_abs:
                timed_out = True
                break

            try:
                chunk = chan.recv(RECV_CHUNK)
            except socket.timeout:
                chunk = b""
            except Exception:
                timed_out = True
                break

            if chunk:
                raw_buf += chunk.decode(ENCODING, ENCODING_ERRORS)
                last_recv = now
                candidate = _detect_prompt(raw_buf)
                if candidate:
                    prompt_found = candidate
                    prompt_found_at = now
            else:
                if prompt_found_at is not None:
                    if (now - prompt_found_at) >= QUIET_PERIOD:
                        break
                remaining = min(deadline_abs - now, QUIET_PERIOD)
                if remaining > 0:
                    try:
                        select.select([chan], [], [], min(0.1, remaining))
                    except Exception:
                        pass

        latency = time.monotonic() - t_send
        current_prompt = prompt_found or current_prompt

        cleaned = _clean_output(raw_buf, cmd_text, prompt_found)

        results.append({
            "target":   target["name"],
            "run":      run_index,
            "cmd_id":   cmd_id,
            "text":     cmd_text,
            "raw_output":     raw_buf,
            "cleaned_output": cleaned,
            "latency_s":      round(latency, 3),
            "timed_out":      timed_out,
            "bytes":          len(raw_buf),
            "prompt":         prompt_found,
            "literal_escape_text_present": _has_literal_escape(raw_buf),
            "trap_markers_found": (
                [m for m in TRAP_MARKERS if m in raw_buf]
                if kind == "detector" else []
            ),
        })

    # ── Teardown ─────────────────────────────────────────────────────────────
    try:
        chan.close()
    except Exception:
        pass
    try:
        transport.close()
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass

    return results, fingerprint, run_meta


# ── Output helpers ────────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "target", "run", "cmd_id", "text", "category", "host_specific",
    "cleaned_output", "latency_s", "timed_out", "bytes",
    "prompt", "literal_escape_text_present", "trap_markers_found", "error",
]

def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=ENCODING) as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _append_error_log(
    path: Path,
    target: str,
    run_index: int,
    run_meta: dict[str, Any],
) -> None:
    """Append the complete traceback for a failed target run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding=ENCODING) as fh:
        fh.write(
            f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] "
            f"target={target} run={run_index} "
            f"stage={run_meta.get('error_stage', 'unknown')} "
            f"type={run_meta.get('exception_type', 'UnknownError')} "
            f"message={run_meta.get('error_message', 'unknown run failure')}\n"
        )
        fh.write(run_meta.get("error_traceback") or "No traceback captured.\n")
        if not (run_meta.get("error_traceback") or "").endswith("\n"):
            fh.write("\n")

def _append_csv(path: Path, rows: list[dict[str, Any]],
                cmd_map: dict[str, dict[str, Any]]) -> None:
    write_header = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding=ENCODING) as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for row in rows:
            extra = cmd_map.get(row.get("cmd_id", ""), {})
            row_out = dict(row)
            row_out["category"]      = extra.get("category", "")
            row_out["host_specific"] = extra.get("host_specific", "")
            row_out["trap_markers_found"] = json.dumps(
                row_out.get("trap_markers_found", [])
            )
            row_out.setdefault("error", "")
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

# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SSH benchmark harness")
    p.add_argument("--targets",  default="harness/targets.yaml",
                   help="Target config path, or comma-separated target names")
    p.add_argument("--commands", default="harness/commands.yaml")
    p.add_argument("--runs",     type=int, default=5)
    p.add_argument("--out",      default="results/raw")
    p.add_argument("--timeout",  type=float, default=90.0)
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--force", action="store_true",
                   help="Back up and rerun already-complete target/run pairs")
    p.add_argument(
        "--target",
        default=None,
        help="Comma-separated target names (default: all SSH targets)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Load YAML
    targets_path = Path(args.targets) if Path(args.targets).is_file() else Path("harness/targets.yaml")
    with open(targets_path, encoding=ENCODING) as fh:
        targets_data = yaml.safe_load(fh)
    with open(args.commands, encoding=ENCODING) as fh:
        commands_data = yaml.safe_load(fh)

    all_targets  = targets_data.get("targets", [])
    all_commands = commands_data.get("commands", [])

    # Build command lookup map
    cmd_map = {c["id"]: c for c in all_commands}

    # Filter to SSH targets
    ssh_targets = [t for t in all_targets if t.get("track") == "ssh"]
    selection = args.target
    if selection is None and not Path(args.targets).is_file():
        selection = args.targets
    if selection:
        requested = {n.strip() for n in selection.split(",")}
        ssh_targets = [t for t in ssh_targets if t["name"] in requested]

    if not ssh_targets:
        print("No SSH targets selected.", file=sys.stderr)
        return 1

    # Validate: no forbidden commands
    for cmd in all_commands:
        if any(f in cmd["text"] for f in _FORBIDDEN_COMMANDS):
            print(
                f"ERROR: command '{cmd['id']}' contains a forbidden string.",
                file=sys.stderr,
            )
            return 1

    if args.dry_run:
        print("Dry-run: YAML validated OK")
        print(f"  SSH targets : {[t['name'] for t in ssh_targets]}")
        print(f"  Commands    : {len(all_commands)}")
        print(f"  Runs        : {args.runs}")
        return 0

    out_dir    = Path(args.out)
    csv_path   = Path("results") / "ssh_commands_long.csv"
    errors_path = Path("results") / "errors.log"
    fp_path    = Path("results") / "ssh_fingerprints.json"
    fingerprints: dict[str, Any] = {}

    # Suppress Paramiko logging noise
    import logging
    logging.getLogger("paramiko").setLevel(logging.WARNING)

    planned: list[tuple[str, int, str]] = []
    expected_records = len(all_commands)
    for target in ssh_targets:
        for run_idx in range(1, args.runs + 1):
            pair = out_dir / f"{target['name']}_run{run_idx:02d}.jsonl"
            complete = pair.exists() and sum(
                1 for _ in pair.open(encoding=ENCODING)
            ) == expected_records
            planned.append((target["name"], run_idx, "run" if args.force or not complete else "skip"))
    print("Plan: " + ", ".join(f"{name}/run{run:02d}={action}"
                               for name, run, action in planned))

    for target in ssh_targets:
        tname = target["name"]
        print(f"\n=== Target: {tname} ===")
        target_fps = []

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

            try:
                cmd_results, fp, run_meta = _run_once(
                    target, all_commands, run_idx, args.timeout
                )
            except Exception as exc:
                _failure_meta(run_meta := {}, exc, "run")
                cmd_results = []
                fp = {}
            if run_meta.get("connection_error"):
                print(
                    f"ERROR: {run_meta.get('error_stage', 'run')} "
                    f"{run_meta['connection_error']}"
                )
                _append_error_log(errors_path, tname, run_idx, run_meta)

            elapsed = time.monotonic() - t0
            n_cmds  = len(cmd_results)
            n_to    = sum(1 for r in cmd_results if r.get("timed_out"))
            err     = run_meta.get("connection_error")
            print(
                f"done ({elapsed:.1f}s, {n_cmds} cmds, {n_to} timeouts"
                + (f", ERR: {err}" if err else "") + ")"
            )

            # Write JSONL
            records_for_jsonl = []
            for r in cmd_results:
                rec = dict(r)
                extra = cmd_map.get(rec.get("cmd_id", ""), {})
                rec["category"]      = extra.get("category", "")
                rec["host_specific"] = extra.get("host_specific", False)
                rec["run_meta"]      = run_meta
                records_for_jsonl.append(rec)
            if not records_for_jsonl and run_meta.get("connection_error"):
                records_for_jsonl.append(_error_record(target, run_idx, run_meta))
            _write_jsonl(jsonl_path, records_for_jsonl)

            # Append CSV
            _append_csv(csv_path, cmd_results, cmd_map)

            # Collect fingerprint
            fp_entry = dict(fp)
            fp_entry["run"]              = run_idx
            fp_entry["auth_method_used"] = run_meta.get("auth_method_used")
            fp_entry["connection_error"] = run_meta.get("connection_error")
            target_fps.append(fp_entry)

        fingerprints[tname] = target_fps

    # Write fingerprints JSON
    fp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(fp_path, "w", encoding=ENCODING) as fh:
        json.dump(fingerprints, fh, indent=2, ensure_ascii=False)

    print(f"\nDone. CSV: {csv_path}  Fingerprints: {fp_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
