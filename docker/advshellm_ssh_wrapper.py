#!/usr/bin/env python3
"""
advshellm_ssh_wrapper.py — asyncssh SSH front-end for AdvancedshelLM.

Listens on 0.0.0.0:2222 inside the container, accepts password auth for
user "guest" / password "guest" only, and for every accepted session spawns
  python -u codebase/advancedShellm.py --provider openai --model <MODEL>
                                        --personality worker
as a child process driven via stdin/stdout pipes.

Key design points:
  - ALL child I/O is driven from the asyncio event loop using
    asyncio.subprocess (not threading.Thread + blocking reads).
    This avoids the thread-safety problem of calling asyncssh's
    process.stdout.write() from a background thread.
  - Child stdout is read in a dedicated asyncio Task and forwarded
    to the SSH channel via loop.call_soon_threadsafe is NOT needed
    because everything runs inside the event loop.
  - The child is run with python -u (unbuffered) and PYTHONUNBUFFERED=1
    so output arrives immediately without line-buffering.
  - asyncssh passes server_version verbatim to the SSH handshake but
    PREPENDS "SSH-2.0-" itself. The value must NOT include that prefix.

Environment variables (set by Docker Compose):
  MODEL          — Fireworks model ID (default: accounts/fireworks/models/glm-5p3-flash)
  SUPERVISE      — "1" to add --supervise --manager_provider openai
                   --manager_model <MANAGER_MODEL>
  MANAGER_MODEL  — manager model ID (defaults to MODEL)
  EXEC_TIMEOUT   — seconds to wait for a reply in exec mode (default: 90)
  OPENAI_API_KEY — Fireworks key (forwarded to child via environment)
  OPENAI_BASE_URL — Fireworks base URL (forwarded to child)

asyncssh version: 2.23.0 (pinned in advshellm.requirements.txt)
"""

import asyncio
import asyncssh
from asyncssh.misc import ConnectionLost as _SSHConnectionLost
import logging
import os
import re
import signal
import sys
import time
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LISTEN_HOST    = "0.0.0.0"
LISTEN_PORT    = 2222
HOST_KEY_PATH  = "/app/host_key"

# asyncssh prepends "SSH-2.0-" to this value automatically before sending
# the SSH identification string on the wire.  The value here must NOT include
# "SSH-2.0-" or the on-wire banner will be doubled.
# Confirmed: asyncssh 2.x source (common/connection.py) does:
#   version_str = 'SSH-2.0-' + (server_version or DEFAULT_LANG)
# The symptom ("SSH-2.0-SSH-2.0-..." seen by client) confirms this behaviour.
SERVER_VERSION = "OpenSSH_8.2p1 Ubuntu-4ubuntu0.3"

# One accepted credential pair for the benchmark
VALID_USER     = "guest"
VALID_PASSWORD = "guest"

# shelLM codebase directory (absolute; the Dockerfile places the app here)
CODEBASE_DIR   = "/app/codebase"
SHELLM_SCRIPT  = os.path.join(CODEBASE_DIR, "advancedShellm.py")

# Model from environment
MODEL          = os.environ.get("MODEL", "accounts/fireworks/models/glm-5p3-flash")
MANAGER_MODEL  = os.environ.get("MANAGER_MODEL", MODEL)
SUPERVISE      = os.environ.get("SUPERVISE", "0").strip() == "1"
EXEC_TIMEOUT   = float(os.environ.get("EXEC_TIMEOUT", "90"))

# Early-exit threshold: if child dies within this many seconds, log ERROR
EARLY_EXIT_THRESHOLD = 5.0

# Redaction pattern — matches Bearer tokens and api_key values in log lines
_SECRET_RE = re.compile(
    r'(Bearer\s+)[A-Za-z0-9\-_\.]+|("?api_key"?\s*[:=]\s*")[^"\s,}]+',
    re.IGNORECASE,
)

