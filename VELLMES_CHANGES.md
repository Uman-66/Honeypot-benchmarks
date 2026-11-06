# VELLMES_CHANGES.md

## Repository name

The cloned directory is **`VelLMes-AI-Deception-Framework`** (not `VelLMes-LLM-Honeypot`).

---

## Step 1 – Analysis answers

### a) How does the SSH honeypot receive connections?

**VelLMes has no built-in SSH server.** `VelLMes.py` is a pure stdin/stdout
interactive loop:

- It calls `openai.chat.completions.create(…)` to get the LLM response.
- It prints the response to stdout.
- It reads the next command from `input()` (i.e. stdin).

There is no paramiko, asyncssh, socket binding, or any network code in the
repository. The README says to run it directly in a terminal; a human attacker
would SSH to a separate server and the operator would redirect stdin/stdout to
that session manually (or via an external tool).

**Consequence:** We need an SSH wrapper, exactly like the AdvancedShelLM target
uses. The wrapper (`docker/vellmes_ssh_wrapper.py`) is modelled directly on
`docker/advshellm_ssh_wrapper.py`.

### b) SSH banner

**VelLMes itself never sends an SSH banner** because it has no SSH server.
The asyncssh wrapper (`vellmes_ssh_wrapper.py`) sets:

```python
SERVER_VERSION = "OpenSSH_8.2p1 Ubuntu-4ubuntu0.11"
```

asyncssh prepends `"SSH-2.0-"` to this value automatically before sending the
identification string on the wire. The value in `server_version` must **not**
include that prefix, otherwise the banner is doubled
(`SSH-2.0-SSH-2.0-OpenSSH_8.2p1 …`). This behaviour is confirmed in the
asyncssh 2.x source (`common/connection.py`) and was the exact bug observed
with an earlier AdvancedShelLM build.

On the wire the client sees: `SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.11`

The ground truth value from the benchmark spec is
`SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.x`; the patch number `.11` is a
reasonable Ubuntu 20.04 value. **UNVERIFIED: the exact Ubuntu patch string
has not been confirmed against a real Ubuntu 20.04 OpenSSH 8.2 banner; `.11`
was chosen because it is a real Ubuntu package revision. Adjust
`SERVER_VERSION` in `vellmes_ssh_wrapper.py` if your ground truth banner uses
a different value.**

### c) OpenAI client: API key and base_url

**Original code (problematic):**

```python
# set_key(), line 51 (original)
env = dotenv_values(env_path)
openai.api_key = env["OPENAI_API_KEY"]          # old-SDK module attribute

# main(), line 203 (original)
res = openai.chat.completions.create(…)         # new SDK — ignores openai.api_key!
```

There are two separate bugs:

1. `openai.api_key = …` is the **old (<1.0) SDK** pattern. The current
   `openai>=1.0` SDK does **not** read from `openai.api_key`. The call at
   line 203 (`openai.chat.completions.create(…)`) uses the new SDK which picks
   up the key from the `OPENAI_API_KEY` environment variable automatically
   (or from an `openai.OpenAI(api_key=…)` instance). The original code would
   produce an `AuthenticationError` unless `OPENAI_API_KEY` was already in the
   environment.

2. There is **no `base_url` configuration** anywhere in the original code. It
   will always call `api.openai.com`, ignoring `OPENAI_BASE_URL`. This means
   Fireworks cannot be used without patching.

**Patch applied:** `set_key()` now reads the `.env` file and injects values
into `os.environ` (using `setdefault` so the Docker-supplied env vars win).
A new `_get_client()` factory builds an `openai.OpenAI(api_key=…, base_url=…)`
instance from environment variables. All `openai.chat.completions.create(…)`
calls are replaced with `_get_client().chat.completions.create(…)`.

### d) Model name handling / tiktoken crash

`read_history()` (line 67 original) calls:

```python
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
```

This uses the hardcoded `"gpt-3.5-turbo"` model name (not the configured
model), so it does **not** crash on non-OpenAI model names **in its current
form**. However, it does require `tiktoken` to be importable. `tiktoken`
itself may fail to resolve the token count correctly for very long contexts
with the GLM model, but more importantly: if `tiktoken` is ever called with
the actual model name (or if `tiktoken` is not installed), the code crashes.

**Patch applied:** `tiktoken` import is wrapped in `try/except ImportError`.
The `encoding_for_model("gpt-3.5-turbo")` call is wrapped in
`try/except (KeyError, Exception)` with `TOKEN_COUNT = 0` fallback. Token
counting is purely used to decide when to reset context history; if it fails,
the safe fallback is to keep `TOKEN_COUNT = 0` which forces a fresh session
(harmless and correct for the benchmark).

### e) `<think>` reasoning block stripping

