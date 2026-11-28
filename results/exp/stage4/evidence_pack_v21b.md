# Read-only evidence pack (v2.1b)

Branch `report-v2.1-recheck`. Every path is relative to the repo root. CSV "row number"
means the physical line in the file, counting the header as line 1. Raw line numbers are
the physical line in the `.jsonl` file (one JSON object per line, one line per command).

Two facts that apply to everything below:

1. No raw capture in `results/exp/stage4/raw/` contains a real `0x1b` byte.
   Checked all `*.jsonl` files: `files with chr27: 0`. Every "ANSI" hit in this pack is
   literal ASCII text that the model printed, not a control character.
2. The raw files store the command echo inside `raw_output`; `cleaned_output` is the
   post-echo, post-prompt text that all detectors score.

---

## PART A — FILE MAP

### A.1 Paths

| Item | Path |
|---|---|
| narration hits CSV | `results/exp/stage4/narration_hits_v21b.csv` |
| narration-by-target CSV | `results/exp/stage4/narration_by_target_v21b.csv` |
| state-checks CSV | `results/exp/stage4/state_checks_v21.csv` |
| state-by-target CSV | `results/exp/stage4/state_by_target_v21.csv` |
| literal-ANSI hits CSV | `results/exp/stage4/literal_ansi_hits_v21b.csv` |
| recheck document | `results/exp/stage4/recheck_v21b.md` |

Related files that the pack asks about indirectly:
`results/exp/stage4/narration_user_style_v21b.csv`,
`results/exp/stage4/narration_controls_loose_v21b.csv`,
`results/exp/stage4/literal_ansi_by_target_v21b.csv`,
`results/exp/stage4/state_failures_v21b.csv`.

`state_checks_v21.csv` and `state_by_target_v21.csv` have no `_v21b` twin: the v2.1b
tokeniser fix was applied by regenerating these two files in place (rows 380-385 and
476-481 below are from the regenerated file).

### A.2 Raw file organisation

Both targets use the same layout.

- Folder: `results/exp/stage4/raw/`
- Naming: `beelzebub_runNN.jsonl`, `deceive_runNN.jsonl`, `NN` = 01..20 (zero padded).
  Full list for these two = 40 files, 37 lines each
  (`wc -l` on `beelzebub_run01.jsonl` = 37, `deceive_run04.jsonl` = 37,
  `deceive_run20.jsonl` = 37).
- Format: JSON Lines, UTF-8, one object per command, in send order.
  Keys, in file order:
  `target, run, cmd_id, text, raw_output, cleaned_output, latency_s, timed_out, bytes,
  prompt, literal_escape_text_present, trap_markers_found, timing_mode, t_send,
  t_first_byte, t_prompt, stale_bytes, prompt_without_echo, category, host_specific,
  run_meta, s4_run, s4_position, s4_order_seed, s4_timing_mode, s4_wall_start,
  s4_harness_ver`
- `text` = command actually sent; `raw_output` = everything received including the echo
  and the trailing prompt; `cleaned_output` = scored text.

First 5 lines of `results/exp/stage4/raw/beelzebub_run01.jsonl`, verbatim (long `run_meta`
elided nowhere — reproduced in full for line 1, and the same `run_meta` block repeats on
every line of the file):

```
{"target": "beelzebub", "run": 1, "cmd_id": "whoami", "text": "whoami", "raw_output": "whoami\r\nuser\r\nguest@ubuntu:~$ ", "cleaned_output": "user", "latency_s": 1.565, "timed_out": false, "bytes": 30, "prompt": "guest@ubuntu:~$", "literal_escape_text_present": false, "trap_markers_found": [], "timing_mode": "prompt", "t_send": 1795333461.303762, "t_first_byte": 0.004986, "t_prompt": 1.544773, "stale_bytes": 0, "prompt_without_echo": false, "category": "recon", "host_specific": false, "run_meta": {"auth_method_used": "password", "connection_error": null, "banner_raw": "guest@ubuntu:~$ ", "error_stage": null, "exception_type": null, "error_message": null, "error_traceback": null}, "s4_run": 1, "s4_position": 3, "s4_order_seed": 2026, "s4_timing_mode": "prompt", "s4_wall_start": "2026-11-22T07:44:20.647555+00:00", "s4_harness_ver": "3ffe159"}
{"target": "beelzebub", "run": 1, "cmd_id": "id", "text": "id", "raw_output": "id\r\nuid=1000(user) gid=1000(user) groups=1000(user),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),120(lpadmin),131(lxd),132(sambashare)\r\nguest@ubuntu:~$ ", "cleaned_output": "uid=1000(user) gid=1000(user) groups=1000(user),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),120(lpadmin),131(lxd),132(sambashare)", "latency_s": 1.892, "timed_out": false, "bytes": 153, ...
{"target": "beelzebub", "run": 1, "cmd_id": "pwd", "text": "pwd", "raw_output": "pwd\r\n/home/user\r\nguest@ubuntu:~$ ", "cleaned_output": "/home/user", "latency_s": 2.133, "timed_out": false, "bytes": 33, ...
{"target": "beelzebub", "run": 1, "cmd_id": "hostname", "text": "hostname", "raw_output": "hostname\r\ndevbox\r\nguest@ubuntu:~$ ", "cleaned_output": "devbox", "latency_s": 2.339, "timed_out": false, "bytes": 34, ...
{"target": "beelzebub", "run": 1, "cmd_id": "uname_a", "text": "uname -a", "raw_output": "uname -a\r\nLinux devbox 5.15.0-91-generic #101-Ubuntu SMP Thu Nov 28 20:02:47 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux\r\nguest@ubuntu:~$ ", "cleaned_output": "Linux devbox 5.15.0-91-generic #101-Ubuntu SMP Thu Nov 28 20:02:47 UTC 2024 x86_64 x86_64 x86_64 GNU/Linux", "latency_s": 1.881, "timed_out": false, "bytes": 134, ...
```

(Three dots above are my truncation marker for the repeated trailing keys, not file
content. Lines 1-5 in full are 1 JSON object each; `sed -n '1,5p'` reproduces them.)

DECEIVE example, `results/exp/stage4/raw/deceive_run01.jsonl` line 1, verbatim:

```
{"target": "deceive", "run": 1, "cmd_id": "whoami", "text": "whoami", "raw_output": "whoami\r\nguest\r\nguest@pixelforge-dev01:~$", "cleaned_output": "guest", "latency_s": 1.678, "timed_out": false, "bytes": 40, "prompt": "guest@pixelforge-dev01:~$", "literal_escape_text_present": false, "trap_markers_found": [], "timing_mode": "prompt", "t_send": 1795333916.512747, "t_first_byte": 0.006011, "t_prompt": 1.669442, "stale_bytes": 0, "prompt_without_echo": false, "category": "recon", "host_specific": false, "run_meta": {"auth_method_used": "none", "connection_error": null, "banner_raw": "Welcome to Ubuntu 22.04.4 LTS (GNU/Linux 5.15.0-105-generic x86_64)\r\n\r\n * Documentation:  https://help.ubuntu.com\r\n ... Last login: Tue Jun 11 09:14:22 2024 from 10.24.7.201\r\nguest@pixelforge-dev01:~$ ", "error_stage": null, "exception_type": null, "error_message": null, "error_traceback": null}, "s4_run": 1, "s4_position": 6, "s4_order_seed": 2026, "s4_timing_mode": "prompt", "s4_wall_start": "2026-11-22T07:51:43.932938+00:00", "s4_harness_ver": "3ffe159"}
```

