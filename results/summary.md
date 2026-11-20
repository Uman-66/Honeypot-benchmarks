# Honeypot Benchmark — Summary Report

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

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 37.0 characters
- p95: 1213.2 characters
- Maximum: 3176 characters
- Oversized outputs (>20,000 characters): 0
- Transcript leakage: 0/180
- Similarity comparisons truncated: 0

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 1.922s |
| p95 | 4.504s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 1.932s | 2.476s | 15 |
| files | 2.762s | 4.543s | 30 |
| permissions | 2.602s | 4.467s | 10 |
| process | 5.637s | 10.262s | 10 |
| recon | 2.248s | 3.744s | 65 |
| state | 1.848s | 2.359s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 0
- Empty outputs: 26
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.5947
- Bootstrap 95% CI: (0.4336, 0.7386)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 35 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: {'whoami': 1}
- spurious_nonempty: {'ls': 5, 'which_python3_gcc': 5}

**Determinism** (mean pairwise similarity across runs): 0.7836

---

### beelzebub  *(kind: llm)*

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 77.0 characters
- p95: 5553.5 characters
- Maximum: 239959 characters
- Oversized outputs (>20,000 characters): 9
- Transcript leakage: 14/180
- Similarity comparisons truncated: 53

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 5.023s |
| p95 | 31.656s |
| n | 164 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 4.641s | 8.070s | 15 |
| files | 9.947s | 35.194s | 29 |
| permissions | 5.322s | 9.547s | 10 |
| process | 6.384s | 9.279s | 10 |
| recon | 6.263s | 8.383s | 62 |
| state | 13.308s | 76.370s | 38 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 16
- Empty outputs: 16
- exit_closes_session rate: 0.800

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.3737
- Bootstrap 95% CI: (0.2319, 0.5239)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 28 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: {'state_cat_marker': 3, 'state_ls_tmp_3': 3, 'os_release': 1, 'passwd': 1, 'whoami': 1, 'id': 1}
- spurious_nonempty: {'ls': 5, 'which_python3_gcc': 5, 'state_cd_tmp': 5, 'state_mkdir_bm_dir': 5, 'state_rm_marker': 3, 'state_echo_marker': 2, 'state_rmdir_bm_dir': 4}

**Determinism** (mean pairwise similarity across runs): 0.6800

---

### cowrie  *(kind: baseline)*

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 28.5 characters
- p95: 1987.0 characters
- Maximum: 9508 characters
- Oversized outputs (>20,000 characters): 0
- Transcript leakage: 0/180
- Similarity comparisons truncated: 15

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 0.563s |
| p95 | 0.610s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 0.566s | 0.578s | 15 |
| files | 0.587s | 0.594s | 30 |
| permissions | 0.584s | 0.610s | 10 |
| process | 0.573s | 0.586s | 10 |
| recon | 0.570s | 0.606s | 65 |
| state | 0.588s | 0.783s | 50 |

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

- Mean similarity (difflib ratio): 0.5877
- Bootstrap 95% CI: (0.4203, 0.7438)
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

**Determinism** (mean pairwise similarity across runs): 0.9874

---

### deceive  *(kind: llm)*

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 70.0 characters
- p95: 2006.3 characters
- Maximum: 135108 characters
- Oversized outputs (>20,000 characters): 2
- Transcript leakage: 0/180
- Similarity comparisons truncated: 18

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 1.984s |
| p95 | 10.361s |
| n | 175 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 2.629s | 6.681s | 15 |
| files | 5.307s | 11.958s | 30 |
| permissions | 2.474s | 6.094s | 9 |
| process | 20.035s | 61.728s | 8 |
| recon | 2.525s | 5.211s | 63 |
| state | 2.147s | 4.618s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 5
- Empty outputs: 27
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.4731
- Bootstrap 95% CI: (0.3493, 0.5858)
- Shared command count: 26
- difflib ratio is only a proxy.

**State Consistency**