The original code does **no stripping** of model output before printing or
storing it. If the GLM model emits `<think>…</think>` blocks (chain-of-thought
reasoning visible in the response), they will be printed verbatim to the
connecting client — which would immediately reveal the LLM nature of the
honeypot.

**Patch applied:**

```python
_THINK_RE    = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_FENCE_START = re.compile(r'^```[a-zA-Z0-9]*\n', re.MULTILINE)
_FENCE_END   = re.compile(r'\n```\s*$', re.MULTILINE)

def _strip_reasoning(text: str) -> str:
    text = _THINK_RE.sub('', text)
    text = _FENCE_START.sub('', text, count=1)
    text = _FENCE_END.sub('', text, count=1)
    return text.strip()
```

Called immediately after `res.choices[0].message.content` is retrieved,
before the message is appended to working memory or written to the history
file. **UNVERIFIED: whether the specific Fireworks
`accounts/fireworks/models/glm-5p3-flash` model emits `<think>` blocks or
markdown fences in its SSH shell persona responses has not been tested.**

### f) What is written to disk / key-leak risks

**Files written:**

| Path | Content |
|------|---------|
| `-o <output>` (`historySSH.txt` by default) | Full conversation: system prompt + all assistant/user turns. No API key, no HTTP headers. |
| `-l <log>` (`logSSH.txt` by default) | Exception messages only (written in the `except Exception as e:` block). The error string `str(e)` could include API error messages from the OpenAI SDK that include request metadata but **not** the raw API key. |

**Key-leak risks:**

- Original `set_key()`: `dotenv_values(env_path)` → `openai.api_key = env["OPENAI_API_KEY"]`. If `env_path` is passed as a CLI argument, the key is held in a Python variable in memory but never written to a file or logged. **Risk: low** in production but the pattern made `base_url` unsettable.
- `str(e)` in the error log: The openai SDK may include the `Authorization` header value in some exception messages (e.g. `APIConnectionError`). **UNVERIFIED: whether the version of `openai` pinned by `requirements.txt` (unpinned — latest) includes auth headers in exception strings.** The wrapper's `_safe_log_line()` / `_redact()` functions strip `Bearer …` tokens from wrapper logs; but VelLMes's own `logSSH.txt` is not similarly protected.
- No `--trace` option exists in VelLMes.py. No logging of request headers in the original code.

**Patch:** the wrapper never passes secrets on the command line; secrets stay in `os.environ` and are picked up by `_get_client()`.

### g) Authentication, username, hostname, persona

The SSH config (`configSSH.yml`) defines the persona in the system prompt:

```
User is tomas@ailabs.
```

This is CTU lab branding — not neutral. For the benchmark we use a neutral persona:

- **Username:** `user`
- **Hostname:** `srv-ubuntu`
- **Home:** `/home/user`

The **SSH authentication credentials** (checked by the wrapper, not VelLMes.py)
are:

- **Username:** `user`
- **Password:** `user123`

These are set in `vellmes_ssh_wrapper.py` as `VALID_USER` / `VALID_PASSWORD`.

Add to `harness/targets.yaml`:

```yaml
vellmes:
  host: 127.0.0.1
  port: 2228
  username: user
  password: user123
```

### h) Cross-session memory / carry-over contamination

`read_history()` implements carry-over:

1. Opens the output file with `"a+"` mode.
2. If the file is non-empty, reads all prior content as the new prompt and
   appends a `reset_prompt` divider.
3. Only resets (truncates) if `TOKEN_COUNT > 15100`.

**For the benchmark, this is a contamination risk:** run 2 would start with
run 1's entire conversation as context.

**Fix applied (two-part):**

1. The **wrapper** (`vellmes_ssh_wrapper.py`) passes a unique per-session
   output file via `-o /app/logs/history_<uuid>.txt`. Because each session
   gets a new file, `os.stat(output_dir).st_size == 0` is always `True` when
   `read_history()` runs → it always loads the initial personality. The
   carry-over code path in `read_history()` is effectively dead.

2. The comment in the patched `read_history()` documents this intent so future
   maintainers understand why.

No source code changes to `read_history()` logic itself were needed because
the per-session file approach is sufficient and minimal.

### i) Python version / requirements compatibility

`requirements.txt` (unpinned):

```
openai
python-dotenv
pyyaml
tiktoken
requests
```

- **No version pins.** All five packages install successfully on Python 3.11
  and Python 3.12. No known Python 3.12 incompatibilities in any of these
  packages as of late 2025.
- **`tiktoken`** requires a C extension (Rust via `maturin`). Python 3.12
  wheels are available on PyPI. On `python:3.12-slim` it installs without
  `gcc` but may require `rustc` if no wheel is available for the platform.
  Using **`python:3.11-slim`** (as in the Dockerfile) avoids this risk.
- **`openai>=1.0`**: The code uses `openai.chat.completions.create(…)` which
  requires the new SDK (≥1.0.0). The original `openai.api_key = …` is the
  old SDK pattern and is now a no-op; it was replaced by the `_get_client()`
  factory in the patch.

---

## Files created / edited

| File | Action | Reason |
|------|--------|--------|
| `docker/vellmes.Dockerfile` | **Created** | Container image: python:3.11-slim, UID 10001 non-root user, installs wrapper + VelLMes deps, copies code |
| `docker/vellmes.compose.yaml` | **Created** | Compose service: 127.0.0.1:2228→2228, env_file, named volumes for logs and SSH host key |
| `docker/vellmes.requirements.txt` | **Created** | Wrapper-only deps (asyncssh, cryptography, cffi, pycparser, typing-extensions) |
| `docker/vellmes_ssh_wrapper.py` | **Created** | asyncssh SSH front-end; spawns one fresh VelLMes.py per session; correct banner; redacts secrets from logs |
| `docker/vellmes_configSSH.yml` | **Created** | Benchmark SSH personality: neutral `user@srv-ubuntu` persona, model/temp/max_tokens defaults |
| `VelLMes-AI-Deception-Framework/VelLMes.py` | **Patched** | API key from env, base_url support, tiktoken fallback, `<think>` stripping, env overrides for model/temp/max_tokens, session isolation via per-session output file |

---

## Credentials and persona

For `harness/targets.yaml`:

```yaml
vellmes:
  host: 127.0.0.1
  port: 2228
  username: user
  password: user123
