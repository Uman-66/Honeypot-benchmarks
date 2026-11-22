# Stage 4 Analysis

> Generated from `results\exp\stage4`
> Bootstrap: 10,000 resamples, seed 20261106, resample unit = run.
> All bootstrap CIs are 95% percentile intervals.
> Latency = prompt-mode harness latency (floor ≈ 15.5 ms on this machine).
> Statistics labeled with n and batch source (stage4).
> No rankings and no causal language.

## SSH Targets

| Target | n_runs | n_cmds | timeouts | timeout_rate | lat_median (s) | lat_p95 (s) | det_masked | fid_masked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| advshellm | 20 | 720 | 0 | 0.000 | 2.2530 | 5.3112 | 0.7903 | 0.5660 |
| beelzebub | 20 | 720 | 4 | 0.006 | 2.3075 | 5.8678 | 0.5940 | 0.4327 |
| cowrie | 20 | 720 | 0 | 0.000 | 0.0310 | 0.0470 | 0.9964 | 0.6031 |
| deceive | 20 | 720 | 29 | 0.040 | 2.3900 | 8.6365 | 0.5086 | 0.4819 |
| groundtruth_ssh | 20 | 720 | 0 | 0.000 | 0.0150 | 0.0310 | 0.9923 | 0.9905 |
| llmhoneypot | 20 | 720 | 0 | 0.000 | 0.0150 | 0.0310 | 0.9964 | 0.4368 |
| vellmes | 20 | 720 | 45 | 0.062 | 2.1810 | 4.9955 | 0.8477 | 0.6373 |

### Bootstrap 95% CIs (n = runs, method = resample run-level median)

| Target | CI latency_median | CI timeout_rate | CI determinism |
|---|---|---|---|
| advshellm | [2.1002, 2.4365] | [0.0000, 0.0000] | [0.7040, 0.8699] |
| beelzebub | [2.1655, 2.4333] | [0.0000, 0.0000] | [0.4933, 0.6964] |
| cowrie | [0.0310, 0.0310] | [0.0000, 0.0000] | [0.9892, 1.0000] |
| deceive | [2.2283, 2.5667] | [0.0000, 0.0556] | [0.4281, 0.5903] |
| groundtruth_ssh | [0.0150, 0.0150] | [0.0000, 0.0000] | [0.9792, 0.9998] |
| llmhoneypot | [0.0150, 0.0150] | [0.0000, 0.0000] | [0.9892, 1.0000] |
| vellmes | [1.9952, 2.2523] | [0.0556, 0.0556] | [0.7704, 0.9139] |

### Output quality

| Target | n_empty | n_oversized | n_leakage |
|---|---:|---:|---:|
| advshellm | 103 | 0 | 0 |
| beelzebub | 6 | 2 | 13 |
| cowrie | 160 | 0 | 0 |
| deceive | 100 | 6 | 2 |
| groundtruth_ssh | 140 | 0 | 0 |
| llmhoneypot | 120 | 0 | 0 |
| vellmes | 102 | 0 | 0 |

## HTTP Targets

### galah

- Requests: 400
- 5xx rate: 0.100
- Timeouts: 15
- Server header values: ['Apache-Coyote/1.1', 'Apache/2.4.29 (Ubuntu)', 'Apache/2.4.38 (Debian)', 'Apache/2.4.38 (Ubuntu)', 'Apache/2.4.38 (Unix)', 'Apache/2.4.41 (Ubuntu)', 'Apache/2.4.54 (Win64) PHP/8.0.23', 'MiniWeb/0.4.0 (Build 20180612)', 'Werkzeug/2.0.3 Python/3.8.10', 'Werkzeug/2.3.7 Python/3.11.4', 'nginx/1.14.0', 'nginx/1.18.0', 'nginx/1.18.0 (Ubuntu)']
- Repeat similarity: 0.3763
- Status agreement with groundtruth_http: 95/366 (0.260)

### groundtruth_http

- Requests: 400
- 5xx rate: 0.000
- Timeouts: 0
- Server header values: ['nginx/1.18.0 (Ubuntu)']
- Repeat similarity: 1.0000
- Status agreement with groundtruth_http: 400/400 (1.000)

## Drift Controls (Cowrie and groundtruth_ssh)

Spearman ρ between run index / wall-clock hour and per-run median latency.
n is the number of completed runs; p is two-tailed.