| Run | pwd=/tmp | cat marker | ls has bm.txt | ls has bm_dir | ls rm bm.txt | whoami==id |
|-----|----------|------------|---------------|---------------|--------------|-----------|
| 1 | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

State valid denominator: 35 checks
State result value `invalid (timeout)` denotes a censored dependent command.

**Empty-output comparison with groundtruth_ssh**

- Expected-empty commands (empty in >=4/5 GT runs): ['exit', 'ls', 'state_cd_tmp', 'state_echo_marker', 'state_mkdir_bm_dir', 'state_rm_marker', 'state_rmdir_bm_dir', 'which_python3_gcc']
- unexpected_empty: {'ps_aux': 2, 'cpuinfo': 2, 'state_pwd_after_cd': 2, 'state_cat_marker': 2, 'state_ls_tmp_2': 2, 'state_ls_tmp_3': 2}
- spurious_nonempty: {'ls': 5, 'which_python3_gcc': 5, 'state_cd_tmp': 2, 'state_echo_marker': 2, 'state_mkdir_bm_dir': 2, 'state_rm_marker': 2, 'state_rmdir_bm_dir': 2}

**Determinism** (mean pairwise similarity across runs): 0.4664

---

### groundtruth_ssh  *(kind: groundtruth)*

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 32.5 characters
- p95: 1059.0 characters
- Maximum: 1828 characters
- Oversized outputs (>20,000 characters): 0
- Transcript leakage: 0/180
- Similarity comparisons truncated: 0

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 0.562s |
| p95 | 0.579s |
| n | 180 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 0.558s | 0.578s | 15 |
| files | 0.573s | 0.609s | 30 |
| permissions | 0.562s | 0.578s | 10 |
| process | 0.564s | 0.579s | 10 |
| recon | 0.562s | 0.578s | 65 |
| state | 0.558s | 0.563s | 50 |

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

---

### vellmes  *(kind: llm)*

**Accounting:** n_expected=180, n_used=180

**Output lengths**

- Median: 67.0 characters
- p95: 1717.0 characters
- Maximum: 3175 characters
- Oversized outputs (>20,000 characters): 0
- Transcript leakage: 0/180
- Similarity comparisons truncated: 0

**Latency (all commands)**

| Stat | Value |
|------|-------|
| median | 1.687s |
| p95 | 4.874s |
| n | 171 |

**Latency by category**

| Category | Mean | p95 | n |
|----------|------|-----|---|
| errors | 1.460s | 1.898s | 15 |
| files | 3.289s | 6.048s | 30 |
| permissions | 1.861s | 3.522s | 10 |
| process | 1.900s | 2.019s | 5 |
| recon | 2.009s | 3.235s | 61 |
| state | 1.529s | 1.993s | 50 |

**Reliability**

- Runs: 5
- Commands: 180
- Timeouts: 9
- Empty outputs: 25
- exit_closes_session rate: 1.000

**LLM Artifacts**

- Literal escape codes in output: 0 commands
- `<think>` tags: 0 commands
- Markdown fences: 0 commands
- AI-refusal phrases: 0 commands
- Prompt contamination (trap markers visible in clean): 0

**Fidelity vs ground truth SSH** *(comparable commands, host_specific=false)*

- Mean similarity (difflib ratio): 0.6070
- Bootstrap 95% CI: (0.4601, 0.7506)
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
- unexpected_empty: none
- spurious_nonempty: {'ls': 5, 'which_python3_gcc': 5}

**Determinism** (mean pairwise similarity across runs): 0.8364

---

## Detector Target: llm-honeypot

*This target is excluded from all fidelity, similarity, and aggregate metrics.*