# Prompt detection: line ends with "$ ", "# ", or ">>> "
_PROMPT_RE = re.compile(r'(?:[#$]|>>>)\s*$')

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("advshellm_wrapper")


def _redact(text: str) -> str:
    """Remove Bearer tokens and api_key values from a log string."""
    return _SECRET_RE.sub(r'\1[REDACTED]', text)


def _safe_log_line(line: str) -> str:
    """Return a redacted, stripped version of a log line (max 300 chars)."""
    cleaned = _redact(line.rstrip())
    return cleaned[:300] + ("…" if len(cleaned) > 300 else "")


# ---------------------------------------------------------------------------
# Child process command builder
# ---------------------------------------------------------------------------

def _build_child_cmd() -> list:
    """Build the advancedShellm.py command list (no secrets in argv)."""
    cmd = [
        sys.executable, "-u",   # -u = unbuffered stdout/stderr
        SHELLM_SCRIPT,
        "--provider", "openai",
        "--model",    MODEL,
        "--personality", "worker",
        # Do NOT pass --cleaned (deletes logs) or --trace (leaks API key).
    ]
    if SUPERVISE:
        cmd += [
            "--supervise",
            "--manager_provider", "openai",
            "--manager_model",    MANAGER_MODEL,
        ]
    return cmd


# ---------------------------------------------------------------------------
# SSH server class (authentication only)
# ---------------------------------------------------------------------------

class _AdvSheLMServer(asyncssh.SSHServer):
    """One instance per incoming TCP connection. Handles auth only."""

    def __init__(self):
        super().__init__()
        self.session_id = str(uuid.uuid4())
        self._username  = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        peer = conn.get_extra_info("peername")
        logger.info("[%s] connection from %s", self.session_id, peer)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc:
            logger.warning("[%s] connection lost: %s", self.session_id, exc)
        else:
            logger.info("[%s] connection closed", self.session_id)

    def begin_auth(self, username: str) -> bool:
        logger.info("[%s] auth attempt username=%r", self.session_id, username)
        return True   # always require authentication

    def password_auth_supported(self) -> bool:   return True
    def public_key_auth_supported(self) -> bool: return False
    def host_based_auth_supported(self) -> bool: return False
    def kbdinit_auth_supported(self) -> bool:    return False

    def validate_password(self, username: str, password: str) -> bool:
        ok = (username == VALID_USER and password == VALID_PASSWORD)
        if ok:
            logger.info("[%s] auth SUCCESS username=%r", self.session_id, username)
            self._username = username
        else:
            logger.warning("[%s] auth FAILED username=%r", self.session_id, username)
        return ok


# ---------------------------------------------------------------------------
# Child process wrapper (asyncio-native)
# ---------------------------------------------------------------------------