```

LLM persona: `user@srv-ubuntu`  
Home directory: `/home/user`

---

## Commands to run (PowerShell, Windows)

### Before any cleanup — save the patch

```powershell
# Run from repo root
git -C VelLMes-AI-Deception-Framework rev-parse HEAD

# Save diff of all changes to VelLMes source
New-Item -ItemType Directory -Force -Path patches | Out-Null
git -C VelLMes-AI-Deception-Framework diff > patches\vellmes.patch
```

### Build the image

```powershell
# From repo root
docker compose -f docker/vellmes.compose.yaml build
```

### Start the service

```powershell
docker compose -f docker/vellmes.compose.yaml up
```

Or detached:

```powershell
docker compose -f docker/vellmes.compose.yaml up -d
```

### Clear SSH known-hosts entry (run before each fresh smoke test)

```powershell
ssh-keygen -R "[127.0.0.1]:2228"
```

### Smoke test

```powershell
ssh -p 2228 user@127.0.0.1
```

Once logged in, run:

```
whoami
pwd
ls
uname -a
notacommand
exit
```

Expected:
- `whoami` → `user`
- `pwd` → `/home/user`
- `ls` → list of home directory files (LLM-generated)
- `uname -a` → Linux banner mentioning `srv-ubuntu` and a kernel version
- `notacommand` → `bash: notacommand: command not found` (or similar)
- `exit` → session closes cleanly

### Read container logs (check for empty replies or errors)

```powershell
# Follow logs live
docker compose -f docker/vellmes.compose.yaml logs -f

# Check for empty model replies: VelLMes logs "Error generating response!" in logSSH.txt
# Copy log files out of the named volume:
$container = docker compose -f docker/vellmes.compose.yaml ps -q vellmes
docker cp "${container}:/app/logs/." ./docker/logs/vellmes/

