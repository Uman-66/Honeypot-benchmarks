# HONEYBEE_CHANGES.md

Benchmark integration notes for **honeybee** (package `pyhoneybee` v0.1.1).

UI generation tabs now report empty or exhausted model results instead of raising.

---

## Step 1 — Code Investigation Answers

### a) Entry point and Streamlit headless configuration

| Item | Finding | Evidence |
|------|---------|----------|
| Console script | `honeybee = "honeybee:main"` | `pyproject.toml:34` |
| What `main()` does | Builds `["streamlit", "run", "<path>/1_🐝_app.py", *args]` and calls `runpy.run_module("streamlit", run_name="__main__")` | `honeybee/__main__.py:9-12` |
| Streamlit app file | `honeybee/1_🐝_app.py` | `__main__.py:9` |
| Headless / address / port | Pass `--server.headless=true --server.address=0.0.0.0 --server.port=8501` as trailing args after `honeybee --` **or** put `[server] headless=true` in `~/.streamlit/config.toml`. Both methods used: the Dockerfile writes the config.toml and the CMD also passes the flags. | Streamlit docs; Dockerfile lines 54–60, 71 |
| Telemetry off | `[browser] gatherUsageStats = false` in config.toml, plus `--browser.gatherUsageStats=false` on CMD | Dockerfile lines 54–60, 71 |
| Package name & version | `pyhoneybee` `0.1.1` | `pyproject.toml:6`, `honeybee/__init__.py:1` |
| Python requirement | `>=3.9` (pyproject.toml says 3.9; image uses 3.11-slim) | `pyproject.toml:12` |

### b) LLM client library, configurability, model names, structured outputs

| Item | Finding | Evidence |
|------|---------|----------|
| Library | `openai` SDK (`openai==1.66.2`) | `requirements.txt:5`, `src/client_provider.py:1` |
| `base_url` configurable? | **Not in original code** — `OpenAI(api_key=...)` was constructed without `base_url`. **Patched** to read `OPENAI_BASE_URL` from the environment. | `src/client_provider.py:6` (original); patch adds `os.getenv("OPENAI_BASE_URL")` |
| Azure path | Selected by sidebar "Azure OpenAI" provider dropdown. Uses `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` env vars. | `src/settings.py:48-69`, `src/client_provider.py:8-12` |
| Hardcoded model names | `"gpt-4o"` used as default in both OpenAI and Azure branches. **Patched** to read `MODEL` env var (default still `gpt-4o` if `MODEL` not set). | `src/settings.py:39`, `71` (original) |
| Structured outputs / `response_format` / function calling | **None.** All calls use plain `client.chat.completions.create(messages=[...], model=...)`. No `response_format`, no function-calling, no JSON-schema mode. | `src/generators.py:17-23` (original), all generate_* functions |
| tiktoken / model-name-specific logic | **None found.** No tiktoken import anywhere in the codebase. | Full source scan |
| `temperature` / `max_tokens` in original | **Not set** in any `create()` call — model defaults are used. **Patched** to accept and forward `temperature` and `max_tokens` throughout the call stack. | `src/generators.py` (all `create()` calls) |
| Impact on glm-5p3-flash | The absence of structured-output mode means glm-5p3-flash is fully compatible as long as it returns the requested JSON in a markdown fence or as raw JSON. The `_strip_think_and_fences` patch handles `<think>` blocks and fence variations. | UNVERIFIED: whether glm-5p3-flash emits `<think>` blocks on non-reasoning tasks — tested cautiously by stripping regardless. |

### c) Output parsing — how model responses become files