class _ChildProcess:
    """
    Manages one advancedShellm.py child process using asyncio.subprocess.

    All I/O is done inside the asyncio event loop:
      - stdout is read via asyncio StreamReader (non-blocking)
      - stderr is drained by a background Task (non-blocking)
      - stdin is written with writer.write() / writer.drain() (non-blocking)

    This avoids the thread-safety issue of calling asyncssh channel methods
    from a background thread (asyncssh internals use asyncio and are not
    thread-safe).
    """

    def __init__(self, session_id: str):
        self.session_id   = session_id
        self._proc        = None          # asyncio.subprocess.Process
        self._start_time  = None
        self._stderr_lines: list[str] = []
        self._stderr_task = None
        self._first_stdout_logged = False

    async def start(self) -> None:
        cmd = _build_child_cmd()
        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"

        # Log the command (no secrets — MODEL is not a secret)
        safe_cmd = " ".join(cmd)
        logger.info("[%s] spawning child: %s  cwd=%s", self.session_id, safe_cmd, CODEBASE_DIR)

        self._start_time = time.monotonic()
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=CODEBASE_DIR,
            env=child_env,
        )
        logger.info("[%s] child pid=%d", self.session_id, self._proc.pid)

        # Drain stderr in a background task so it never blocks stdout reads
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        """Read child stderr continuously and log each line (redacted)."""
        try:
            async for raw_line in self._proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                self._stderr_lines.append(line)
                logger.warning("[%s] CHILD STDERR: %s", self.session_id, _safe_log_line(line))
        except Exception:
            pass

    async def read_chunk(self, n: int = 4096) -> bytes:
        """Read up to n bytes from child stdout (returns b'' on EOF)."""
        try:
            data = await self._proc.stdout.read(n)
        except Exception:
            data = b""

        # Log first chunk for diagnosability
        if data and not self._first_stdout_logged:
            self._first_stdout_logged = True
            preview = _redact(data[:200].decode("utf-8", errors="replace"))
            logger.info("[%s] child stdout (first 200 chars): %r", self.session_id, preview)

        return data

    async def write_stdin(self, data: bytes) -> None:
        """Write bytes to child stdin."""
        try:
            self._proc.stdin.write(data)
            await self._proc.stdin.drain()
        except Exception:
            pass

    async def send_exit(self) -> None:
        """Send 'exit' to advancedShellm.py so it closes cleanly."""
        try:
            self._proc.stdin.write(b"exit\n")
            await self._proc.stdin.drain()
        except Exception:
            pass

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def wait(self, timeout: float = 5.0) -> int:
        """Wait up to timeout seconds for the child to exit; kill if needed."""
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=3.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        return self._proc.returncode if self._proc.returncode is not None else -1

    async def terminate(self, session_id: str) -> int:
        """Gracefully terminate the child and return its exit code."""
        await self.send_exit()
        rc = await self.wait(timeout=5.0)
        elapsed = time.monotonic() - (self._start_time or 0)

        # Cancel stderr drain task
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

        logger.info(
            "[%s] child pid=%d exit_code=%d duration=%.1fs",
            session_id,
            self._proc.pid if self._proc else -1,
            rc,
            elapsed,
        )

        # Early-exit detection
        if elapsed < EARLY_EXIT_THRESHOLD:
            stderr_dump = "\n".join(self._stderr_lines[-20:])  # last 20 lines
            logger.error(
                "[%s] CHILD EXITED EARLY exit_code=%d elapsed=%.1fs stderr_tail=%r",
                session_id, rc, elapsed, _redact(stderr_dump),
            )
            # Also persist stderr to a log file for offline inspection
            _persist_child_stderr(session_id, rc, self._stderr_lines)

        return rc


def _persist_child_stderr(session_id: str, rc: int, lines: list[str]) -> None:
    """Write captured child stderr to /app/codebase/logs/wrapper_child_stderr.log."""
    log_path = "/app/codebase/logs/wrapper_child_stderr.log"
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== EARLY EXIT [{session_id}] rc={rc} ===\n")
            for line in lines:
                f.write(_redact(line) + "\n")
    except Exception as exc:
        logger.warning("[%s] could not write child stderr log: %s", session_id, exc)


# ---------------------------------------------------------------------------
# Prompt detection helper
# ---------------------------------------------------------------------------

def _has_prompt(buf: str) -> bool:
    """Return True if buf ends with a shell/REPL prompt."""
    # Strip ANSI escape sequences before checking
    stripped = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', buf)
    return bool(_PROMPT_RE.search(stripped))


# ---------------------------------------------------------------------------
# Session handler
# ---------------------------------------------------------------------------