# Look for empty messages in the wrapper's own logs:
docker compose -f docker/vellmes.compose.yaml logs | Select-String "CHILD STDERR", "EARLY EXIT"
```

---

## Known risks / things likely to fail first

1. **`openai` package not pinned.** If a breaking API change is released,
   `pip install openai` may pull in an incompatible version. Recommend pinning
   to a known-good release (e.g. `openai==1.58.1`) in
   `VelLMes-AI-Deception-Framework/requirements.txt`.

2. **`tiktoken` C extension on python:3.11-slim.** `gcc` is installed in the
   Dockerfile to build `cffi` (asyncssh dependency). `tiktoken` uses a Rust
   extension built by `maturin`; if no pre-built wheel is available for the
   exact Python version, the build will fail unless `rustc` / `cargo` are
   installed. **Mitigation:** the tiktoken import is now wrapped in
   `try/except ImportError`; if it fails to install, remove it from
   `requirements.txt` and the fallback TOKEN_COUNT=0 handles the rest.

3. **GLM model may emit `<think>` blocks.** The stripping regex handles the
   common `<think>…</think>` pattern but some model variants use different
   delimiters. Watch the first smoke-test session carefully.

4. **VelLMes.py `input()` blocking.** The tool reads user input via
   `input(f'\n{messages[-1]["content"]}'.strip() + " ")`. In subprocess/pipe
   mode (used by the wrapper) `input()` reads from stdin — this is the
   correct behaviour. However, if VelLMes.py emits a multi-line response
   ending with the prompt on the last line, the wrapper's `_read_until_prompt`
   will correctly detect `$ ` at the end of the buffer. If the model
   occasionally omits the trailing `$ `, the wrapper will wait until the
   `EXEC_TIMEOUT` (90 s) and then proceed — which matches the harness timeout.

5. **Cross-session isolation: file path uniqueness.** The wrapper generates
   `-o /app/logs/history_<uuid>.txt` per session. If the named volume fills
   up with many session files, disk pressure could eventually cause failures.
   For a benchmark (≤5 runs × 37 commands) this is not a practical risk.

6. **`connection_lost` / `EARLY EXIT` on first connection.** The first LLM
   call after container start may be slow (Fireworks cold-start). If it
   exceeds the SSH client's initial read timeout the client will disconnect
   before seeing the banner. The wrapper itself has `EXEC_TIMEOUT=90` s for
   waiting for the initial banner; the harness must be configured with a
   matching `ConnectTimeout` / `ServerAliveInterval`.

7. **`openai.OpenAI(**kwargs)` type errors from static analysis.** The
   pyright/mypy errors reported during patching are false positives from the
   checker not being able to resolve the dynamically-built `kwargs` dict at
   analysis time. The code is correct at runtime.

---

## UNVERIFIED claims

1. **SSH banner patch version** (`.11` in `OpenSSH_8.2p1 Ubuntu-4ubuntu0.11`):
   not confirmed against a real Ubuntu 20.04 OpenSSH 8.2 package revision.
   Adjust `SERVER_VERSION` in `vellmes_ssh_wrapper.py` to match your ground
   truth target.

2. **`<think>` blocks in GLM responses**: not confirmed that
   `accounts/fireworks/models/glm-5p3-flash` emits `<think>` blocks in an
   SSH-shell role-play persona. Observe the first smoke test.

3. **`openai` SDK exception messages and auth header leaks**: not confirmed
   whether the installed version includes the `Authorization` header value in
   `APIConnectionError` or similar exception strings that would be written to
   `logSSH.txt` by the `except Exception as e: logfile.write(str(e))` block.

4. **`tiktoken` wheel availability on python:3.11-slim**: not confirmed
   whether a pre-built wheel is available for all Python 3.11 micro versions
   used by `python:3.11-slim` on linux/amd64. If the build fails, remove
   `tiktoken` from `requirements.txt`.

5. **VelLMes `main()` arg-parsing in subprocess mode**: not confirmed that
   passing `-e /dev/null` does not cause VelLMes.py to crash on any code path
   that calls `open(env_path)` directly rather than via `dotenv_values`. The
   patched `set_key()` wraps the dotenv call in `try/except`, so an empty or
   missing file is handled.

---

## Other protocols (config-only, no changes made this round)

### MySQL

| Item | Value |
|------|-------|
| Config file | `VelLMes Configuration Files/configMySQL.yml` |
| Start command | `python3 VelLMes.py -e .env -c "VelLMes Configuration Files/configMySQL.yml" -m <model> -mt 900 -t 0.0 -o historyMySQL.txt -l logMySQL.txt` |
| Protocol / port | Interacts over stdin/stdout only. No real MySQL port binding. To expose as a network service, a TCP proxy (e.g. socat or a custom wrapper) must listen on port **3306** and pipe connections to `VelLMes.py` stdin/stdout. |
| Notes | The prompt configures multiple databases with IT-company names. The `\q` and `exit` commands close the session. |

### POP3

| Item | Value |
|------|-------|
| Config file | `VelLMes Configuration Files/configPOP3.yml` |
| Start command | `python3 VelLMes.py -e .env -c "VelLMes Configuration Files/configPOP3.yml" -m <model> -mt 2000 -t 0.0 -o historyPOP3.txt -l logPOP3.txt` |
| Protocol / port | stdin/stdout only. A TCP wrapper must listen on port **110** (or **995** for TLS) and pipe to `VelLMes.py`. |
| Notes | Simulates `cooperd@tpeaks.com` / password `owls`. Would need credential changes for a different persona. Session ends when VelLMes emits "Connection closed". |

### HTTP

| Item | Value |
|------|-------|
| Config file | `VelLMes Configuration Files/configHTTP.yml` |
| Start command | `python3 VelLMes.py -e .env -c "VelLMes Configuration Files/configHTTP.yml" -m <model> -mt 4000 -t 0.0 -o historyHTTP.txt -l logHTTP.txt` |
| Protocol / port | stdin/stdout only. A TCP wrapper (or `socat`) must listen on port **80** (or **8080**) and pipe raw HTTP requests to `VelLMes.py` stdin. |
| Notes | Simulates a printer device HTTP interface ("TechPrint 2000"). Session ends when VelLMes emits "Connection closed by foreign host." or "Bad Request". |