| Item | Finding | Evidence |
|------|---------|----------|
| Normal flow | `generate_from_prompt()` searches for ` ```json … ``` ` with `re.search(r"```json(.*?)```$", ..., re.DOTALL)` and calls `json.loads()`. Retries up to 5 times on failure. | `src/generators.py:26-30` (original) |
| `<think>` stripping | **Not present in original.** **Patched**: `_strip_think_and_fences()` removes `<think>…</think>` blocks (dotall, case-insensitive), then extracts the first ` ```json … ``` ` fence (now matching both array and object), then falls back to stripping stray fence markers. | `src/generators.py:9-30` (patched) |
| Markdown fence stripping | The original regex required `$` at end with `DOTALL` — brittle. **Patched** to a more robust two-pass approach matching `[…]` or `{…}` inside any ` ``` ` fence. | `src/generators.py:23-29` (patched) |
| Nuclei output | Not parsed as JSON by the app — raw model response string is stored as-is, then `st.write()`-ed. The harness attempts `yaml.safe_load()` on it as a validity check. | `src/generators.py:68`, `tabs/nuclei_tab.py:17` |

### d) Deploy feature — how it works and how it is disabled

| Item | Finding | Evidence |
|------|---------|----------|
| Mechanism | `local_deploy_compose()` writes the generated YAML to a `tempfile.mkdtemp(prefix="honeybee-")` directory, then calls `subprocess.Popen(["docker", "compose", "up"], cwd=tmpdir)`. It streams stdout into the Streamlit UI. | `src/local_deploy.py:55-94` (original) |
| When enabled | Only if `check_docker_compose_installed()` returns `True` (runs `docker compose ls` and checks exit code + stdout prefix). | `src/local_deploy.py:12-19` (original) |
| Disable method | **Patched**: `check_docker_compose_installed()` always returns `False`; `local_deploy_compose()` raises `RuntimeError`. The Docker CLI is not installed in the image; `/var/run/docker.sock` is not mounted. | `src/local_deploy.py` (patched) |
| Generated files | Written to a `tempfile.mkdtemp()` directory **during deploy only** (not during generation). During generation, content exists only in Streamlit `session_state`. The query history stores outputs in `.qhistory/*.json`. | `src/local_deploy.py:57-58`, `src/query_history.py` |

### e) Jina feature — external calls and disable path

| Item | Finding | Evidence |
|------|---------|----------|
| What it does | Calls `https://r.jina.ai/{url}` with `Authorization: Bearer {jina_api}` to convert a URL to markdown, then feeds it to the LLM. | `honeybee/1_🐝_app.py:127-129` |
| Guarded by | The "Import from URL" branch checks `if not jina_ai_api: st.warning(...); st.stop()`. If `get_jina_ai_api_key()` returns empty string the UI halts before making the request. | `1_🐝_app.py:120-122` |
| How disabled | **Patched**: `get_jina_ai_api_key()` in `src/settings.py` now always returns `""` (empty string). The `JINA_API_TOKEN` env var is never read; no sidebar input is shown. "Import from URL" mode will display a warning and stop. | `src/settings.py:103-109` (patched) |
| Other outbound calls | `requests` library imported in `1_🐝_app.py:1` but only used for the Jina call. `boto3` in `pages/2_🌐️_network.py` is used only for S3 PCAP loading (an opt-in UI action, not automatic). No automatic outbound calls other than Jina (now disabled) and the LLM API call. | `1_🐝_app.py:1`, `pages/2_🌐️_network.py:6` |

### f) Persistence and key-leak risk

| Location | What is stored | Key-leak risk? |
|----------|---------------|---------------|
| `src/settings.py` sidebar text input (`type="password"`) | API key stored **only in Streamlit `session_state`** (in-memory per session, never serialized to disk by Streamlit) | **No disk write.** Risk: key visible in Streamlit session while the browser is open. Mitigated: `OPENAI_API_KEY` from env means input is never shown. |
| `src/query_history.py` | Writes `{type, input_parameters, output}` to `<DATA_DIR>/.qhistory/<timestamp>.json`. Input parameters are `[application, selected_misconfigs]` — **no API keys**. | No key leak. |
| `1_🐝_app.py` line 37 | `st.sidebar.info("Using OpenAI API Key from environment variable")` — only prints a static banner, not the key value. | No leak. |
| Anywhere else | No `logging`, no `print(api_key)`, no file write of any secret found. | Confirmed by full source scan. |
| UNVERIFIED | Streamlit's own session serialization behavior; whether it ever persists `st.session_state` beyond the browser session. Per Streamlit docs it does not, but not tested. | UNVERIFIED |

### g) What the app writes to disk

| Path | Written by | Content | Named volume? |
|------|-----------|---------|---------------|
| `<DATA_DIR>/.qhistory/<ts>.json` | `src/query_history.py:save_query()` | `{type, input_parameters, output}` per generation | Yes — `honeybee_data` at `/app/data` |
| `~/.streamlit/` | Streamlit itself | Config cache, feature flags | Container `~/.streamlit` (ephemeral unless separately mounted) |
| `tmpfile` (deploy only) | `src/local_deploy.py` (original) | Generated `docker-compose.yaml` | **Disabled by patch — never written** |
| Nothing else | | | |

### h) Dependencies and Python version

| Package | Version pinned? | Potential issue on python:3.11-slim |
|---------|----------------|-------------------------------------|
| `streamlit` | `==1.46.0` | None expected |
| `openai` | `==1.66.2` | None expected |
| `PyYAML` | `==6.0.2` | None expected |
| `yamllint` | `==1.37.0` | None expected |
| `yamlfix` | `==1.17.0` | None expected |
| `tqdm` | `==4.67.0` | None expected |
| `oyaml` | `==1.0` | None expected |
| `PyJWT` | `>=2.8.0` | None expected |
| `scapy` | `==2.6.1` | Needs `libmagic1` system package (used for `magic` import in scapy); **added to Dockerfile apt-get** |
| `boto3` | `==1.34.26` | None expected |
| `Requests` | `==2.32.3` | None expected |
| Python version | pyproject requires `>=3.9`; image uses 3.11 | Compatible |

UNVERIFIED: `scapy` may require additional system libs beyond `libmagic1` (e.g. `tcpdump`, `libpcap-dev`) if live capture is used. The Network page only reads uploaded PCAP files or fetches from S3 — no live capture is performed by the app itself. `libmagic1` should be sufficient.

### i) Classification — is honeybee a honeypot?

**No. honeybee is NOT a honeypot.**

Evidence:
- The app accepts connections **only from the operator's browser** (Streamlit HTTP/WebSocket on port 8501 → 127.0.0.1:2229). It does not listen for attacker connections.
- It does **not emulate any vulnerable service** (SSH, HTTP, database, etc.).
- It does **not capture, log, or analyse attacker interaction data**.
- Every file in `honeybee/` is either:
  - Streamlit UI code (`1_🐝_app.py`, `tabs/`, `pages/`)
  - LLM generator code (`src/generators.py`, `src/client_provider.py`)
  - Support utilities (`src/settings.py`, `src/validations.py`, `src/trace_tools.py`, `src/query_history.py`)
  - A catalog of misconfigurations (`misconfigurations_catalog.json`)
  - Prompt files (`prompts/*.md`)
- The "one-click deploy" feature (now disabled) would have deployed **generated** misconfigured apps, which could then serve as honeypots — but that is a downstream use case, not honeybee itself.
- The Network page (`pages/2_🌐️_network.py`) is a PCAP viewer for analysing packet captures produced by those deployed apps — again, not honeybee itself acting as a honeypot.

**Benchmark classification**: honeybee is a **misconfiguration-artifact generator**, not a honeypot. It should be treated as a **tooling / harness component** in the benchmark — used to generate test targets, not as a subject of the benchmark itself. Its outputs (Docker Compose / Dockerfile files) are the raw material for honeypot research, not honeypot deployments.

### j) Curated misconfiguration list

| Item | Finding | Evidence |
|------|---------|----------|
| Location | `honeybee/misconfigurations_catalog.json` | `1_🐝_app.py:53-55` |
| Structure | `{category: {application: [misconfiguration_string, ...]}}` — **21 applications, 210 misconfigurations (as shown in the UI)** | `misconfigurations_catalog.json` |
| Categories | Development Tools, Messaging Systems, Data Processing, Web Servers, Databases | `misconfigurations_catalog.json:2-264` |
| Usable without Jina? | **Yes.** "Browse Catalog" mode reads only from the JSON file; Jina is only needed for "Import from URL" mode. | `1_🐝_app.py:91-102` |
| README examples in catalog? | PostgreSQL is under Databases. Grafana is under Data Processing. The exact wording differs from the README but equivalent misconfigs are present. | `misconfigurations_catalog.json:238-249`, `190-200` |

---

## Classification Section

**honeybee is NOT a honeypot.**

It is a Streamlit web application that uses an LLM to generate deliberately-misconfigured Docker artifacts (Compose files, Dockerfiles, Nuclei detection templates, READMEs). Its purpose is to create test targets for vulnerability research — it is not itself a target and does not interact with attackers.

**How it should be treated in the benchmark:**
- honeybee is a **generator / tooling component**. Run it to produce inert artifact files.
- Its generated outputs (YAML, Dockerfiles) must be stored as text only and **never deployed** via this benchmark setup.
- If you want to study LLM-generated misconfigured services as honeypots, honeybee is a useful upstream tool, but the honeypot itself would be whatever you build from its output.

---

## Files Created / Edited

| File | Type | Reason |
|------|------|--------|
| `docker/honeybee.Dockerfile` | **Created** | Container image: python:3.11-slim, UID 10001, no Docker CLI, Streamlit headless config |
| `docker/honeybee.compose.yaml` | **Created** | Compose definition: loopback-only port 127.0.0.1:2229:8501, env_file secrets, named volume, cap_drop ALL |
| `honeybee/honeybee/src/client_provider.py` | **Edited** | Add `OPENAI_BASE_URL` support via `os.getenv` so Fireworks AI endpoint works |
| `honeybee/honeybee/src/settings.py` | **Edited** | Default model from `MODEL` env var; expose `temperature`/`max_tokens` from env vars; disable Jina by returning `""` |
| `honeybee/honeybee/src/generators.py` | **Edited** | Add `_strip_think_and_fences()` for `<think>` block and fence stripping; thread `temperature`/`max_tokens` through all `create()` calls |
| `honeybee/honeybee/src/local_deploy.py` | **Edited** | Disable deploy feature completely: `check_docker_compose_installed()` returns `False`; `local_deploy_compose()` raises `RuntimeError` |
| `honeybee/honeybee/src/query_history.py` | **Edited** | Read `DATA_DIR` env var for history path so history writes to the named volume at `/app/data` |
| `honeybee/honeybee/tabs/dockercompose_tab.py` | **Edited** | Thread `temperature`/`max_tokens` through `render()` signature |
| `honeybee/honeybee/tabs/dockerfile_tab.py` | **Edited** | Thread `temperature`/`max_tokens` through `render()` signature |
| `honeybee/honeybee/tabs/nuclei_tab.py` | **Edited** | Thread `temperature`/`max_tokens` through `render()` signature |
| `honeybee/honeybee/1_🐝_app.py` | **Edited** | Extract `temperature`/`max_tokens` from settings and pass to all tab renders |
| `harness/honeybee_generate.py` | **Created** | Headless harness: runs two README example cases through the generator core, writes inert artifacts to `results/honeybee/`, produces `validity.json` |

---

## PowerShell Commands (in order)

### a) Before any cleanup — capture current state

```powershell
# Record the exact commit of the honeybee source
git -C honeybee rev-parse HEAD

# Export all source modifications as a UTF-8 patch file
# --output avoids shell redirection encoding issues
git -C honeybee diff --output="$PWD\patches\honeybee.patch"
```

### b) Build and start the container

```powershell
# Build the image (from repo root)
docker compose -f docker/honeybee.compose.yaml build

# Start in detached mode
docker compose -f docker/honeybee.compose.yaml up -d
```

### c) Manual test at http://127.0.0.1:2229

Open your browser to **http://127.0.0.1:2229** and perform these two tests only:

**Test 1 — PostgreSQL, no password:**
1. Input mode: Browse Catalog → Databases → PostgreSQL
2. Select misconfigurations: "Weak password policies or no password set" + "Trust authentication method used allowing login without password"
3. Click "Generate Docker Compose" → verify YAML appears in the code pane
4. Click "Generate Dockerfile" → verify Dockerfile content appears
5. DO NOT click "Deploy Locally" (it is disabled)

**Test 2 — Grafana, multiple misconfigurations:**
1. Input mode: Browse Catalog → Data Processing → Grafana
2. Select all four misconfigurations

## Bugs fixed in the benchmark integration

* **(a) Empty model content:** `message.content` can be `None` or empty. The generator
  now treats that as a failed attempt, logs only non-sensitive attempt metadata to
  stderr, and preserves the existing retry count.
* **(b) Windows decoding:** all `read_text()` and `open()` reads in the honeybee
  package now specify UTF-8, including the Nuclei prompt.

### Task 1 files changed

* `honeybee/src/generators.py` — UTF-8 prompt reads, empty-content handling,
  attempt telemetry, and configurable completion budget.
* `honeybee/1_🐝_app.py` — UTF-8 catalog read.
* `honeybee/src/query_history.py` — UTF-8 history reads.

## Results

The benchmark checker previously applied compose and Dockerfile checks to every extracted
code block, so auxiliary files such as `postgresql.conf`, SQL, README, and datasource YAML
created false failures. It now classifies one primary artifact per generator, records
auxiliary files without scoring them, and rejects an accepted attempt whose finish reason is
`length`. The saved `postgresql_no_password` run03 Dockerfile record is therefore an
accepted truncation: all three attempts ended with `length`, and the third returned files;
this is not a logging mismatch. No root cause for the length failures is claimed.

TODO — run the 16384-token sensitivity run and compare primary-artifact validity without
claiming a cause for any remaining length failures.

The scorer was revised after the first results were seen; the original unscored outputs are kept in results/honeybee/validity.json.
3. Click "Generate Docker Compose" → verify YAML
4. Click "Generate Nuclei" → verify YAML template appears
5. DO NOT deploy

### d) Confirm NOTHING was deployed

```powershell
# Only the honeybee container should appear — no postgres, grafana, etc.
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
# Expected: one row for "honeybee-honeybee-1" on 127.0.0.1:2229->8501/tcp
```

### e) Read container logs

```powershell
# Tail logs
docker compose -f docker/honeybee.compose.yaml logs --tail=100

# Follow logs live
docker compose -f docker/honeybee.compose.yaml logs -f
```

### f) Run the headless harness (optional)

```powershell
# From repo root, with venv that has honeybee installed:
# pip install -e honeybee/
python harness/honeybee_generate.py --runs 2

# Dry-run (no LLM calls, writes placeholder files):
python harness/honeybee_generate.py --dry-run

# Outputs written to: results/honeybee/<case>_run01/, results/honeybee/<case>_run02/
# Validity record:     results/honeybee/validity.json
```

---

## Known Risks / Things Likely to Fail First

1. **`scapy` build fails** — `scapy==2.6.1` imports `magic` which needs `libmagic1`. Added to Dockerfile apt-get. If additional libs are needed (e.g. `libpcap-dev`), the build error will say so.

2. **Streamlit emoji filename on Windows** — The app file is `1_🐝_app.py`. On Windows hosts this is fine inside the Docker Linux container, but `COPY honeybee/ /app/honeybee_src/` must preserve the filename. Docker buildx with the default context should handle this.

3. **`<think>` stripping regex** — The patch uses `re.DOTALL | re.IGNORECASE` for `<think>` and a nested bracket match for fences. If glm-5p3-flash nests JSON inside a `<think>` block (unlikely), the stripper would discard it. Watch for "all retries exhausted" (5×) in container logs.

4. **glm-5p3-flash JSON format** — UNVERIFIED whether this model reliably wraps output in ` ```json … ``` ` fences as instructed by the system prompts. The 5-retry loop in `generate_from_prompt()` is the main guard. Monitor the Streamlit UI for "generation failed" toasts.

5. **`temperature` not accepted** — UNVERIFIED whether the Fireworks glm-5p3-flash endpoint accepts the `temperature` parameter. If it raises a 400 error, remove `TEMPERATURE` from the compose environment and revert the `temperature=` kwarg default to relying on the model default.

6. **Named volume / DATA_DIR** — `query_history.py` now reads `DATA_DIR=/app/data`. The `mkdir -p /app/data/.qhistory` in the Dockerfile pre-creates it owned by `honey`. If the named volume is mounted before the `chown` layer is applied on a fresh volume, writes may fail. Watch for `PermissionError` in logs.

7. **`read_only: true` root filesystem** — Not enabled. Streamlit writes to `~/.streamlit/` (cache, telemetry stub) and pip leaves behind `__pycache__`. A truly read-only rootfs would require additional `tmpfs` mounts for these paths. Mitigated by `cap_drop: ALL` + `no-new-privileges` + non-root user.

8. **`.qhistory` path on bare dev install** — In a local `pip install -e .` dev setup, `DATA_DIR` is not set, so history goes to `honeybee/honeybee/src/.qhistory/` (original behavior). Set `export DATA_DIR=./data` before running locally if you want a different path.

---

## UNVERIFIED Claims

- Whether `scapy==2.6.1` on python:3.11-slim needs any system lib beyond `libmagic1`.
- Whether glm-5p3-flash emits `<think>` blocks on normal (non-reasoning-mode) prompts.
- Whether glm-5p3-flash reliably wraps JSON in ` ```json ``` ` fences as the system prompts instruct.
- Whether the Fireworks endpoint accepts `temperature` and `max_tokens` for this model.
- Whether Streamlit's internal session state is ever persisted to disk in this version (`==1.46.0`).
- Whether `honeybee` (the console script) correctly forwards extra args after `--` to Streamlit in v1.46.0.