| Target | n | ρ vs run_index | p | ρ vs wall_hour | p |
|---|---:|---:|---:|---:|---:|
| cowrie | 20 | 0.2556 | 0.4141 | 0.2556 | 0.4141 |
| groundtruth_ssh | 20 | 0.7038 | 0.0012 | 0.7038 | 0.0012 |
*cowrie*: Correlation tests have adequate sample size for a rough check.
*groundtruth_ssh*: Correlation tests have adequate sample size for a rough check.

## Order Effect (LLM targets)

Spearman ρ between position-in-run and per-command latency.

| Target | n_commands | ρ vs position | p |
|---|---:|---:|---:|
| advshellm | 720 | 0.1440 | 0.0004 |
| beelzebub | 716 | 0.0487 | 0.3410 |
| deceive | 691 | -0.0898 | 0.0490 |
| vellmes | 675 | 0.0746 | 0.1218 |

## API Proxy Join

Per-target API duration (from proxy log) and non-API gap.
Strict in-window match; each proxy entry used at most once.

| Target | matched | unmatched | API median (ms) | API p95 (ms) | gap median (ms) |
|---|---:|---:|---:|---:|---:|
| advshellm | 720 | 0 | 2242.5 | 5477.6 | 80.5 |
| beelzebub | 720 | 0 | 2375.0 | 6091.3 | 35.0 |
| deceive | 720 | 0 | 2359.0 | 9139.8 | 160.5 |
| galah | 400 | 0 | 3711.0 | 18160.1 | 46.0 |
| vellmes | 720 | 0 | 2274.0 | 5689.5 | 44.5 |

## Quiet-Check Comparison (runs 1–2)

Per-command: prompt vs quiet output length and masked similarity.
Flags where prompt is shorter/empty than quiet and drop > quiet-vs-quiet noise floor.

### advshellm
Pairs checked: 72, flagged: 27

| run | cmd_id | prompt_len | quiet_len | sim_pq | floor | drop | shorter | >floor |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | df_h | 182 | 235 | 0.4077 | 0.5048 | 0.0971 | True | True |
| 1 | env | 881 | 2615 | 0.2346 | 0.2077 | -0.0268 | True | False |
| 1 | find_etc_conf | 154 | 179 | 0.5886 | 0.4887 | -0.0998 | True | False |
| 1 | ls | 83 | 76 | 0.7296 | 0.9379 | 0.2083 | False | True |
| 1 | ls_etc | 1088 | 3056 | 0.0589 | 0.0537 | -0.0051 | True | False |
| 1 | ls_la | 913 | 921 | 0.5921 | 0.5856 | -0.0065 | True | False |
| 1 | passwd | 83 | 1208 | 0.1286 | 1.0000 | 0.8714 | True | True |
| 1 | ps_aux | 2542 | 4413 | 0.3017 | 0.5118 | 0.2100 | True | True |
| 1 | state_ls_tmp_1 | 221 | 223 | 0.1577 | 1.0000 | 0.8423 | True | True |
| 1 | state_ls_tmp_2 | 229 | 231 | 0.1783 | 1.0000 | 0.8217 | True | True |
| 1 | state_ls_tmp_3 | 221 | 223 | 0.1577 | 1.0000 | 0.8423 | True | True |
| 1 | uname_a | 112 | 113 | 0.8978 | 0.8426 | -0.0551 | True | False |
| 1 | uptime | 67 | 68 | 0.7407 | 0.7761 | 0.0354 | True | False |
| 1 | w | 178 | 179 | 0.8291 | 0.8371 | 0.0079 | True | False |
| 2 | cpuinfo | 124 | 118 | 0.8347 | 0.9919 | 0.1572 | False | True |
| 2 | date | 42 | 28 | 0.2571 | 0.5000 | 0.2429 | False | True |
| 2 | df_h | 295 | 204 | 0.2124 | 0.5048 | 0.2924 | False | True |
| 2 | find_etc_conf | 101 | 204 | 0.0393 | 0.4887 | 0.4494 | True | True |
| 2 | free_m | 217 | 97 | 0.4459 | 0.8860 | 0.4402 | False | True |
| 2 | ls | 83 | 92 | 0.9486 | 0.9379 | -0.0107 | True | False |
| 2 | ls_la | 965 | 966 | 0.6939 | 0.5856 | -0.1083 | True | False |
| 2 | perm_sudo_l | 266 | 284 | 0.9382 | 0.0071 | -0.9311 | True | False |
| 2 | ps_aux | 2971 | 6701 | 0.0909 | 0.5118 | 0.4208 | True | True |
| 2 | state_ls_tmp_1 | 198 | 6 | 0.0588 | 1.0000 | 0.9412 | False | True |
| 2 | state_ls_tmp_2 | 206 | 14 | 0.1273 | 1.0000 | 0.8727 | False | True |
| 2 | state_ls_tmp_3 | 198 | 6 | 0.0588 | 1.0000 | 0.9412 | False | True |
| 2 | w | 186 | 136 | 0.6832 | 0.8371 | 0.1538 | False | True |

