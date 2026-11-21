# docs/PATCH_NOTES.md
# Source Patches Applied to Third-Party Repositories

This document lists every source edit made to each cloned third-party repository
to make it work with this benchmark.  Entries are taken from the notes in `Changes/`.

**Apply one route or the other, not both.** Machine-readable patches exist for the
VelLMes and HoneyBee repositories and live in `patches/` — see §0 below.  For every
other target the changes were applied by hand and are documented in the sections
that follow; there is no patch file for DECEIVE, Beelzebub, shelLM, galah, Cowrie,
the ground-truth servers, or the harness.  The `Changes/` directory contains the
detailed rationale documents — consult them if a step is unclear.

All items are marked **UNVERIFIED against upstream commit** because the exact commit
hashes of the third-party repositories at clone time were not recorded.  The clone
date window was **October 31 – November 2, 2026**.

---

## 0. Patch inventory

The patches in `patches/` are unified diffs against the third-party clones.  All
three are byte-reproducible records of edits that are **already applied** in the
current working trees; applying them again on top will fail.

| File | Lines | Hunks | Repository | State of the working tree |
|---|---:|---:|---|---|
| `patches/vellmes.patch` | 181 | 7 | `VelLMes-AI-Deception-Framework/` | applied — `git status` reports `M VelLMes.py` |
| `patches/honeybee.patch` | 737 | 28 | `honeybee/` | applied — modified and added files present |
| `patches/honeybee_before_fixes.patch` | 632 | 26 | `honeybee/` | **not** applied — superseded, kept for provenance |

`honeybee.patch` and `honeybee_before_fixes.patch` differ by two hunks: the current
patch adds the `temperature` / `max_tokens` settings wiring and an
`encoding="utf-8"` fix in `1_🐝_app.py`.  Do not apply
`honeybee_before_fixes.patch` on top of the current tree.

Verify the state before touching either repository:

```
git -C VelLMes-AI-Deception-Framework status --short
git -C honeybee status --short
```

## 1. DECEIVE (`DECEIVE/`)

Source notes: `Changes/CHANGES.md`, `Changes/FIX_CHANGES.md`, `Changes/SLIM_CHANGES.md`

Upstream: `https://github.com/splunk/DECEIVE` (resolves; `coverflex-tech/DECEIVE` is not a
repository). At upstream HEAD `cce98f3` the tracked template is `SSH/config.ini.TEMPLATE`,
so the clone's `SSH/config.ini` derives from that file.

### 1.1 `DECEIVE/SSH/ssh_server.py`