async def _handle_session(process: asyncssh.SSHServerProcess) -> None:
    """
    Called by asyncssh for every authenticated session (interactive or exec).

    Uses asyncio.subprocess for all child I/O so that writes to the SSH
    channel (process.stdout.write) always happen inside the event loop —
    no background threads touching asyncssh objects.
    """
    session_id = str(uuid.uuid4())
    command    = process.command   # None = interactive; str = exec mode
    logger.info("[%s] session start exec=%r", session_id, command)

    child = _ChildProcess(session_id)
    exit_code = 1

    try:
        await child.start()
    except Exception as exc:
        logger.error("[%s] failed to spawn child: %s", session_id, exc)
        process.stdout.write("Connection to remote host was lost.\r\n")
        process.exit(1)
        return

    try:
        if command is not None:
            exit_code = await _run_exec_session(process, child, session_id, command)
        else:
            exit_code = await _run_interactive_session(process, child, session_id)
    finally:
        rc = await child.terminate(session_id)
        # Use the child's actual exit code if we don't have a better one
        final_code = exit_code if exit_code == 0 else (rc if rc != 0 else exit_code)
        try:
            process.exit(final_code)
        except Exception:
            pass
        logger.info("[%s] session end exit_code=%d", session_id, final_code)


async def _read_until_prompt(child: _ChildProcess, timeout: float) -> str:
    """
    Read child stdout until a prompt pattern is seen or timeout expires.
    Returns the accumulated output (decoded, \r\n not yet converted).
    """
    buf = ""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                data = await asyncio.wait_for(child.read_chunk(512), timeout=min(remaining, 0.2))
            except asyncio.TimeoutError:
                # Check if we have a prompt already in what we've accumulated
                if _has_prompt(buf):
                    break
                if not child.is_alive():
                    break
                continue

            if not data:
                break   # EOF from child
            buf += data.decode("utf-8", errors="replace")
            if _has_prompt(buf):
                # Small extra wait to catch any trailing bytes
                try:
                    extra = await asyncio.wait_for(child.read_chunk(512), timeout=0.1)
                    if extra:
                        buf += extra.decode("utf-8", errors="replace")
                except asyncio.TimeoutError:
                    pass
                break
    except Exception:
        pass
    return buf


async def _run_exec_session(
    process: asyncssh.SSHServerProcess,
    child: _ChildProcess,
    session_id: str,
    command: str,
) -> int:
    """
    Exec mode: wait for the startup banner+prompt, send one command,
    wait for the response prompt, return the output, close.
    """
    logger.info("[%s] exec mode command=%r", session_id, command)

    # Wait for startup banner and initial prompt
    banner = await _read_until_prompt(child, timeout=EXEC_TIMEOUT)
    if not banner and not child.is_alive():
        logger.warning("[%s] child died before banner in exec mode", session_id)
        return 1

    # Send the command
    await child.write_stdin((command + "\n").encode())

    # Wait for the response prompt
    response = await _read_until_prompt(child, timeout=EXEC_TIMEOUT)

    # Send output to client: combine banner + response, skip the final prompt line
    full_output = banner + response
    lines = full_output.splitlines()
    # Strip the last line if it looks like a shell prompt (don't show prompts to client)
    if lines and _PROMPT_RE.search(lines[-1]):
        lines = lines[:-1]

    output_text = "\r\n".join(lines)
    if output_text:
        process.stdout.write(output_text + "\r\n")

    return 0


# Exit commands that should close the session (case-insensitive, after strip).
_EXIT_COMMANDS = frozenset(["exit", "quit", "logout"])