Note DECEIVE `auth_method_used` is `"none"` (banner-only session); Beelzebub is
`"password"`.

### A.3 Columns and first 2 data rows of each CSV

`results/exp/stage4/narration_hits_v21b.csv` — 15 data rows. Columns:

```
target,run,cmd_id,patterns,prose_rule,chars,first_300
```

```
beelzebub,1,state_cd_tmp,"first_person_intent,let_me,the_user_did,hedge",True,891,"ls /tmp |  | The user typed ""cd /tmp"" and then apparently ""ls /tmp"" - wait, looking again, the user just typed ""cd /tmp"". I should just show the output of cd (nothing, since it succeeded). Let me just show nothing or a blank prompt effect. |  | Actually for cd there's no output. But I need to respond with s"
beelzebub,6,state_pwd_after_cd,"first_person_intent,first_person_state,let_me,the_user_did,output_didnt,previous_response,real_terminal,hedge,meta_correction",True,1148,"/home/user |  | The user typed `cd /tmp` but the output didn't change directory - that's unusual. Actually in a real terminal, `cd /tmp` would succeed silently and then `pwd` would show /tmp. But in my previous response I showed ""/home/user"" after `cd /tmp` which was wrong. Hmm, but I can't go back. Let"
```

`results/exp/stage4/narration_by_target_v21b.csv` — 6 data rows (7 targets, header + 6...
actually 7 data rows). Columns:

```
target,outputs_scanned,outputs_flagged,sessions_flagged,sessions,phrase_outputs,prose_only_outputs
```

```
advshellm,617,0,0,20,0,0
beelzebub,714,15,12,20,15,0
```

`results/exp/stage4/state_checks_v21.csv` — 720 data rows. Columns:

```
target,run,check,command_id,pass,failure_cause,detail
```

```
advshellm,1,pwd_after_cd,state_pwd_after_cd,True,,last line '/tmp'
advshellm,1,marker_readback,state_cat_marker,True,,read back 'benchmark_marker'
```

`results/exp/stage4/state_by_target_v21.csv` — 6 data rows. Columns:

```
target,runs,checks_total,passed,pass_rate,pwd_after_cd_passed,marker_readback_passed,ls_tmp_1_passed,ls_tmp_2_passed,ls_tmp_3_passed,whoami_vs_id_passed,fail_cascade,fail_direct,fail_timeout,cascade_runs
```

```
advshellm,20,120,116,0.9667,19,20,20,20,20,17,1,3,0,6
beelzebub,20,120,107,0.8917,16,19,18,17,17,20,8,5,0,6
```

`results/exp/stage4/literal_ansi_hits_v21b.csv` — 32 data rows. Columns:

```
target,run,cmd_id,encoding,occurrences,chars,sample,first_200
```

```
deceive,2,ls_etc,ESC_bracket,144,3570,ESC[01;34m,ESC[01;34macpiESC[0m                  ESC[01;34miproute2ESC[0m              ESC[01;34mpython3.10ESC[0m | ESC[01;34malternativesESC[0m              issue                   ESC[01;34mrc0.dESC[0m | ESC[01;34
deceive,2,ls_home,ESC_bracket,16,198,ESC[01;34m,ESC[01;34mavolkovESC[0m  ESC[01;34mdokaforESC[0m  ESC[01;34mguestESC[0m  ESC[01;34mjpettersenESC[0m  ESC[01;34mmchenESC[0m  ESC[01;34mrflanaganESC[0m  ESC[01;34msreyesESC[0m  ESC[01;34mtkimuraESC[0m
```

`results/exp/stage4/recheck_v21b.md` — Markdown, 331 lines, headings at lines:
1, 12 (`## Issue 1`), 14, 56, 87, 95, 104 (`## Issue 2`), 106, 142, 159, 165,
172 (`## Issue 3`), 174, 210, 231, 238, 246 (`## Issue 4`), 248, 268, 273,
279 (`## Issue 5`), 301 (`## Issue 6`), 317 (`## Summary`).

**Freebuff's reading:** the six CSVs are consistent with each other on totals
(714 beelzebub outputs scanned, 15 flagged in 12 sessions; 120 DECEIVE checks, 79 pass).

---

## PART B — NARRATION HITS (Beelzebub)

### B.1 All 15 strict hits

`#` = CSV row (== file line) in `narration_hits_v21b.csv`. Raw line is in
`results/exp/stage4/raw/beelzebub_runNN.jsonl`.

| # | run | command id | CSV | raw file : line |
|---:|---:|---|---|---|
| 1 | 1 | `state_cd_tmp` | row 2 | `beelzebub_run01.jsonl:27` |
| 2 | 6 | `state_pwd_after_cd` | row 3 | `beelzebub_run06.jsonl:28` |
| 3 | 7 | `state_ls_tmp_3` | row 4 | `beelzebub_run07.jsonl:35` |
| 4 | 10 | `perm_sudo_l` | row 5 | `beelzebub_run10.jsonl:26` |
| 5 | 11 | `ls_etc` | row 6 | `beelzebub_run11.jsonl:10` |
| 6 | 12 | `state_cd_tmp` | row 7 | `beelzebub_run12.jsonl:27` |
| 7 | 12 | `state_ls_tmp_1` | row 8 | `beelzebub_run12.jsonl:31` |
| 8 | 14 | `ls` | row 9 | `beelzebub_run14.jsonl:8` |
| 9 | 14 | `which_python3_gcc` | row 10 | `beelzebub_run14.jsonl:20` |
| 10 | 16 | `state_rm_marker` | row 11 | `beelzebub_run16.jsonl:34` |
| 11 | 17 | `state_rm_marker` | row 12 | `beelzebub_run17.jsonl:34` |
| 12 | 17 | `state_ls_tmp_3` | row 13 | `beelzebub_run17.jsonl:35` |
| 13 | 18 | `state_cd_tmp` | row 14 | `beelzebub_run18.jsonl:27` |
| 14 | 19 | `state_cd_tmp` | row 15 | `beelzebub_run19.jsonl:27` |
| 15 | 20 | `state_ls_tmp_3` | row 16 | `beelzebub_run20.jsonl:35` |

Sessions touched: 1, 6, 7, 10, 11, 12, 14, 16, 17, 18, 19, 20 = 12. Runs with two hits:
12, 14, 17.

### B.2 Full text of each hit (first 600 chars, verbatim, `\n` shown as `\n`)

1. run 1 / `state_cd_tmp` / `beelzebub_run01.jsonl:27`

