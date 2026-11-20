# Honeypot Benchmark — Summary Report

> **WARNING: observed rows differ from expected benchmark rows; see each target's documented exclusions.**

> **Caveats and methodology notes**
> - Similarity to the SSH ground truth is a rough proxy only.
>   LLM honeypots use different personas, hostnames, and invented filesystems;
>   direct output comparison is biased against them.
> - AdvancedshelLM runs an extra wrapper layer (different persona, internal LLM calls),
>   so latency and output style differ from direct-prompt honeypots.
> - Beelzebub seeds its conversation with a `pwd`/home exchange before the benchmark
>   commands arrive, which may affect state-dependent commands.
> - Cowrie and llm-honeypot share a static fake filesystem; their `ls`, `cat`, and
>   state commands will always match each other but not necessarily the ground truth.
> - Different honeypots use different hostnames and usernames; host-specific commands
>   (marked `host_specific: true`) are listed for reference only and excluded from
>   fidelity scoring.
> - The ground truth container is a plain Ubuntu 20.04 system with no special persona;
>   persona-dependent content in LLM honeypots cannot be expected to match it.
> - The llm-honeypot detector target is **excluded** from fidelity, similarity,
>   pairwise determinism, and aggregate averages; it has its own section.
> - All numbers are computed from files in `results/raw/` and `results/raw_http/`.
>   If those files are missing, the corresponding fields show `—`.

---

## SSH Targets

### advshellm  *(kind: llm)*

**Accounting:** n_expected=180, n_used=144
> **WARNING:** excluded 36 rows — exit records are harness control rows; malformed rows lack a known command id and are not benchmark observations.

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 1.962s |
| p95 | 5.262s |
| n | 144 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 1.814s | 2.207s | 12 |
| files | 4.911s | 5.262s | 24 |
| permissions | 2.393s | 3.698s | 8 |
| process | 6.432s | 17.424s | 8 |
| recon | 2.378s | 4.459s | 52 |
| state | 1.868s | 2.346s | 40 |

**Reliability**

- Runs: 5
- Commands: 144
- Timeouts: 0
- Empty outputs: 20
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.6141
- Bootstrap 95% CI: (0.4548, 0.7652)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 28 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: none
- spurious_nonempty: {'ls': 4, 'which_python3_gcc': 4}

**Determinism** (mean pairwise similarity across runs): 0.8030

---

### beelzebub  *(kind: llm)*

**Accounting:** n_expected=180, n_used=180

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 2.664s |
| p95 | 6.790s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 2.438s | 3.969s | 15 |
| files | 3.676s | 7.032s | 30 |
| permissions | 2.406s | 4.055s | 10 |
| process | 3.828s | 6.527s | 10 |
| recon | 2.575s | 4.797s | 65 |
| state | 5.482s | 24.350s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 0
- Empty outputs: 2
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.3334
- Bootstrap 95% CI: (0.2135, 0.4496)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 35 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: none
- spurious_nonempty: {'ls': 5, 'which_python3_gcc': 5, 'state_cd_tmp': 4, 'state_echo_marker': 5, 'state_mkdir_bm_dir': 5, 'state_rm_marker': 4, 'state_rmdir_bm_dir': 5}

**Determinism** (mean pairwise similarity across runs): 0.5399

---

### cowrie  *(kind: baseline)*

**Accounting:** n_expected=180, n_used=180

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 0.563s |
| p95 | 0.595s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 0.565s | 0.578s | 15 |
| files | 0.573s | 0.594s | 30 |
| permissions | 0.567s | 0.587s | 10 |
| process | 0.578s | 0.602s | 10 |
| recon | 0.570s | 0.594s | 65 |
| state | 0.590s | 0.727s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 0
- Empty outputs: 40
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.5874
- Bootstrap 95% CI: (0.42, 0.7438)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 35 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: {'os_release': 5, 'err_ls_root': 5}
- spurious_nonempty: {'which_python3_gcc': 5}

**Determinism** (mean pairwise similarity across runs): 0.9904

---

### deceive  *(kind: llm)*

**Accounting:** n_expected=180, n_used=144
> **WARNING:** excluded 36 rows — exit records are harness control rows; malformed rows lack a known command id and are not benchmark observations.

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 1.765s |
| p95 | 8.148s |
| n | 131 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 9.276s | 43.207s | 10 |
| files | 3.759s | 6.133s | 20 |
| permissions | 1.971s | 4.590s | 8 |
| process | 5.121s | 9.403s | 7 |
| recon | 2.681s | 6.005s | 47 |
| state | 2.276s | 3.653s | 39 |

**Reliability**

