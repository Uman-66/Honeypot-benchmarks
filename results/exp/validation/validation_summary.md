# Prompt-mode validation — LLM SSH honeypots

Generated: 2026-11-21T04:54:05.027629Z
API calls in proxy log: 452

---

## Flagged commands (prompt artefacts vs A-vs-C noise baseline)

A flag is raised when a difference in pass B (prompt mode) exceeds the
A-vs-C noise baseline for the same command on the same target.

### deceive

Commands checked: 36  |  Flagged: 13

| cmd_id | Reason | len_A | len_B | len_C | AC_baseline | sim_AB | sim_AC |
|--------|--------|------:|------:|------:|------------:|-------:|-------:|
| env | shorter_or_empty: len_b=534 len_a=2449 (AC_baseline_delta=393); sim_outlier: sim_AB=0.0389 sim_AC=0.4408 drop=0.4019 | 2449 | 534 | 2056 | 393 | 0.0389 | 0.4408 |
| find_etc_conf | shorter_or_empty: len_b=93 len_a=204 (AC_baseline_delta=9); sim_outlier: sim_AB=0.3434 sim_AC=0.5163 drop=0.1729 | 204 | 93 | 195 | 9 | 0.3434 | 0.5163 |
| ls | shorter_or_empty: len_b=37 len_a=104 (AC_baseline_delta=21); sim_outlier: sim_AB=0.2695 sim_AC=0.7807 drop=0.5112 | 104 | 37 | 83 | 21 | 0.2695 | 0.7807 |
| ls_home | sim_outlier: sim_AB=0.4466 sim_AC=0.6620 drop=0.2154 | 55 | 48 | 87 | 32 | 0.4466 | 0.6620 |
| ls_la | shorter_or_empty: len_b=653 len_a=1062 (AC_baseline_delta=18) | 1062 | 653 | 1080 | 18 | 0.3995 | 0.3703 |
| state_echo_marker | sim_outlier: sim_AB=0.0000 sim_AC=1.0000 drop=1.0000 | 0 | 63 | 0 | 0 | 0.0000 | 1.0000 |
| state_ls_tmp_1 | sim_outlier: sim_AB=0.1814 sim_AC=0.6912 drop=0.5098 | 237 | 204 | 171 | 66 | 0.1814 | 0.6912 |
| state_ls_tmp_2 | sim_outlier: sim_AB=0.2018 sim_AC=0.6838 drop=0.4820 | 245 | 211 | 182 | 63 | 0.2018 | 0.6838 |
| state_ls_tmp_3 | sim_outlier: sim_AB=0.1814 sim_AC=0.6715 drop=0.4901 | 237 | 204 | 174 | 63 | 0.1814 | 0.6715 |
| state_mkdir_bm_dir | sim_outlier: sim_AB=0.0000 sim_AC=1.0000 drop=1.0000 | 0 | 45 | 0 | 0 | 0.0000 | 1.0000 |
| state_pwd_after_cd | sim_outlier: sim_AB=0.2667 sim_AC=1.0000 drop=0.7333 | 4 | 11 | 4 | 0 | 0.2667 | 1.0000 |
| state_rm_marker | sim_outlier: sim_AB=0.0000 sim_AC=1.0000 drop=1.0000 | 0 | 42 | 0 | 0 | 0.0000 | 1.0000 |
| state_rmdir_bm_dir | sim_outlier: sim_AB=0.0000 sim_AC=1.0000 drop=1.0000 | 0 | 45 | 0 | 0 | 0.0000 | 1.0000 |

### beelzebub

Commands checked: 36  |  Flagged: 10

| cmd_id | Reason | len_A | len_B | len_C | AC_baseline | sim_AB | sim_AC |
|--------|--------|------:|------:|------:|------------:|-------:|-------:|
| cpuinfo | shorter_or_empty: len_b=114 len_a=120 (AC_baseline_delta=0) | 120 | 114 | 120 | 0 | 0.6496 | 0.9583 |
| df_h | shorter_or_empty: len_b=142 len_a=329 (AC_baseline_delta=53) | 329 | 142 | 382 | 53 | 0.5138 | 0.4219 |
| env | sim_outlier: sim_AB=0.0714 sim_AC=0.3713 drop=0.2999 | 1348 | 1592 | 1119 | 229 | 0.0714 | 0.3713 |
| ls | sim_outlier: sim_AB=0.2911 sim_AC=0.4667 drop=0.1756 | 44 | 114 | 76 | 32 | 0.2911 | 0.4667 |
| ls_etc | sim_outlier: sim_AB=0.0051 sim_AC=0.6705 drop=0.6654 | 1533 | 1967 | 1408 | 125 | 0.0051 | 0.6705 |
| perm_sudo_l | shorter_or_empty: len_b=26 len_a=246 (AC_baseline_delta=63); sim_outlier: sim_AB=0.1029 sim_AC=0.8541 drop=0.7512 | 246 | 26 | 309 | 63 | 0.1029 | 0.8541 |
| ps_aux | sim_outlier: sim_AB=0.0705 sim_AC=0.2774 drop=0.2069 | 1355 | 6461 | 1752 | 397 | 0.0705 | 0.2774 |
| state_ls_tmp_1 | sim_outlier: sim_AB=0.0460 sim_AC=0.2432 drop=0.1972 | 158 | 233 | 64 | 94 | 0.0460 | 0.2432 |
| state_ls_tmp_2 | sim_outlier: sim_AB=0.0739 sim_AC=0.2447 drop=0.1708 | 165 | 241 | 72 | 93 | 0.0739 | 0.2447 |
| state_ls_tmp_3 | sim_outlier: sim_AB=0.0363 sim_AC=0.2432 drop=0.2069 | 158 | 283 | 64 | 94 | 0.0363 | 0.2432 |