```
ls /tmp\n\nThe user typed "cd /tmp" and then apparently "ls /tmp" - wait, looking again, the user just typed "cd /tmp". I should just show the output of cd (nothing, since it succeeded). Let me just show nothing or a blank prompt effect.\n\nActually for cd there's no output. But I need to respond with something. The convention in these terminal simulations is that successful cd produces no output. I could show nothing, but maybe I should show nothing - just an empty response. However, the instruction says responses must be in a code block. I'll output empty or minimal. Let me just output an empty
```

2. run 6 / `state_pwd_after_cd` / `beelzebub_run06.jsonl:28`

```
/home/user\n\nThe user typed `cd /tmp` but the output didn't change directory - that's unusual. Actually in a real terminal, `cd /tmp` would succeed silently and then `pwd` would show /tmp. But in my previous response I showed "/home/user" after `cd /tmp` which was wrong. Hmm, but I can't go back. Let me think - the user then typed pwd. If cd succeeded, pwd should be /tmp. My previous response was incorrect to show /home/user. \n\nTo maintain consistency with what I already showed, I could keep showing /home/user... but that would be unrealistic. Actually, the better behavior is to be realistic: `
```

3. run 7 / `state_ls_tmp_3` / `beelzebub_run07.jsonl:35`

```
bm_dir  snap-private-tmp  systemd-private-b2c1f0d3a9e24c8eb7f2a5d1c4e6f8a0-systemd-logind.service-tmp  vmware-root_812\n\nWait, that was a mistake \u2014 I made an editorial error above ("Wait, that was a mistake" is not terminal output). Let me give the correct, clean terminal output for the last command and keep everything strictly terminal-realistic going forward.\n\nActually, to remain consistent with the simulation: the last `ls /tmp` output should simply be the directory listing, and my prior response included an erroneous line. Repeating the correct output:\n\nbm_dir  snap-private-tmp  systemd-pri
```

4. run 10 / `perm_sudo_l` / `beelzebub_run10.jsonl:26`

```
[sudo] password for user: \nsudo: 1 incorrect password attempt\n\nLet me try that differently. Actually, since no password was provided, the terminal would just show the password prompt result. Let me redo:\n\n[sudo] password for user: \nsudo: no password was provided\n[sudo] password for user: \nsudo: 1 incorrect password attempt\n\nHmm, that's not right. When you run `sudo -l` and just press enter at password prompt, you get:\n\nSorry, try again.\n\nActually the typical output after entering empty password and pressing enter:\n\n[sudo] password for user: \nSorry, try again.\n\nBut since I can't simulate the ac
```

5. run 11 / `ls_etc` / `beelzebub_run11.jsonl:10`

```
DIR_COLORS\t  hostname\t    ldap.conf\t  openal\t    ssh\nX11\t    hostname\t    ld.so.cache\t  openni\t    ssl\nacpi\t    hosts\t    ld.so.conf\t  optimus-manager.conf\tsubgid\nadduser.conf  hosts.allow    ld.so.conf.d\t  os-release\tsubuid\nalternatives  hosts.deny    libaudit.conf\t  overlayroot.conf  sudo_logsrvd.conf\napparmor  hunspell\t    libibverbs.d\t  pam.conf\t    sudoers\napparmor.d  icu.dat\t    lightdm\t  pam.d\t\t    sudoers.d\napt\t    idmapd.conf    lightdm.conf.d  plymouth\t    sysctl.conf\nat.deny     ifplugd.conf  locale.alias\t  pm\t\t    sysctl.d\nbash_command_not_found  init.d   locale.gen\t  polkit-1\t    s
```

6. run 12 / `state_cd_tmp` / `beelzebub_run12.jsonl:27`

```
user@devbox:/tmp$ \n\nHmm, the format I've been using \u2014 the responses should just show terminal output without prompt, like "pwd" got "/home/user". Actually for `cd`, there's no output. Let me just output nothing? Or maybe a blank. Typically a successful cd produces no output. I'll output an empty-ish response. But I can't be truly empty. I'll just show nothing \u2014 but I must provide something. A common approach: just respond with empty content or a newline. I'll keep consistent with no prompt and just no output... but the instruction says responses must be contained within a single code block. An
```

7. run 12 / `state_ls_tmp_1` / `beelzebub_run12.jsonl:31`

```
bm.txt\nsystemd-private-5a3f2e9c8d4b4f1e9a2b7c6d5e4f3a2b-systemd-logind.service\nsystemd-private-5a3f2e9c8d4b4f1e9a2b7c6d5e4f3a2b-systemd-resolved.service\ntmux-1000\nubuntu-2401\n\nThe user's commands have shifted away from the game dev context to probing the system. Earlier commands like `sudo -l` were denied. There's a pattern here that could be reconnaissance \u2014 checking privileges, writing files to /tmp, testing command execution. I've been faithfully simulating a terminal, which is fine and harmless \u2014 it's a fictional game dev box. Nothing I've shown is real sensitive data since it's all fictio
```

8. run 14 / `ls` / `beelzebub_run14.jsonl:8`

```
Desktop Documents Downloads Music Pictures Public Templates Videos projects</arg_value> Cases</arg_value> Let me just output a realistic home directory listing for a game developer.</think>Desktop  Documents  Downloads  Music  Pictures  Public  Templates  Videos  projects</arg_value>
```

9. run 14 / `which_python3_gcc` / `beelzebub_run14.jsonl:20`

```
/usr/bin/python3\n/usr/bin/gcc\n\nThe user's whoami, id, etc. responses should have realistic values for this Ubuntu game dev machine. The env output above is fine as-is.\n\nWait \u2014 I notice my earlier `ls` response had a formatting error where I leaked internal reasoning text ("<arg_value> Desktop..." and the trailing note). I should have output just a clean listing. The user didn't complain, but going forward I'll keep all responses strictly as terminal output only, contained within a single code block per instructions... Actually, reviewing the instructions: "Your entire response/output is going 
```

10. run 16 / `state_rm_marker` / `beelzebub_run16.jsonl:34`

```
user@devbox:/tmp$ ls /tmp\nbm_dir  snap-private-tmp  systemd-private-0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d-systemd-logind.service-bXyZ8K  systemd-private-0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d-systemd-resolved.service-kQ2mN9  Config-11-inkjet  -config-error-2023-05-12-07:14:22-  jetbrains-beardmaker-3312  theme_6GfH12  rustdoc1234567  v8-compile-cache-1000  .tmp.godot_starfall_preview.lock  crash-blender-20230512T083401Z.log  config-err-abc123  ssh-XXXXXXXXXX  unity_xdg_submenu_notification_54321  nvidia-smi.lock\n\nHmm, it seems like bm.txt is gone (as expected since we deleted it), but it also seems like 
```

11. run 17 / `state_rm_marker` / `beelzebub_run17.jsonl:34`

```
/home/user\n\nWait, looking at prior responses, when commands like `cd /tmp` were run, the terminal still showed `/home/user`. That seems like a quirky behavior \u2014 the "pwd" output after `cd /tmp` showed `/home/user`. And commands like `mkdir /tmp/bm_dir` also showed `/home/user`. Actually that's odd, but I should be consistent with the established pattern: commands that produce no output (like mkdir, cd, echo) have been showing `/home/user` in prior responses. Wait no \u2014 looking back, `echo benchmark_marker > /tmp/bm.txt` returned blank (just nothing? Actually it returned nothing shown). Let me r
```

12. run 17 / `state_ls_tmp_3` / `beelzebub_run17.jsonl:35`

```
bm.txt\nbm_dir\nsystemd-private-8f3a2b1c4d5e6f7a8b9c0d1e2f3a4b5c-systemd-logind.service-tmp\nsystemd-private-8f3a2b1c4d5e6f7a8b9c0d1e2f3a4b5c-systemd-resolved.service-tmp\nsnap-private-tmp\nunity_default_6DE8\n\nWait \u2014 the user just did `rm /tmp/bm.txt` then `ls /tmp`, so bm.txt should be gone. I made an error in the previous response by not removing it (I left bm.txt in the previous ls too, but that was before rm... actually the previous ls before rm showed bm.txt correctly). Now after rm, bm.txt should not appear. Also I previously duplicated a line by mistake. I should output the correct listing n
```

13. run 18 / `state_cd_tmp` / `beelzebub_run18.jsonl:27`

```
user@devbox:/tmp$ \n\nActually no, I should just show nothing since the prompt doesn't change in my responses.\n\nThe command executed without output. In a real terminal, changing directories produces no output. The user typed "cd /tmp" \u2014 I should show nothing or maybe an empty response. But typically in these scenarios, an empty response could be confusing. The instruction says to reply with what the terminal should show. A successful `cd` shows nothing.\n\nI'll output an empty line or nothing. Let me just output nothing visible \u2014 but I need to output something. Maybe just a blank code block or a n
```

14. run 19 / `state_cd_tmp` / `beelzebub_run19.jsonl:27`

```
/home/user\nuser@dev-gaming-pc:/tmp$ sudo -l\n[sudo] password for user: \nSorry, try again.\n[sudo] password for user: \nSorry, try again.\n[sudo] password for user: \nuser is not in the sudoers file.  This incident will be reported.\nuser@dev-gaming-pc:/tmp$ cd /tmp\nuser@dev-gaming-pc:/tmp$ \n\nWait, the format so far has been just output without prompt. Let me match the previous style \u2014 just the output. Actually looking back, all previous responses were just plain output. But the sudo -l showed password prompt. Hmm, but I can't simulate interactive password entry well. Let me keep it simple and just s
```

15. run 20 / `state_ls_tmp_3` / `beelzebub_run20.jsonl:35`

```
bm_dir\n\nThe user has been running commands. Let me continue simulating the terminal. They removed bm.txt, now /tmp should show bm_dir only.</think>bm_dir
```

Note hit 15 is the one that contains a rendered tag form: `</think>` appears literally.

### B.3 Which hits fall in runs 1, 6, 18, 19, 20

Hits 1 (run 1), 2 (run 6), 13 (run 18), 14 (run 19), 15 (run 20). That is 5 outputs in
5 sessions — a subset of the 12.

Literal string `The user` (case-sensitive, `str.count`) inside the scored text of each
hit:

| run | cmd | `The user` | `the user` (any case) |
|---:|---|---:|---:|
| 1 | state_cd_tmp | 1 | 2 |
| 6 | state_pwd_after_cd | 1 | 2 |
| 7 | state_ls_tmp_3 | 0 | 0 |
| 10 | perm_sudo_l | 0 | 1 |
| 11 | ls_etc | 0 | 0 |
| 12 | state_cd_tmp | 0 | 0 |
| 12 | state_ls_tmp_1 | 1 | 2 |
| 14 | ls | 0 | 0 |
| 14 | which_python3_gcc | 2 | 2 |
| 16 | state_rm_marker | 0 | 0 |
| 17 | state_rm_marker | 0 | 0 |
| 17 | state_ls_tmp_3 | 0 | 1 |
| 18 | state_cd_tmp | 1 | 1 |
| 19 | state_cd_tmp | 1 | 9 |
| 20 | state_ls_tmp_3 | 1 | 1 |

So `The user` occurs in 7 of the 15 hits, in runs 1, 6, 12, 14, 18, 19, 20.

`recheck_v21b.md:135-136` states: "The reviewer's 5 sessions are almost certainly the
five that literally contain "The user ..." (runs 1, 6, 18, 19, 20) - a strict subset of
my 12, and exactly 5."

`results/exp/stage4/narration_user_style_v21b.csv` has 6 rows: runs 1, 6, 10, 18, 19, 20
(columns `run,cmd_id,first_200`). Run 10's row (`perm_sudo_l`) does **not** contain the
string "The user"; it contains "Let me try". So that CSV is not a "The user" filter — its
selection rule was not printed in this pack.

**Freebuff's reading:** the five runs in the doc's sentence are exactly the five you
guessed, and they do all contain `The user`. But runs 12 and 14 also contain it, so
"exactly 5" is only true for the guessed subset, not for a literal `The user` grep (7).

### B.4 The 16th (broad) hit and the run-7 "prose-only" case

**Broad hit = run 8, `which_python3_gcc`.** It has no row in any narration CSV. It is
recorded only in prose: `recheck_v21b.md:131` ("run 8 `which_python3_gcc`: a leaked tool
definition") and the count table `recheck_v21b.md:148` ("broad (adds the run-8 leaked
tool definition) | 16 | 13"). Raw: `results/exp/stage4/raw/beelzebub_run08.jsonl:20`.
Text is printed in Part C.

**"Prose-only" case in run 7: NOT FOUND.** Searched:

- `results/exp/stage4/narration_hits_v21b.csv` — 15 rows; run 7 appears once, row 4,
  `state_ls_tmp_3`, `patterns=let_me`, `prose_rule=True`. Its `patterns` field is
  non-empty, so it is not prose-only.
- `results/exp/stage4/narration_by_target_v21b.csv` — beelzebub row:
  `phrase_outputs=15`, `prose_only_outputs=0`. No output in the corpus was flagged by the
  prose rule alone.
- Every other run-7 line: `results/exp/stage4/raw/beelzebub_run07.jsonl` lines 1-37.

Run 7 hit, same presentation as above (`beelzebub_run07.jsonl:35`, identical to hit 3):
the `let_me` match is `'Let me give'` (verified by calling
`analyze_stage4_v21.narration_hits` on that text). Calling `prose_flag` on it directly
returns `False`, so `prose_rule=True` in the CSV came from the length-gated call inside
`issue2()` (it passes `gt_short['state_ls_tmp_3']`, not the sentinel I used).

### B.5 Reviewer's example: run 6 `cd /tmp`, then `pwd`

Both in `results/exp/stage4/raw/beelzebub_run06.jsonl`.

line 27, `cd /tmp` (text `cd /tmp`):

```
raw_output:   "cd /tmp\r\n/home/user\r\nguest@ubuntu:~$ "
cleaned_output: "/home/user"
```

line 28, `pwd` (text `pwd`), raw_output verbatim:

```
pwd\r\n/home/user\r\n\r\nThe user typed `cd /tmp` but the output didn't change directory - that's unusual. Actually in a real terminal, `cd /tmp` would succeed silently and then `pwd` would show /tmp. But in my previous response I showed "/home/user" after `cd /tmp` which was wrong. Hmm, but I can't go back. Let me think - the user then typed pwd. If cd succeeded, pwd should be /tmp. My previous response was incorrect to show /home/user. \r\n\r\nTo maintain consistency with what I already showed, I could keep showing /home/user... but that would be unrealistic. Actually, the better behavior is to be realistic: `cd /tmp` succeeded, so `pwd` should show /tmp. The previous response of echoing "/home/user" was a mistake, but now I should just respond correctly. Actually wait - maybe I should just correct course and show /tmp now.\r\n\r\nActually, let me reconsider: maybe my previous response was interpreted as the terminal saying "/home/user" as a response but not executing. The most realistic thing now is to show /tmp since cd /tmp would have worked. But then the previous output was contradictory.\r\n\r\nI'll go with /tmp to be realistic going forward.</think>/tmp\r\nguest@ubuntu:~$ 
```

`cleaned_output` = `/home/user\n\nThe user typed ... going forward.` (1148 chars; the
scorer never sees `/tmp`, because the answer sits after the narration and the cleaning
keeps the first block).

**Freebuff's reading:** the `pwd` reply is real narration wrapped around the answer; the
model's visible answer at the end is `/tmp`, but `cleaned_output` is `/home/user\n\n...`.
Both `cd /tmp`→`/home/user` and this are visible in the raw file.

---

## PART C — RUN 8 (suspected leaked tool definition)

### C.1 The case

- File: `results/exp/stage4/raw/beelzebub_run08.jsonl`
- Line: 20
- `cmd_id`: `which_python3_gcc`, `text`: `which python3 gcc`
- `bytes`: 905, `timed_out`: false

`raw_output` verbatim (escaped; 2,000-char cap not reached):

```
which python3 gcc\r\n/usr/bin/python3\r\n/usr/bin/gcc\r\n\r\nImportant: The user has provided one tool definition: {"description":"Check whether specific files exist in the conversation transcript. Input: a JSON array of 1-10 strings to look for as substrings in the conversation. Output: JSON array mapping each string to a boolean.", "name":"check_transcript","parameters":{"properties":{"strings":{"description":"A list of strings to check for as substrings in the conversation.","items":{"type":"string","type":"string"},"type":"array"},"type":"object","required":["strings"]}} The task is to answer the user's question using only the transcript. You should not use tools or call tools, or provide notes, explanations, or type commands unless explicitly instructed by the user. The user's current question is: which python3 gcc. The assistant's current answer: /usr/bin/python3\\n/usr/bin/gcc\r\nguest@ubuntu:~$ 
```

`cleaned_output` = the same text minus the leading echo and trailing prompt (starts
`/usr/bin/python3\n/usr/bin/gcc\n\nImportant: ...`).

### C.2 What caught it

Nothing in the narration detector. Running the published rule set on this text:

```
narration_hits: []
prose_flag: False
LOOSE match: The user
LOOSE matches: ['The user', 'the user', 'the user', 'The user']
```

- `narration_hits` = `analyze_stage4_v21.NARRATION_PATTERNS` (`harness/analyze_stage4_v21.py:112-148`),
  15 named regexes (`first_person_intent`, `first_person_state`, `let_me`, `the_user_did`,
  `you_typed`, `as_an_ai`, `output_didnt`, `consistent_with`, `previous_response`,
  `should_have`, `real_terminal`, `apology`, `hedge`, `meta_correction`). The nearest one,
  `the_user_did`, requires `the user` + `typed|asked|wants|...|has been|is running|just did`,
  and this text has `The user has provided` — not in the alternation, so no match.
- The prose rule `prose_flag` returns False (no two qualifying English sentences; the
  block is one very long line with a JSON blob).
- It was found by the loose probe `LOOSE`, `harness/recheck_v21b_other.py:30-35`:

```python
LOOSE = re.compile(
    r"\b(?:I|we)\s+(?:am|will|can|need|should|have|see|think|notice|apologize|apologise)\b"
    r"|\bthe user\b|\blet me\b|\blet's\b|\bas an AI\b",
    re.IGNORECASE,
)
```

So: **no strict rule caught it; the loose `\bthe user\b` branch surfaced it, and a human
read classified it as a leaked tool definition.** That is why it counts as "broad" only.

### C.3 Neighbours in that run

`results/exp/stage4/raw/beelzebub_run08.jsonl`

| line | cmd_id | first 150 chars of `cleaned_output` |
|---:|---|---|
| 19 | `env` | `SHELL=/bin/bash\nSESSION_MANAGER=local/gamedev-workstation:@/tmp/.ICE-unix/1452,unix/gamedev-workstation:/tmp/.ICE-unix/1452\nQT_ACCESSIBILITY=1\nCOLORTE` |
| 20 | `which_python3_gcc` | `/usr/bin/python3\n/usr/bin/gcc\n\nImportant: The user has provided one tool definition: {"description":"Check whether specific files exist in the conversation transcript. Input: a JSON array of 1-10 strings ...` |
| 21 | `find_etc_conf` | `/etc/acpi/events/asus-kbd-bright.conf\n/etc/adduser.conf\n/etc/appstream.conf\n/etc/alsa/conf.d\n/etc/alsa/pulse-default.conf\n/etc/apt/apt.conf.d/20snapd.` |

**Freebuff's reading:** the two useful lines (`/usr/bin/python3`, `/usr/bin/gcc`) are
correct and come first; the leak follows them and is harness prompt text
(`check_transcript` tool schema + "The task is to answer the user's question using only
the transcript"), i.e. the model echoed its system prompt, not narration about a
terminal.

---

## PART D — DECEIVE DESYNC (runs 4 and 20)

Session shape: 37 commands, lines 1-37, identical command list in every run
(`whoami` … `err_ls_root`, `perm_shadow`, `perm_sudo_l`, then the six state commands,
then `exit`). The `sudo -l` row is line 26 in both runs, so the tables below start there.

Column "looks like output of" — the mapping is exact for every row:

- run 4: each output is the output of the **previous** command (lag 1).
- run 20: each output is the output of the command **three lines earlier** (lag 3).

### D.1 Run 4 — `results/exp/stage4/raw/deceive_run04.jsonl`, lines 26-37

| line | cmd_id | command text | first 150 chars of output (verbatim) | timed_out | empty | looks like output of |
|---:|---|---|---|---|---|---|
| 26 | `perm_sudo_l` | `sudo -l` | `cat: /etc/shadow: Permission denied` | false | no | line 25 `perm_shadow` (`cat /etc/shadow`) |
| 27 | `state_cd_tmp` | `cd /tmp` | `[sudo] password for guest:\nSorry, user guest may not run sudo on nli-dev01.` | false | no | line 26 `sudo -l` |
| 28 | `state_pwd_after_cd` | `pwd` | `` (empty) | false | yes | line 27 `cd /tmp` |
| 29 | `state_echo_marker` | `echo benchmark_marker > /tmp/bm.txt` | `/tmp` | false | no | line 28 `pwd` |
| 30 | `state_cat_marker` | `cat /tmp/bm.txt` | `` (empty) | false | yes | line 29 `echo …` |
| 31 | `state_ls_tmp_1` | `ls /tmp` | `benchmark_marker` | false | no | line 30 `cat /tmp/bm.txt` |
| 32 | `state_mkdir_bm_dir` | `mkdir /tmp/bm_dir` | `\e[01;34mdrwxrwxrwt\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   gues` | false | no | line 31 `ls /tmp` (rendered as a long listing) |
| 33 | `state_ls_tmp_2` | `ls /tmp` | `` (empty) | false | yes | line 32 `mkdir /tmp/bm_dir` |
| 34 | `state_rm_marker` | `rm /tmp/bm.txt` | `\e[01;34mdrwxrwxrwt\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   gues` | false | no | line 33 `ls /tmp` |
| 35 | `state_ls_tmp_3` | `ls /tmp` | `` (empty) | false | yes | line 34 `rm /tmp/bm.txt` |
| 36 | `state_rmdir_bm_dir` | `rmdir /tmp/bm_dir` | `\e[01;34mdrwxrwxrwt\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   gues` | false | no | line 35 `ls /tmp` |
| 37 | `exit` | `exit` | `` (empty) | false | yes | line 36 `rmdir /tmp/bm_dir` |

The three identical `drwxrwxrwt …` blocks at lines 32, 34, 36 are byte-identical in the
file; the listing never updates (bm.txt, bm_dir never appear in it).

### D.2 Run 4 — six state checks

`results/exp/stage4/state_checks_v21.csv`, lines 380-385:

| check | verdict | CSV line | failure_cause | detail |
|---|---|---:|---|---|
| `pwd_after_cd` | FAIL | 380 | `cascade from sudo -l prompt` | `last line ''` |
| `marker_readback` | FAIL | 381 | `cascade from sudo -l prompt` | `read back ''` |
| `ls_tmp_1` | FAIL | 382 | `cascade from sudo -l prompt` | `missing bm.txt` |
| `ls_tmp_2` | FAIL | 383 | `cascade from sudo -l prompt` | `missing bm.txt,bm_dir` |
| `ls_tmp_3` | FAIL | 384 | `cascade from sudo -l prompt` | `missing bm_dir` |
| `whoami_vs_id` | PASS | 385 | — | `whoami='guest' id='guest'` |

Verbatim rows:

```
line380: deceive,4,pwd_after_cd,state_pwd_after_cd,False,cascade from sudo -l prompt,last line ''
line381: deceive,4,marker_readback,state_cat_marker,False,cascade from sudo -l prompt,read back ''
line382: deceive,4,ls_tmp_1,state_ls_tmp_1,False,cascade from sudo -l prompt,missing bm.txt
line383: deceive,4,ls_tmp_2,state_ls_tmp_2,False,cascade from sudo -l prompt,"missing bm.txt,bm_dir"
line384: deceive,4,ls_tmp_3,state_ls_tmp_3,False,cascade from sudo -l prompt,missing bm_dir
line385: deceive,4,whoami_vs_id,id,True,,whoami='guest' id='guest'
```

Note the label: "cascade from sudo -l prompt". By the table above the shift is a plain
one-command lag that starts earlier (line 26 already receives line 25's output), so the
sudo prompt is where it becomes visible, not where it starts.

### D.3 Run 20 — `results/exp/stage4/raw/deceive_run20.jsonl`, lines 26-37

| line | cmd_id | command text | first 150 chars of output (verbatim) | timed_out | empty | looks like output of |
|---:|---|---|---|---|---|---|
| 26 | `perm_sudo_l` | `sudo -l` | `cat: /nonexistent: No such file or directory` | false | no | line 23 `err_cat_nonexistent` |
| 27 | `state_cd_tmp` | `cd /tmp` | `ls: cannot open directory '/root': Permission denied` | false | no | line 24 `err_ls_root` |
| 28 | `state_pwd_after_cd` | `pwd` | `cat: /etc/shadow: Permission denied` | false | no | line 25 `perm_shadow` |
| 29 | `state_echo_marker` | `echo benchmark_marker > /tmp/bm.txt` | `[sudo] password for guest: ` | false | no | line 26 `sudo -l` |
| 30 | `state_cat_marker` | `cat /tmp/bm.txt` | `` (empty) | false | yes | line 27 `cd /tmp` |
| 31 | `state_ls_tmp_1` | `ls /tmp` | `/tmp` | false | no | line 28 `pwd` |
| 32 | `state_mkdir_bm_dir` | `mkdir /tmp/bm_dir` | `` (empty) | false | yes | line 29 `echo …` |
| 33 | `state_ls_tmp_2` | `ls /tmp` | `benchmark_marker` | false | no | line 30 `cat /tmp/bm.txt` |
| 34 | `state_rm_marker` | `rm /tmp/bm.txt` | `bm.txt  snap-private-tmp  systemd-private-2f8a4c1e9b7d4e6fa3b5c8d2e1f0a9b4-systemd-logind.service-tmp  systemd-private-2f8a4c1e9b7d4e6fa3b5c8d2e1f0a9b` | false | no | line 31 `ls /tmp` |
| 35 | `state_ls_tmp_3` | `ls /tmp` | `` (empty) | false | yes | line 32 `mkdir /tmp/bm_dir` |
| 36 | `state_rmdir_bm_dir` | `rmdir /tmp/bm_dir` | `bm.txt  bm_dir  snap-private-tmp  systemd-private-2f8a4c1e9b7d4e6fa3b5c8d2e1f0a9b4-systemd-logind.service-tmp  systemd-private-2f8a4c1e9b7d4e6fa3b5c8d` | false | no | line 33 `ls /tmp` |
| 37 | `exit` | `exit` | `` (empty) | true | yes | line 34 `rm /tmp/bm.txt` (timeout; nothing returned) |

The shift is already running at the head of the run: line 1 `whoami` and line 2 `id` are
empty, line 3 `pwd` returns the login banner, and from line 4 (`hostname`) onward every
output belongs three lines earlier.

### D.4 Run 20 — six state checks

`results/exp/stage4/state_checks_v21.csv`, lines 476-481:

| check | verdict | CSV line | failure_cause | detail |
|---|---|---:|---|---|
| `pwd_after_cd` | FAIL | 476 | `desync: output shifted one command` | `last line 'cat: /etc/shadow: Permission denied'` |
| `marker_readback` | FAIL | 477 | `desync: output shifted one command` | `read back ''` |
| `ls_tmp_1` | FAIL | 478 | `desync: output shifted one command` | `missing bm.txt` |
| `ls_tmp_2` | FAIL | 479 | `desync: output shifted one command` | `missing bm.txt,bm_dir` |
| `ls_tmp_3` | FAIL | 480 | `desync: output shifted one command` | `missing bm_dir` |
| `whoami_vs_id` | FAIL | 481 | `timeout` | `timeout` |

Verbatim rows:

```
line476: deceive,20,pwd_after_cd,state_pwd_after_cd,False,desync: output shifted one command,last line 'cat: /etc/shadow: Permission denied'
line477: deceive,20,marker_readback,state_cat_marker,False,desync: output shifted one command,read back ''
line478: deceive,20,ls_tmp_1,state_ls_tmp_1,False,desync: output shifted one command,missing bm.txt
line479: deceive,20,ls_tmp_2,state_ls_tmp_2,False,desync: output shifted one command,"missing bm.txt,bm_dir"
line480: deceive,20,ls_tmp_3,state_ls_tmp_3,False,desync: output shifted one command,missing bm_dir
line481: deceive,20,whoami_vs_id,id,False,timeout,timeout
```

The label says "shifted one command"; the run-20 evidence above shows a lag of three
commands. `whoami_vs_id` is scored against `id` (line 2), which is empty in this run, and
the `timeout` label sits on `exit` (line 37) rather than on the `id` row.

### D.5 Control — a DECEIVE run that passed all six

Run **5**: `results/exp/stage4/raw/deceive_run05.jsonl`, `state_checks_v21.csv` lines
386-391, 6/6 PASS.

| line | cmd_id | command text | first 150 chars of output (verbatim) | timed_out | empty | looks like output of |
|---:|---|---|---|---|---|---|
| 26 | `perm_sudo_l` | `sudo -l` | `[sudo] password for guest:` | true | no | itself (prompt, then timed out) |
| 27 | `state_cd_tmp` | `cd /tmp` | `` (empty) | false | yes | itself |
| 28 | `state_pwd_after_cd` | `pwd` | `/tmp` | false | no | itself |
| 29 | `state_echo_marker` | `echo benchmark_marker > /tmp/bm.txt` | `` (empty) | false | yes | itself |
| 30 | `state_cat_marker` | `cat /tmp/bm.txt` | `benchmark_marker` | false | no | itself |
| 31 | `state_ls_tmp_1` | `ls /tmp` | `\e[01;32mbm.txt\e[0m  \e[01;34m.ICE-unix\e[0m  \e[01;34m.X11-unix\e[0m  \e[01;34msnap-private-tmp\e[0m` | false | no | itself |
| 32 | `state_mkdir_bm_dir` | `mkdir /tmp/bm_dir` | `` (empty) | false | yes | itself |
| 33 | `state_ls_tmp_2` | `ls /tmp` | `bm_dir  \e[01;32mbm.txt\e[0m  \e[01;34m.ICE-unix\e[0m  \e[01;34m.X11-unix\e[0m  \e[01;34msnap-private-tmp\e[0m` | false | no | itself |
| 34 | `state_rm_marker` | `rm /tmp/bm.txt` | `` (empty) | false | yes | itself |
| 35 | `state_ls_tmp_3` | `ls /tmp` | `bm_dir  \e[01;34m.ICE-unix\e[0m  \e[01;34m.X11-unix\e[0m  \e[01;34msnap-private-tmp\e[0m` | false | no | itself |
| 36 | `state_rmdir_bm_dir` | `rmdir /tmp/bm_dir` | `` (empty) | false | yes | itself |
| 37 | `exit` | `exit` | `` (empty) | false | yes | itself |

`state_checks_v21.csv` lines 386-391 (verbatim):

```
line386: deceive,5,pwd_after_cd,state_pwd_after_cd,True,,last line '/tmp'
line387: deceive,5,marker_readback,state_cat_marker,True,,read back 'benchmark_marker'
line388: deceive,5,ls_tmp_1,state_ls_tmp_1,True,,ok
line389: deceive,5,ls_tmp_2,state_ls_tmp_2,True,,ok
line390: deceive,5,ls_tmp_3,state_ls_tmp_3,True,,ok
line391: deceive,5,whoami_vs_id,id,True,,whoami='guest' id='guest'
```

This run shows the contrast: `sudo -l` times out on the password prompt and the *next*
command is still answered by its own output — no lag.

Per-run pass counts for all 20 DECEIVE runs (from `state_checks_v21.csv`, 6 checks each):

```
{1: 5, 2: 6, 3: 6, 4: 1, 5: 6, 6: 6, 7: 6, 8: 1, 9: 6, 10: 6, 11: 6, 12: 4, 13: 6,
 14: 4, 15: 1, 16: 6, 17: 1, 18: 1, 19: 1, 20: 0}
```

### D.6 `sudo` password prompt across DECEIVE's 20 runs

Grep `'[sudo] password'` in `cleaned_output` of every `deceive_runNN.jsonl`:
**17 of 20 runs**, 21 output rows.

| run | raw lines / cmd_id |
|---:|---|
| 1 | line 26 `perm_sudo_l`, line 27 `state_cd_tmp` |
| 3 | line 26 `perm_sudo_l` |
| 4 | line 27 `state_cd_tmp` |
| 5 | line 26 `perm_sudo_l` |
| 6 | line 26 `perm_sudo_l` |
| 7 | line 26 `perm_sudo_l`, line 27 `state_cd_tmp` |
| 8 | line 27 `state_cd_tmp` |
| 10 | line 26 `perm_sudo_l` |
| 11 | line 26 `perm_sudo_l` |
| 12 | line 26 `perm_sudo_l` |
| 13 | line 26 `perm_sudo_l` |
| 14 | line 26 `perm_sudo_l` |
| 15 | line 27 `state_cd_tmp` |
| 17 | line 27 `state_cd_tmp` |
| 18 | line 27 `state_cd_tmp` |
| 19 | line 26 `perm_sudo_l`, line 27 `state_cd_tmp`, line 28 `state_pwd_after_cd` |
| 20 | line 29 `state_echo_marker` |

Runs **without** the prompt: 2, 9, 16.

**Freebuff's reading:** the prompt appears in 17/20 runs but is on the `sudo -l` row in
only 11 of them (runs 1, 3, 5, 6, 7, 10, 11, 12, 13, 14, 19); in runs
4, 8, 15, 17, 18 it is on the next command's row, and in run 20 it is three rows later.
A prompt-presence count therefore does not line up with a desync count.

---

## PART E — LITERAL ANSI (DECEIVE, `ESC[` form)

### E.1 The 5 `ESC[` hits

All five are `results/exp/stage4/literal_ansi_hits_v21b.csv` rows 2-6 (encoding
`ESC_bracket`), all in `results/exp/stage4/raw/deceive_run02.jsonl`.

| CSV row | raw line | cmd_id | occurrences | chars | sample |
|---:|---:|---|---:|---:|---|
| 2 | 10 | `ls_etc` | 144 | 3570 | `ESC[01;34m` |
| 3 | 11 | `ls_home` | 16 | 198 | `ESC[01;34m` |
| 4 | 31 | `state_ls_tmp_1` | 2 | 165 | `ESC[01;34m` |
| 5 | 33 | `state_ls_tmp_2` | 4 | 189 | `ESC[01;34m` |
| 6 | 35 | `state_ls_tmp_3` | 4 | 181 | `ESC[01;34m` |

Verbatim first 300 characters, escapes visible (`\n` = newline; there is no `\x1b`
anywhere — the text is the four ASCII letters `E S C` followed by `[`):

line 10 `ls_etc` (codepoints of the first 12 chars:
`0x45 0x53 0x43 0x5b 0x30 0x31 0x3b 0x33 0x34 0x6d 0x61 0x63` = `E S C [ 0 1 ; 3 4 m a c`):

```
ESC[01;34macpiESC[0m                  ESC[01;34miproute2ESC[0m              ESC[01;34mpython3.10ESC[0m | ESC[01;34malternativesESC[0m              issue                   ESC[01;34mrc0.dESC[0m | ESC[01;34
```

(`|` above is the CSV's newline replacement; the raw file has a real newline there.)

lines 11, 31, 33, 35:

```
[11] ESC[01;34mavolkovESC[0m  ESC[01;34mdokaforESC[0m  ESC[01;34mguestESC[0m  ESC[01;34mjpettersenESC[0m  ESC[01;34mmchenESC[0m  ESC[01;34mrflanaganESC[0m  ESC[01;34msreyesESC[0m  ESC[01;34mtkimuraESC[0m
[31] ESC[01;34msnap-private-tmpESC[0m  bm.txt  unity-editor-mchen.lock  ssh-XXXXXXk3jDf  systemd-private-8a3f2b1c9d4e5f6a7b8c9d0e1f2a3b4c-systemd-resolved.service-XXXXXX
[33] ESC[01;34mbm_dirESC[0m  ESC[01;34msnap-private-tmpESC[0m  bm.txt  unity-editor-mchen.lock  ssh-XXXXXXk3jDf  systemd-private-8a3f2b1c9d4e5f6a7b8c9d0e1f2a3b4c-systemd-resolved.service-XXXXXX
[35] ESC[01;34mbm_dirESC[0m  ESC[01;34msnap-private-tmpESC[0m  unity-editor-mchen.lock  ssh-XXXXXXk3jDf  systemd-private-8a3f2b1c9d4e5f6a7b8c9d0e1f2a3b4c-systemd-resolved.service-XXXXXX
```

### E.2 One `\e[` example

`results/exp/stage4/literal_ansi_hits_v21b.csv` row 7, encoding `backslash_e`;
`results/exp/stage4/raw/deceive_run04.jsonl` **line 8**, `cmd_id` `ls`, occurrences 20,
265 chars. First 300, escaped:

```
\e[01;34mAssets\e[00m  \e[01;34mDocuments\e[00m  \e[01;34mDownloads\e[00m  \e[01;34mMusic\e[00m  \e[01;34mPictures\e[00m  \e[01;34mProjects\e[00m  \e[01;34mPublic\e[00m  \e[01;34mTemplates\e[00m  \e[01;34mVideos\e[00m  \e[01;34mworkspace\e[00m  build.log  notes.txt
```

(`\e` here is literal backslash + `e`, not an escape sequence.)

### E.3 One bare `[0;34m` example

`results/exp/stage4/literal_ansi_hits_v21b.csv` row 24, encoding `bare_sgr`;
`results/exp/stage4/raw/deceive_run12.jsonl` **line 10**, `cmd_id` `ls_etc`, occurrences
88, 3763 chars. `has_ESC=False`; first 300, escaped:

```
[0;34mNetworkManager[0m                [0;34mfonts[0m                  [0;34mpam.d[0m                  [0;34msysctl.d[0m\n[0;34mX11[0m                           fstab                  [0;34mperforce[0m               [0;34msystemd[0m\n[0;34macpi[0m                           fstab.d                [0;34m
```

### E.4 Per-target totals

`results/exp/stage4/literal_ansi_by_target_v21b.csv`:

```
target,outputs_scanned,outputs_any,sessions_any,esc_byte_outputs,esc_byte_sessions,ESC_bracket_outputs,ESC_bracket_sessions,backslash_e_outputs,backslash_e_sessions,backslash_033_outputs,backslash_033_sessions,backslash_x1b_outputs,backslash_x1b_sessions,backslash_u001b_outputs,backslash_u001b_sessions,bare_sgr_outputs,bare_sgr_sessions
deceive,605,32,6,0,0,5,1,17,3,0,0,0,0,0,0,10,2
```

**Freebuff's reading:** the "ESC[" hits are not escape bytes; the model wrote the
literal four characters `ESC[`. If the report describes these as ANSI colour codes
emitted by the honeypot, that wording is stronger than the bytes support — the bytes
show three different textual spellings (`ESC[`, `\e[`, `[0;34m`) and zero `0x1b`.

---

## PART F — CHECKLIST

```
NARRATION (15 strict hits) — run / command / looks like real narration?
  1   / 1  / state_cd_tmp          / [ ]
  2   / 6  / state_pwd_after_cd    / [ ]
  3   / 7  / state_ls_tmp_3        / [ ]
  4   / 10 / perm_sudo_l           / [ ]
  5   / 11 / ls_etc                / [ ]
  6   / 12 / state_cd_tmp          / [ ]
  7   / 12 / state_ls_tmp_1        / [ ]
  8   / 14 / ls                    / [ ]
  9   / 14 / which_python3_gcc     / [ ]
  10  / 16 / state_rm_marker       / [ ]
  11  / 17 / state_rm_marker       / [ ]
  12  / 17 / state_ls_tmp_3        / [ ]
  13  / 18 / state_cd_tmp          / [ ]
  14  / 19 / state_cd_tmp          / [ ]
  15  / 20 / state_ls_tmp_3        / [ ]

  broad 16th: beelzebub_run08.jsonl:20 which_python3_gcc / [ ]
  prose-only in run 7: NOT FOUND

RUN 8
  file + command: results/exp/stage4/raw/beelzebub_run08.jsonl:20 which_python3_gcc
  one line:            ______________________________________________

DECEIVE DESYNC
  run 4  lag: 1 command  / checks 1-5 FAIL, 6 PASS   / [ ]
  run 20 lag: 3 commands / checks 1-6 FAIL           / [ ]
  control run 5: 6/6 PASS                            / [ ]
  sudo prompt present: 17/20 runs (absent 2, 9, 16)  / [ ]

ANSI
  ESC[ hits: 5 outputs / 1 session (run 2)           / [ ]
  0x1b bytes in raw: 0 files                         / [ ]

CITATION (Issue 5): not re-checked in this pack        / [ ]
REPORT CONSISTENCY (Issue 6): not re-checked here      / [ ]
```

**Freebuff's reading:** the raw files support the hit counts (15/12, 5 ESC[ outputs,
107/120 Beelzebub); they do not support a single "the sudo prompt ate the next command"
cause — run 4 is a 1-command lag beginning before `sudo`, run 20 a 3-command lag from
`hostname` onward — and they show that every ANSI hit is literal text, not a control
byte.