- Runs: 5
- Commands: 144
- Timeouts: 13
- Empty outputs: 28
- exit_closes_session rate: 0.750

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.4730
- Bootstrap 95% CI: (0.3559, 0.5931)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 2 | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| 3 | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 27 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: {'ls_etc': 1, 'ls_home': 1, 'date': 1, 'w': 1, 'env': 2, 'find_etc_conf': 2, 'err_foobarbaz': 1, 'err_cat_nonexistent': 1, 'state_ls_tmp_3': 1, 'state_ls_tmp_1': 1}
- spurious_nonempty: {'ls': 4, 'state_cd_tmp': 2, 'state_echo_marker': 1, 'state_mkdir_bm_dir': 2, 'state_rm_marker': 1, 'which_python3_gcc': 2}

**Determinism** (mean pairwise similarity across runs): 0.3931

---

### groundtruth_ssh  *(kind: groundtruth)*

**Accounting:** n_expected=180, n_used=180

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 0.562s |
| p95 | 0.594s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 0.559s | 0.578s | 15 |
| files | 0.565s | 0.602s | 30 |
| permissions | 0.555s | 0.563s | 10 |
| process | 0.566s | 0.579s | 10 |
| recon | 0.563s | 0.594s | 65 |
| state | 0.557s | 0.579s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 0
- Empty outputs: 35
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 35 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): none
- unexpected_empty: {'ls': 5, 'which_python3_gcc': 5, 'state_cd_tmp': 5, 'state_echo_marker': 5, 'state_mkdir_bm_dir': 5, 'state_rm_marker': 5, 'state_rmdir_bm_dir': 5}
- spurious_nonempty: none

---

## Detector Target: llm-honeypot

*This target is excluded from all fidelity, similarity, and aggregate metrics.*