| Change | Why |
|--------|-----|
| Added `import re` at top | Required by new `strip_llm_output` helper |
| Added `strip_llm_output(text: str) -> str` function | Strips `<think>…</think>` blocks (GLM reasoning model output) and leading/trailing markdown fences (` ``` `) from every LLM reply before it is sent to the SSH client |
| `choose_llm()` openai branch: resolve API key from `OPENAI_API_KEY` env var first, fall back to `FIREWORKS_API_KEY` | Fireworks uses `OPENAI_API_KEY` name; original code used a different variable |
| `choose_llm()` openai branch: resolve `base_url` from `OPENAI_BASE_URL` env var | Original code had no base URL override; Fireworks endpoint is `https://api.fireworks.ai/inference/v1` |
| `choose_llm()` openai branch: pass `tiktoken_model_name` kwarg to `ChatOpenAI` | GLM model ID is not in tiktoken's model map; `tiktoken_model_name = "gpt-4o"` uses cl100k_base as a proxy and prevents `NotImplementedError` from `trim_messages()` |
| `session_summary()`: call `strip_llm_output` on raw summary before parsing | Prevents `<think>` preamble from corrupting the BENIGN/SUSPICIOUS/MALICIOUS judgment parser |
| `handle_client()`: change `== "YYY-END-OF-SESSION-YYY"` to `.strip() == "YYY-END-OF-SESSION-YYY"` | Stray trailing newline from model caused the exit sentinel to be missed |
| Lazy imports: moved top-level `from langchain_openai import ...`, `from langchain_aws import ...`, `from langchain_google_genai import ...`, `from langchain_ollama import ...` inside their respective `elif` branches in `choose_llm()` | Slim image does not install AWS/Google/Ollama packages; top-level import caused `ModuleNotFoundError` on startup |

UNVERIFIED against upstream commit.

### 1.2 `DECEIVE/SSH/config.ini`

| Change | Why |
|--------|-----|
| `model_name` changed from `gpt-4o` to `accounts/fireworks/models/glm-5p3-flash` | Use the benchmark model via Fireworks |
| Added commented-out `base_url` example pointing to Fireworks | Documentation; actual base URL supplied via `OPENAI_BASE_URL` env var |
| Added `tiktoken_model_name = gpt-4o` in `[llm]` section | Paired with code change above |

UNVERIFIED against upstream commit.

---

## 2. Beelzebub (`beelzebub/`)

Source notes: `Changes/BEELZEBUB_CHANGES.md`, `Changes/FIX2_CHANGES.md`

### 2.1 `beelzebub/internal/plugins/llm-integration.go` — function `InitLLMHoneypot`

| Change | Why |
|--------|-----|
| Added fallback: check `OPENAI_API_KEY` env var if `OPEN_AI_SECRET_KEY` is empty | Original only checked `OPEN_AI_SECRET_KEY`; project `.env` uses standard `OPENAI_API_KEY` name |
| Added: if `config.Host == ""` and `OPENAI_BASE_URL` is set, derive `config.Host = base + "/chat/completions"` | Fireworks endpoint; original required host to be set in YAML config |

No new imports needed; `strings` was already imported.

UNVERIFIED against upstream commit.

### 2.2 Configuration files created (not upstream source edits)

| File | Purpose |
|------|---------|
| `docker/beelzebub-ssh.yaml` | Service config: SSH on port 2222, LLM model, persona prompt, rate limiting disabled |
| `docker/beelzebub-core.yaml` | Core config: all remote output plugins disabled, log path set to `/logs/beelzebub.log` |

Note: `serverVersion` in `docker/beelzebub-ssh.yaml` is set to `"OpenSSH_8.2p1 Ubuntu-4ubuntu0.3"` (without the `SSH-2.0-` prefix) because `gliderlabs/ssh` prepends `"SSH-2.0-"` automatically.  See `Changes/FIX2_CHANGES.md` for confirmation.

---

## 3. shelLM / AdvancedshelLM (`shelLM/`)

Source notes: `Changes/ADVSHELLM_CHANGES.md`, `Changes/ADVSHELLM_FIX_CHANGES.md`, `Changes/ADVSHELLM_EXIT_FIX.md`

### 3.1 `shelLM/AdvancedshelLM/codebase/advancedShellm.py`

| Change | Why |
|--------|-----|
| `.env` load made non-fatal: wrapped `dotenv_values()` in `try/except` so missing `.env` does not crash | In Docker, env vars come from Compose `env_file`; no `.env` file is present in the container |
| `api_key` now falls back to `os.environ.get("OPENAI_API_KEY")` | When `.env` is absent, `config` is `{}`; original `config.get("OPENAI_API_KEY")` returned `None` |
| `exit` check: changed `if user_cmd.lower() in ["exit", ...]` to `if user_cmd.strip().lower() in ["exit", ...]: ... break` | Original code fell through the `if` block without a `break`, so the session never terminated on `exit` |
| Moved `logger.log_user`, `logger.record_command`, `logger.close_session` inside the exit branch (before `break`) | Avoids duplicate logging from the old fall-through path |

UNVERIFIED against upstream commit.

### 3.2 `shelLM/AdvancedshelLM/codebase/LLM_Plugins/api_clients/openai_client.py`

| Change | Why |
|--------|-----|
| Added `import os` | Required for env var reads below |
| `_BASE_URL` now reads from `OPENAI_BASE_URL` env var; `CHAT_COMPLETIONS_URL` and `RESPONSES_API_URL` built from `_BASE_URL` | URLs were hardcoded to `https://api.openai.com/v1/...` |
| `temperature` changed from `0.0` to `0.2` in `_send_chat_completions()` | Aligns with DECEIVE's default temperature for this benchmark |
| Added `from requests.exceptions import HTTPError as _HTTPError` | Needed to intercept HTTP errors |
| `_max_tokens = int(os.environ.get("MAX_TOKENS", "4096"))` — replaces hardcoded `16384` | Fireworks GLM rejects `max_tokens=16384` with HTTP 400 |
| Wrapped `resp.raise_for_status()` in `try/except _HTTPError: raise BackendHTTPError(...)` | `requests.HTTPError` was not caught by `advancedShellm.py`'s except clause; now wrapped so the existing handler produces a graceful shutdown message |

UNVERIFIED against upstream commit.

---

## 4. galah (`galah/`)

Source notes: `Changes/GALAH_CHANGES.md`

### 4.1 `galah/pkg/llm/llm.go` — function `cleanResponse`

| Change | Why |
|--------|-----|
| Added `thinkRe = regexp.MustCompile(``(?s)<think>.*?</think>``)` at package level | Fireworks GLM emits `<think>…</think>` reasoning blocks before JSON output; original stripper only handled markdown fences |
| Added `thinkRe.ReplaceAllString(s, "")` as first step in `cleanResponse` | Strips think blocks before fence stripping and JSON extraction |
| Added `fenceRe` to replace the old single `re` variable | Code hygiene; two regexes now used |
| Trimmed to outermost `{…}` (find first `{`, find last `}`) as third step | Ensures valid JSON is extracted even if stray text surrounds it |

No new imports added; `regexp` and `strings` were already imported.

UNVERIFIED against upstream commit.

---

## 5. llm-honeypot / cowrie-base (`llm-honeypot/`, `cowrie-base/`)

Source notes: `Changes/LLMHONEYPOT_CHANGES.md`, `Changes/LLMHONEYPOT_FIX_CHANGES.md`

### 5.1 Overlay pattern (not a fork)

`llm-honeypot/` is not a Cowrie fork — it is a plugin/overlay.  The deployment uses
**Cowrie v2.6.1** from `cowrie-base/` (confirmed from `cowrie-base/src/cowrie/_version.py`).
The overlay command files from `llm-honeypot/configs/` are copied on top of the
`cowrie-base/` source tree.

### 5.2 `docker/llmhoneypot.Dockerfile` — complete rewrite

The Dockerfile was rewritten from scratch.  Key changes:

| Old approach | New approach | Why |
|-------------|--------------|-----|
| `pip install cowrie` (PyPI) | `COPY cowrie-base/` + `pip install -e .` | PyPI Cowrie uses `command_modules` dict (old API); `cowrie-base` v2.6.1 uses `__all__` list (new API). The overlay `init.py` uses `__all__`, so it is only compatible with `cowrie-base` |
| Paths pointed to `cowrie-env/lib/python3.10/site-packages/cowrie/` | Paths use `src/cowrie/` | Correct path for editable install from source |
| `ENTRYPOINT` hardcoded `cowrie-env/bin/twistd` path | `ENV PATH` includes venv `bin/`; `ENTRYPOINT ["twistd", ...]` | Cleaner |

### 5.3 `docker/llmhoneypot.cowrie.cfg` — corrections

| Key | Old value | New value | Reason |
|-----|-----------|-----------|--------|
| `data_path` | `cowrie-env/lib/python3.10/site-packages/cowrie/data` | `src/cowrie/data` | Static files moved to `src/cowrie/data` in Cowrie 2.6.0 |
| `contents_path` | `cowrie-env/lib/python3.10/site-packages/cowrie/data/honeyfs` | `honeyfs` | `honeyfs/` is at repo root in `cowrie-base/`; Cowrie resolves relative to WORKDIR |
| `txtcmds_path` | `cowrie-env/lib/python3.10/site-packages/cowrie/data/txtcmds` | `src/cowrie/data/txtcmds` | Same reason as `data_path` |

All network output plugins remain disabled.  `output_crashreporter` explicitly set to `false`.

### 5.4 Cowrie version pin

Cowrie v2.6.1 is used (from `cowrie-base/`).  This was the known pin for
llm-honeypot as confirmed by `Changes/LLMHONEYPOT_FIX_CHANGES.md` and
`cowrie-base/src/cowrie/_version.py`.

---

## 6. Cowrie (standalone baseline, `cowrie-base/` image not used)

Source notes: `Changes/COWRIE_CHANGES.md`

The standalone Cowrie baseline uses the **official `cowrie/cowrie:latest` Docker Hub image** — no source edits to the Cowrie codebase.  All customisation is via mounted config files:

- `docker/cowrie/cowrie.cfg`: sets hostname, SSH banner (without `SSH-2.0-` prefix — Cowrie prepends it), JSON logging, `download_enabled = false`, all remote output plugins disabled.
- `docker/cowrie/userdb.txt`: accepted credentials.

No upstream source files were modified.

---

## 7. Ground-Truth Servers

Source notes: `Changes/HARNESS_CHANGES.md`, `Changes/GT_SSH_PTY_FIX.md`, `Changes/HTTP_GT_FIX_CHANGES.md`

These are not third-party repositories — they are new Dockerfiles created for this benchmark.

### 7.1 `docker/groundtruth_ssh.Dockerfile`

| Change | Why |
|--------|-----|
| Added `PermitTTY yes` and `LogLevel VERBOSE` to sshd_config | Permits interactive PTY session; verbose logging exposes failures |
| Made `pam_loginuid.so` session handling `optional` | Container `/proc/self/loginuid` is not writable in Docker; marking optional prevents login accounting from killing valid sessions |
| `cap_add` in compose: added `FSETID`, `SETPCAP`, `AUDIT_WRITE` to existing list | Required for PTY ownership/group setup, capability handling during privilege separation, and PAM audit accounting |

### 7.2 Ground-truth HTTP

No source edits needed — the desired state was already present when the files were inspected.  See `Changes/HTTP_GT_FIX_CHANGES.md` for details.

---

## 8. Harness (`harness/`)

Source notes: `Changes/HARNESS_CHANGES.md`, `Changes/GT_SSH_PTY_FIX.md`

These are new files created for this benchmark, not edits to third-party code.

| File | Key design choices |
|------|--------------------|
| `harness/run_ssh.py` | Uses `paramiko.Transport` directly (not `SSHClient`); `auth_none()` first then password fallback; non-blocking `recv` loop with `select.select`; prompt detection with 0.5 s quiet period; hard 90 s per-command timeout; JSONL output |
| `harness/run_http.py` | Uses `http.client.HTTPConnection` (stdlib only); host locked to `127.0.0.1`; Date drift computed as `time.time() − parsedate_to_datetime(Date header).timestamp()` |
| `harness/analyze.py` | Reads from JSONL files in `results/raw/` and `results/raw_http/`; excludes `exit` command from all metrics; llm-honeypot excluded from fidelity/similarity/determinism averages |

---

## 9. VelLMes (`VelLMes-AI-Deception-Framework/`)

Source notes: `Changes/VELLMES_CHANGES.md`, `patches/vellmes.patch`

Patch file exists (§0).  Applied to `VelLMes.py` only; the working tree diff is
`1 file changed, 95 insertions(+), 19 deletions(-)`.

| Change | Why |
|--------|-----|
| `import tiktoken` wrapped in `try/except ImportError`, bound to `_tiktoken` (may be `None`) | `encoding_for_model()` raises `KeyError` for non-OpenAI model IDs such as `accounts/fireworks/models/glm-5p3-flash`; a hard import made the script unusable before the first request |
| Added `import re` and compiled `_THINK_RE`, `_FENCE_START`, `_FENCE_END` | GLM wraps replies in ` thinking…</think>` blocks and markdown fences; both must be stripped before the text is treated as shell output |
| Added `_strip_reasoning(text)` | Removes think blocks and one outer fence, then strips whitespace |
| Added `_get_client()`, a cached `openai.OpenAI` built from `OPENAI_API_KEY` and optional `OPENAI_BASE_URL` | Keeps the key out of files and out of `argv`; the Compose `env_file` supplies it at runtime |
| `.env` loading tolerates a missing, empty, or `/dev/null` path and falls back to the process environment | `docker/vellmes.Dockerfile` runs the child with `-e /dev/null`; the original loader assumed a populated dotenv file |
| `read_arguments()` / `main()`: model, temperature and max tokens resolve as **CLI flag → environment variable (`MODEL`, `TEMPERATURE`, `MAX_TOKENS`) → YAML identity** | Docker Compose supplies the values as environment variables; without this fallback a run with a flag left unset silently used the YAML values instead |
| `chat.completions.create()` is called through `_get_client()` with `temperature = model_temperature` and `max_tokens = model_max_tokens` (`VelLMes.py:276-281`) | Confirms the resolved values reach the API request, not merely the config parse |
| Token counting wrapped so a `tiktoken` failure sets `TOKEN_COUNT = 0` | An unavailable encoding aborted the session instead of degrading to an unknown count |
| `== None` / `!= None` comparisons changed to `is None` / `is not None` | Style fix carried in the same hunks |

UNVERIFIED against upstream commit.

## 10. HoneyBee (`honeybee/`)

Source notes: `Changes/HONEYBEE_CHANGES.md`, `patches/honeybee.patch`

Patch file exists (§0).  HoneyBee is an LLM **generator**, not a honeypot; it is
listed here because it is a cloned third-party repository with source edits.

| Change | Why |
|--------|-----|
| Import paths rewritten from `src.*` → `honeybee.src.*` and `tabs.*` → `honeybee.tabs.*` across the Streamlit app, pages and tabs | The package is installed editable from `honeybee/`, so the importable top-level package is `honeybee`, not the repository root |
| Added `honeybee/src/__init__.py` and `honeybee/pages/__init__.py` | Both directories lacked an `__init__.py` and were not importable as packages |
| `settings["temperature"]` and `settings["max_tokens"]` read into module-level variables | The app previously ignored both settings, so the recorded run parameters could not be attributed to it |
| `Path(...).read_text(encoding="utf-8")` for `misconfigurations_catalog.json` | Default Windows code page fails to decode the non-ASCII catalog |
| `pyproject.toml` adjusted for the editable install path | Required by the package rename above |
| Touched modules: `client_provider.py`, `generators.py`, `local_deploy.py`, `query_history.py`, `settings.py`, `trace_tools.py`, `tabs/{dockercompose,dockerfile,nuclei}_tab.py` | Supporting changes for the rename and the runtime settings |

UNVERIFIED against upstream commit.

*End of PATCH_NOTES.md*