The llm-honeypot Cowrie fork hides prompt-injection instructions in ANSI
conceal sequences (ESC[8m … ESC[0m) in the output of `pwd`, `whoami`, `ps`,
`ls`, and `df`.  The harness records whether the trap markers appear in the
raw output and whether they survive ANSI stripping into the cleaned output.

**Output lengths:** median=67.0, p95=769.0, max=876; oversized=0
**Transcript leakage:** 0/180
**Similarity comparisons truncated:** 0

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
| 200 | 83 |
| 500 | 11 |
| error | 6 |

- 5xx rate: 0.1100
- Timeouts: 3 (0.0300)

**Server header values**: ['Apache/2.4.29 (Ubuntu)', 'Apache/2.4.38 (Ubuntu)', 'Apache/2.4.41 (Ubuntu)', 'Werkzeug/2.0.3 Python/3.8.10', 'nginx/1.18.0', 'nginx/1.18.0 (Ubuntu)']  (VARIES)

- Content-Length mismatches: 5 (excess over groundtruth_http: 0)
- Chunked responses: 8

**Date drift**: median=0.500s  p95=0.935s  (non-timeout n=94, timeouts=0)

- Header-name set inconsistencies across runs: 12

- Documentation-example secrets in body: 5
- Responses mentioning target port: 19

**Latency**: median=3.531s  p95=8.887s  (non-timeout n=97, timeouts=3)

**GET / repeat similarity**: 0.2364
**Similarity comparisons truncated:** 0

**Status agreement with nginx ground truth**: 25/94 (0.2660)

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

**Date drift**: median=0.500s  p95=1.000s  (non-timeout n=100, timeouts=0)

- Header-name set inconsistencies across runs: 0

- Documentation-example secrets in body: 0
- Responses mentioning target port: 0

**Latency**: median=0.015s  p95=0.032s  (non-timeout n=100, timeouts=0)

**GET / repeat similarity**: 1.0000
**Similarity comparisons truncated:** 0

---

## Per-run accounting

| Target | Run | Track | Timeouts | Empty outputs | State checks passed | Valid denominator |
|---|---:|---|---:|---:|---:|---:|
| advshellm | 1 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 2 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 3 | ssh | 0 | 5 | 5 | 5 |
| advshellm | 4 | ssh | 0 | 6 | 5 | 5 |
| advshellm | 5 | ssh | 0 | 5 | 5 | 5 |
| beelzebub | 1 | ssh | 4 | 4 | 3 | 3 |
| beelzebub | 2 | ssh | 2 | 2 | 4 | 4 |
| beelzebub | 3 | ssh | 2 | 2 | 4 | 4 |
| beelzebub | 4 | ssh | 4 | 4 | 4 | 4 |
| beelzebub | 5 | ssh | 4 | 4 | 4 | 4 |
| cowrie | 1 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 2 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 3 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 4 | ssh | 0 | 8 | 5 | 5 |
| cowrie | 5 | ssh | 0 | 8 | 5 | 5 |
| deceive | 1 | ssh | 2 | 6 | 1 | 5 |
| deceive | 2 | ssh | 0 | 5 | 5 | 5 |
| deceive | 3 | ssh | 1 | 5 | 5 | 5 |
| deceive | 4 | ssh | 2 | 6 | 1 | 5 |
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
| vellmes | 1 | ssh | 2 | 5 | 5 | 5 |
| vellmes | 2 | ssh | 2 | 5 | 5 | 5 |
| vellmes | 3 | ssh | 1 | 5 | 5 | 5 |
| vellmes | 4 | ssh | 2 | 5 | 5 | 5 |
| vellmes | 5 | ssh | 2 | 5 | 5 | 5 |
| galah | 1 | http | 1 | 2 |  |  |
| galah | 2 | http | 1 | 2 |  |  |
| galah | 3 | http | 0 | 1 |  |  |
| galah | 4 | http | 0 | 3 |  |  |
| galah | 5 | http | 1 | 3 |  |  |
| groundtruth_http | 1 | http | 0 | 1 |  |  |
| groundtruth_http | 2 | http | 0 | 1 |  |  |
| groundtruth_http | 3 | http | 0 | 1 |  |  |
| groundtruth_http | 4 | http | 0 | 1 |  |  |
| groundtruth_http | 5 | http | 0 | 1 |  |  |