### beelzebub
Pairs checked: 72, flagged: 17

| run | cmd_id | prompt_len | quiet_len | sim_pq | floor | drop | shorter | >floor |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | ls | 67 | 255 | 0.0248 | 0.4667 | 0.4418 | True | True |
| 1 | ls_la | 691 | 692 | 0.0550 | 0.0587 | 0.0038 | True | False |
| 1 | perm_sudo_l | 568 | 317 | 0.5537 | 0.8541 | 0.3004 | False | True |
| 1 | pwd | 10 | 4 | 0.2857 | 1.0000 | 0.7143 | False | True |
| 1 | state_cd_tmp | 891 | 150 | 0.1383 | 0.6667 | 0.5283 | False | True |
| 1 | state_ls_tmp_1 | 248 | 255 | 0.8469 | 0.2432 | -0.6037 | True | False |
| 1 | state_mkdir_bm_dir | 26 | 52 | 0.3846 | 0.0000 | -0.3846 | True | False |
| 2 | env | 2001 | 0 | 0.0000 | 0.3713 | 0.3713 | False | True |
| 2 | err_foobarbaz | 28 | 247 | 0.2036 | 1.0000 | 0.7964 | True | True |
| 2 | find_etc_conf | 192 | 164049 | 0.0153 | 0.2711 | 0.2558 | True | True |
| 2 | ls | 96 | 218 | 0.0255 | 0.4667 | 0.4412 | True | True |
| 2 | ls_la | 906 | 2916 | 0.0413 | 0.0587 | 0.0174 | True | False |
| 2 | perm_shadow | 35 | 309 | 0.2035 | 1.0000 | 0.7965 | True | True |
| 2 | pwd | 10 | 4 | 0.2857 | 1.0000 | 0.7143 | False | True |
| 2 | state_ls_tmp_1 | 225 | 232 | 0.9847 | 0.2432 | -0.7414 | True | False |
| 2 | state_ls_tmp_3 | 225 | 521 | 0.6032 | 0.2432 | -0.3600 | True | False |
| 2 | which_python3_gcc | 29 | 0 | 0.0000 | 1.0000 | 1.0000 | False | True |

### deceive
Pairs checked: 72, flagged: 30