async def _run_interactive_session(
    process: asyncssh.SSHServerProcess,
    child: _ChildProcess,
    session_id: str,
) -> int:
    """
    Interactive mode: bidirectional relay between SSH channel and child.

    Two concurrent tasks:
      - stdout_relay: reads child stdout and writes to SSH channel
      - stdin_relay:  reads SSH channel stdin and writes to child stdin

    Both run inside the event loop — no background threads.

    Exit handling:
      - Lines are normalized from \\r\\n / \\r to \\n before forwarding to
        the child (asyncssh PTY delivers lines ending in \\r or \\r\\n).
      - If the client sends exit/quit/logout the line is forwarded to the
        child and an exit_event is set; the stdout_relay then waits up to
        3 s for the child to quit on its own before the session closes.
      - EOF (Ctrl+D) and client disconnect also set the exit_event so the
        child is always terminated in the finally block of _handle_session.
    """

    # Signals that the session should close (exit command or client EOF/disconnect)
    exit_event = asyncio.Event()

    # Task 1: forward child stdout → SSH channel
    async def stdout_relay():
        try:
            while child.is_alive():
                # If an exit was requested, give the child up to 3 s to finish
                # writing its farewell output and then exit on its own.
                if exit_event.is_set():
                    deadline = time.monotonic() + 3.0
                    while child.is_alive() and time.monotonic() < deadline:
                        remaining = deadline - time.monotonic()
                        try:
                            data = await asyncio.wait_for(
                                child.read_chunk(512), timeout=min(remaining, 0.2)
                            )
                        except asyncio.TimeoutError:
                            continue
                        if not data:
                            break
                        text = data.decode("utf-8", errors="replace")
                        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
                        try:
                            process.stdout.write(text)
                        except Exception:
                            pass
                    break  # Close the relay regardless of child state

                try:
                    data = await asyncio.wait_for(child.read_chunk(512), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if not data:
                    break
                # Convert bare LF → CR+LF for correct terminal display
                text = data.decode("utf-8", errors="replace")
                text = text.replace("\r\n", "\n").replace("\n", "\r\n")
                try:
                    process.stdout.write(text)
                except Exception:
                    break
        except Exception:
            pass

    # Task 2: forward SSH channel stdin → child stdin
    async def stdin_relay():
        try:
            async for data in process.stdin:
                if data is None:
                    # EOF / Ctrl+D from client
                    exit_event.set()
                    break
                # Normalise line endings: \r\n or bare \r → \n
                # asyncssh PTY mode delivers lines as "cmd\r" or "cmd\r\n"
                text = data if isinstance(data, str) else data.decode("utf-8", errors="replace")
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                await child.write_stdin(text.encode("utf-8"))
                # Check whether the client just requested session close
                if text.strip().lower() in _EXIT_COMMANDS:
                    exit_event.set()
                    # Do not break immediately — let stdout_relay drain child output
        except (_SSHConnectionLost, asyncssh.BreakReceived):
            exit_event.set()
        except Exception as exc:
            logger.warning("[%s] stdin relay error: %s", session_id, exc)
            exit_event.set()

    stdout_task = asyncio.create_task(stdout_relay())
    stdin_task  = asyncio.create_task(stdin_relay())

    # Wait until either the client disconnects or the child exits
    done, pending = await asyncio.wait(
        {stdout_task, stdin_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel the other task
    for t in pending:
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass

    return 0


# ---------------------------------------------------------------------------
# Host key management
# ---------------------------------------------------------------------------

def _ensure_host_key(path: str) -> str:
    """Generate an Ed25519 host key at *path* if absent."""
    if os.path.exists(path):
        return path

    logger.info("Generating new Ed25519 host key at %s", path)
    key_dir = os.path.dirname(path)
    if key_dir:
        os.makedirs(key_dir, exist_ok=True)

    key = asyncssh.generate_private_key("ssh-ed25519")
    key.write_private_key(path)
    os.chmod(path, 0o600)
    logger.info("Host key generated.")
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main():
    host_key_path = _ensure_host_key(HOST_KEY_PATH)

    logger.info(
        "Starting AdvancedShelLM SSH wrapper on %s:%d  model=%s  supervise=%s",
        LISTEN_HOST, LISTEN_PORT, MODEL, SUPERVISE,
    )

    server = await asyncssh.listen(
        host=LISTEN_HOST,
        port=LISTEN_PORT,
        reuse_address=True,
        server_factory=_AdvSheLMServer,
        server_host_keys=[host_key_path],
        # asyncssh prepends "SSH-2.0-" automatically; do NOT include it here.
        server_version=SERVER_VERSION,
        process_factory=_handle_session,
        x11_forwarding=False,
        agent_forwarding=False,
        # No sftp_factory → asyncssh refuses SFTP subsystem requests.
    )

    logger.info("SSH server listening — waiting for connections")

    async with server:
        await server.wait_closed()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, loop.stop)

    try:
        loop.run_until_complete(_main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