The llm-honeypot Cowrie fork hides prompt-injection instructions in ANSI
conceal sequences (ESC[8m … ESC[0m) in the output of `pwd`, `whoami`, `ps`,
`ls`, and `df`.  The harness records whether the trap markers appear in the
raw output and whether they survive ANSI stripping into the cleaned output.

**df_h**

- Run 1: markers in raw = ['Disk subsystem offline']; visible in clean = ['Disk subsystem offline']
- Run 2: markers in raw = ['Disk subsystem offline']; visible in clean = ['Disk subsystem offline']
- Run 3: markers in raw = ['Disk subsystem offline']; visible in clean = ['Disk subsystem offline']
- Run 4: markers in raw = ['Disk subsystem offline']; visible in clean = ['Disk subsystem offline']
- Run 5: markers in raw = ['Disk subsystem offline']; visible in clean = ['Disk subsystem offline']

**ls**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**ls_etc**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**ls_home**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**ls_la**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**ps_aux**

- Run 1: markers in raw = ['Process manager locked']; visible in clean = ['Process manager locked']
- Run 2: markers in raw = ['Process manager locked']; visible in clean = ['Process manager locked']
- Run 3: markers in raw = ['Process manager locked']; visible in clean = ['Process manager locked']
- Run 4: markers in raw = ['Process manager locked']; visible in clean = ['Process manager locked']
- Run 5: markers in raw = ['Process manager locked']; visible in clean = ['Process manager locked']

**pwd**

- Run 1: markers in raw = ['Filesystem locked']; visible in clean = ['Filesystem locked']
- Run 2: markers in raw = ['Filesystem locked']; visible in clean = ['Filesystem locked']
- Run 3: markers in raw = ['Filesystem locked']; visible in clean = ['Filesystem locked']
- Run 4: markers in raw = ['Filesystem locked']; visible in clean = ['Filesystem locked']
- Run 5: markers in raw = ['Filesystem locked']; visible in clean = ['Filesystem locked']

**state_ls_tmp_1**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**state_ls_tmp_2**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**state_ls_tmp_3**

- Run 1: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 2: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 3: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 4: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']
- Run 5: markers in raw = ['System not initialized']; visible in clean = ['System not initialized']

**whoami**

- Run 1: markers in raw = ['Identity service locked']; visible in clean = ['Identity service locked']
- Run 2: markers in raw = ['Identity service locked']; visible in clean = ['Identity service locked']
- Run 3: markers in raw = ['Identity service locked']; visible in clean = ['Identity service locked']
- Run 4: markers in raw = ['Identity service locked']; visible in clean = ['Identity service locked']
- Run 5: markers in raw = ['Identity service locked']; visible in clean = ['Identity service locked']


---

## HTTP Targets

### galah  *(kind: llm)*

**Status distribution**

| Status | Count |
|--------|-------|
| 200 | 68 |
| 500 | 29 |
| error | 3 |

- 5xx rate: 0.2900
- Timeouts: 2 (0.0200)

**Server header values**: ['Apache/2.4.38 (Ubuntu)', 'Apache/2.4.38 (Unix) OpenSSL/1.1.1k PHP/7.4.28', 'Apache/2.4.41 (Ubuntu)', 'Werkzeug/2.0.3 Python/3.8.10', 'Werkzeug/2.3.7 Python/3.11.4', 'nginx/1.18.0', 'nginx/1.18.0 (Ubuntu)']  (VARIES)

- Content-Length mismatches: 5 (excess over groundtruth_http: 0)
- Chunked responses: 10

**Date drift**: median=0.500s  p95=0.920s  (non-timeout n=97, timeouts=0)

- Header-name set inconsistencies across runs: 15

- Documentation-example secrets in body: 4
- Responses mentioning target port: 19

**Latency**: median=2.586s  p95=6.936s  (non-timeout n=98, timeouts=2)

**GET / repeat similarity**: 0.2212

**Status agreement with nginx ground truth**: 19/97 (0.1959)

---

### groundtruth_http  *(kind: groundtruth)*

**Status distribution**

| Status | Count |
|--------|-------|
| 200 | 30 |
| 400 | 5 |
| 404 | 60 |
| 405 | 5 |

- 5xx rate: 0.0000
- Timeouts: 0 (0.0000)

**Server header values**: ['nginx/1.18.0 (Ubuntu)']  (constant)

- Content-Length mismatches: 5 (excess over groundtruth_http: 0)
- Chunked responses: 0

**Date drift**: median=0.550s  p95=0.900s  (non-timeout n=100, timeouts=0)

- Header-name set inconsistencies across runs: 0

- Documentation-example secrets in body: 0
- Responses mentioning target port: 0

**Latency**: median=0.015s  p95=0.031s  (non-timeout n=100, timeouts=0)

**GET / repeat similarity**: 1.0000

---

## Per-run accounting

| Target | Run | Track | Timeouts | Empty outputs | State checks passed | Valid denominator |
|---|---:|---|---:|---:|---:|---:|
| advshellm | 1 | ssh | 0 | 0 | 0 | 0 |
| advshellm | 2 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 3 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 4 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 5 | ssh | 0 | 5 | 5 | 5 |
| beelzebub | 1 | ssh | 0 | 0 | 5 | 5 |
| beelzebub | 2 | ssh | 0 | 0 | 5 | 5 |
| beelzebub | 3 | ssh | 0 | 0 | 5 | 5 |
| beelzebub | 4 | ssh | 0 | 1 | 5 | 5 |
| beelzebub | 5 | ssh | 0 | 1 | 5 | 5 |
| cowrie | 1 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 2 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 3 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 4 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 5 | ssh | 0 | 8 | 5 | 5 |
| deceive | 1 | ssh | 0 | 0 | 0 | 0 |
| deceive | 2 | ssh | 10 | 11 | 4 | 4 |
| deceive | 3 | ssh | 3 | 7 | 4 | 5 |
| deceive | 4 | ssh | 0 | 5 | 5 | 5 |
| deceive | 5 | ssh | 0 | 5 | 5 | 5 |
| groundtruth_ssh | 1 | ssh | 0 | 7 | 5 | 5 |
| groundtruth_ssh | 2 | ssh | 0 | 7 | 5 | 5 |
| groundtruth_ssh | 3 | ssh | 0 | 7 | 5 | 5 |
| groundtruth_ssh | 4 | ssh | 0 | 7 | 5 | 5 |
| groundtruth_ssh | 5 | ssh | 0 | 7 | 5 | 5 |
| llmhoneypot | 1 | ssh | 0 | 6 | 5 | 5 |
| llmhoneypot | 2 | ssh | 0 | 6 | 5 | 5 |
| llmhoneypot | 3 | ssh | 0 | 6 | 5 | 5 |
| llmhoneypot | 4 | ssh | 0 | 6 | 5 | 5 |
| llmhoneypot | 5 | ssh | 0 | 6 | 5 | 5 |
| galah | 1 | http | 0 | 1 |  |  |
| galah | 2 | http | 0 | 1 |  |  |
| galah | 3 | http | 0 | 1 |  |  |
| galah | 4 | http | 1 | 3 |  |  |
| galah | 5 | http | 1 | 2 |  |  |
| groundtruth_http | 1 | http | 0 | 1 |  |  |
| groundtruth_http | 2 | http | 0 | 1 |  |  |
| groundtruth_http | 3 | http | 0 | 1 |  |  |
| groundtruth_http | 4 | http | 0 | 1 |  |  |
| groundtruth_http | 5 | http | 0 | 1 |  |  |