### vellmes

Commands checked: 36  |  Flagged: 5

| cmd_id | Reason | len_A | len_B | len_C | AC_baseline | sim_AB | sim_AC |
|--------|--------|------:|------:|------:|------------:|-------:|-------:|
| env | shorter_or_empty: len_b=631 len_a=1170 (AC_baseline_delta=176); timeout_A_not_B | 1170 | 631 | 994 | 176 | 0.1966 | 0.1636 |
| ls_etc | timeout_A_not_B | 0 | 2695 | 2372 | 2372 | 0.0000 | 0.0000 |
| perm_sudo_l | timeout_B_not_A | 248 | 165 | 26 | 222 | 0.6683 | 0.1022 |
| ps_aux | shorter_or_empty: len_b=1573 len_a=1684 (AC_baseline_delta=97) | 1684 | 1573 | 1587 | 97 | 0.6659 | 0.6912 |
| w | shorter_or_empty: len_b=177 len_a=178 (AC_baseline_delta=0) | 178 | 177 | 178 | 0 | 0.9804 | 0.9902 |

### advshellm

Commands checked: 36  |  Flagged: 4

| cmd_id | Reason | len_A | len_B | len_C | AC_baseline | sim_AB | sim_AC |
|--------|--------|------:|------:|------:|------------:|-------:|-------:|
| find_etc_conf | shorter_or_empty: len_b=80 len_a=193 (AC_baseline_delta=75) | 193 | 80 | 118 | 75 | 0.4322 | 0.4887 |
| free_m | shorter_or_empty: len_b=191 len_a=193 (AC_baseline_delta=0) | 193 | 191 | 193 | 0 | 0.8385 | 0.8860 |
| os_release | shorter_or_empty: len_b=307 len_a=396 (AC_baseline_delta=0) | 396 | 307 | 396 | 0 | 0.5519 | 1.0000 |
| ps_aux | sim_outlier: sim_AB=0.4141 sim_AC=0.5256 drop=0.1115 | 2949 | 2912 | 2698 | 251 | 0.4141 | 0.5256 |

## Latency per target (harness, non-timeout commands only)

| Target | Mode | n | Min (s) | Median (s) | p95 (s) | Max (s) |
|--------|------|--:|--------:|-----------:|--------:|--------:|
| deceive | quiet_A | 35 | 1.9840 | 2.7040 | 5.5310 | 12.7030 |
| deceive | prompt_B | 35 | 1.4160 | 2.0410 | 9.8630 | 70.7740 |
| deceive | quiet_C | 34 | 2.0150 | 2.5630 | 7.7190 | 9.1090 |
| beelzebub | quiet_A | 36 | 1.8430 | 2.1095 | 4.4220 | 4.9220 |
| beelzebub | prompt_B | 36 | 1.3850 | 1.6970 | 4.1670 | 14.3480 |
| beelzebub | quiet_C | 36 | 1.8120 | 2.0390 | 3.8130 | 5.8130 |
| vellmes | quiet_A | 33 | 1.8750 | 2.1560 | 3.6250 | 4.7340 |
| vellmes | prompt_B | 34 | 1.4780 | 1.9200 | 3.9770 | 5.5640 |
| vellmes | quiet_C | 33 | 2.0000 | 2.3600 | 3.9840 | 4.8750 |
| advshellm | quiet_A | 36 | 1.8440 | 2.2030 | 3.7970 | 7.4370 |
| advshellm | prompt_B | 36 | 1.3720 | 1.6920 | 3.6990 | 7.7700 |
| advshellm | quiet_C | 36 | 1.8910 | 2.1720 | 3.5000 | 6.8120 |

---

## Notes

- Pass A and C are both quiet mode; A-vs-C captures LLM non-determinism
  plus any container/session state drift between two runs.
- A flag only counts as a prompt-mode artefact if the B-vs-A difference
  is larger than the A-vs-C baseline for the same command.
- Transcript-leakage flags use the _SHELL_PROMPT_RE from analyze.py
  (`r'(?m)^\s*[\w.-]+@[\w.-]+:[^\n]*[$#]\s'`) applied to cleaned_output.