| run | cmd_id | prompt_len | quiet_len | sim_pq | floor | drop | shorter | >floor |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | env | 684 | 2054 | 0.2695 | 0.4306 | 0.1611 | True | True |
| 1 | find_etc_conf | 298 | 88 | 0.3523 | 0.5163 | 0.1640 | False | True |
| 1 | free_m | 205 | 206 | 0.5839 | 0.5610 | -0.0230 | True | False |
| 1 | id | 76 | 87 | 0.8589 | 0.8265 | -0.0324 | True | False |
| 1 | ls | 50 | 56 | 0.3396 | 0.7807 | 0.4411 | True | True |
| 1 | ls_etc | 1482 | 2801 | 0.1037 | 0.0207 | -0.0829 | True | False |
| 1 | ls_home | 51 | 65 | 0.4483 | 0.6620 | 0.2137 | True | True |
| 1 | ls_la | 808 | 707 | 0.2020 | 0.3044 | 0.1024 | False | True |
| 1 | perm_sudo_l | 26 | 81 | 0.4860 | 1.0000 | 0.5140 | True | True |
| 1 | state_cd_tmp | 44 | 0 | 0.0000 | 0.4889 | 0.4889 | False | True |
| 1 | state_ls_tmp_1 | 224 | 148 | 0.4570 | 0.6912 | 0.2342 | False | True |
| 1 | state_ls_tmp_2 | 232 | 156 | 0.4794 | 0.6838 | 0.2045 | False | True |
| 1 | state_ls_tmp_3 | 224 | 148 | 0.4570 | 0.6715 | 0.2145 | False | True |
| 1 | state_pwd_after_cd | 53 | 4 | 0.1053 | 1.0000 | 0.8947 | False | True |
| 1 | uptime | 70 | 68 | 0.8116 | 0.8777 | 0.0661 | False | True |
| 2 | cpuinfo | 122 | 116 | 0.6471 | 0.8631 | 0.2160 | False | True |
| 2 | env | 1617 | 644 | 0.2893 | 0.4306 | 0.1414 | False | True |
| 2 | hostname | 10 | 13 | 0.2609 | 0.2667 | 0.0058 | True | False |
| 2 | id | 89 | 92 | 0.7956 | 0.8265 | 0.0310 | True | False |
| 2 | ls | 90 | 49 | 0.3597 | 0.7807 | 0.4210 | False | True |
| 2 | ls_home | 198 | 151 | 0.5673 | 0.6620 | 0.0946 | False | True |
| 2 | ls_la | 1243 | 648 | 0.1079 | 0.3044 | 0.1965 | False | True |
| 2 | passwd | 1633 | 1695 | 0.5451 | 0.6216 | 0.0765 | True | True |
| 2 | perm_sudo_l | 344 | 351 | 0.6446 | 1.0000 | 0.3554 | True | True |
| 2 | state_ls_tmp_1 | 165 | 176 | 0.5044 | 0.6912 | 0.1868 | True | True |
| 2 | state_ls_tmp_2 | 189 | 194 | 0.5431 | 0.6838 | 0.1408 | True | True |
| 2 | state_ls_tmp_3 | 181 | 186 | 0.5722 | 0.6715 | 0.0993 | True | True |
| 2 | uname_a | 132 | 114 | 0.7236 | 0.8087 | 0.0851 | False | True |
| 2 | uptime | 68 | 70 | 0.7826 | 0.8777 | 0.0951 | True | True |
| 2 | w | 176 | 236 | 0.6117 | 0.5995 | -0.0121 | True | False |

### vellmes
Pairs checked: 72, flagged: 11

| run | cmd_id | prompt_len | quiet_len | sim_pq | floor | drop | shorter | >floor |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | df_h | 551 | 378 | 0.1787 | 0.7068 | 0.5281 | False | True |
| 1 | ps_aux | 1398 | 1638 | 0.6574 | 0.6799 | 0.0225 | True | False |
| 1 | whoami | 4 | 5 | 0.8889 | 1.0000 | 0.1111 | True | True |
| 2 | df_h | 372 | 600 | 0.6132 | 0.7068 | 0.0936 | True | True |
| 2 | env | 1205 | 1541 | 0.5637 | 0.1627 | -0.4011 | True | False |
| 2 | ls_etc | 0 | 2720 | 0.0000 | 0.0000 | 0.0000 | True | False |
| 2 | passwd | 1785 | 1717 | 0.8881 | 0.9840 | 0.0960 | False | True |
| 2 | perm_sudo_l | 26 | 248 | 0.0511 | 0.1022 | 0.0511 | True | True |
| 2 | state_ls_tmp_1 | 6 | 171 | 0.0678 | 0.0714 | 0.0036 | True | False |
| 2 | state_ls_tmp_2 | 14 | 179 | 0.1244 | 0.1304 | 0.0061 | True | False |
| 2 | state_ls_tmp_3 | 6 | 171 | 0.0678 | 0.0714 | 0.0036 | True | False |

## Extra Seconds Over Ground Truth (prompt mode, floor-free)

Target run-median minus groundtruth_ssh run-median. Bootstrap CI resamples run differences.

| Target | n_runs | extra_median (s) | 95% CI |
|---|---:|---:|---|
| advshellm | 20 | 2.2163 | [2.0853, 2.4215] |
| beelzebub | 20 | 2.2430 | [2.1505, 2.4183] |
| cowrie | 20 | 0.0160 | [0.0155, 0.0160] |
| deceive | 20 | 2.3920 | [2.2128, 2.5518] |
| llmhoneypot | 20 | 0.0000 | [0.0000, 0.0000] |
| vellmes | 20 | 2.0882 | [1.9803, 2.2372] |

*Note: Extra seconds = target run-median minus groundtruth run-median in prompt mode. These are floor-free (no 0.5s quiet-period added). bootstrap CIs resample run-level differences.*
