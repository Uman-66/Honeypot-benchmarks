# DECEIVE output desync — onset per run (v2.1b)

Read-only analysis of `results/exp/stage4/raw/deceive_run01.jsonl` … `deceive_run20.jsonl`
(branch `report-v2.1-recheck`). Each file has 37 JSON lines; line N is the N-th command of
`harness/commands.yaml` in file order, so `line == command position == cmd_id position`.
No file was modified except this one.

## Method (so every number can be re-derived)

* **Definition used.** Row *i* "belongs to an earlier command" when its `cleaned_output`
  matches the output signature of command *j* with *j < i* and matches **no** other command's
  signature. `lag = i − j` (measured in rows/commands, not seconds).
* **Signatures** (anchored at start of text, matched on `cleaned_output`; persona values
  `user`/`host` derived from this run's own `id` and `uname -a` output):
  `whoami` = `^<user>$`; `hostname` = `^<host>$`; `pwd` = `^/home/<user>$`;
  `id` = `^uid=<digits>(`; `uname_a` = `^Linux <host> `; `os_release` = `^PRETTY_NAME=`;
  `passwd` = `^root:x:0:0:`; `ls_la` = `^total <digits>`; `ls_etc` = contains
  `adduser.conf`/`appstream.conf`/`ImageMagick`/`ca-certificates.conf` **and** no line
  starting `/etc/`; `date` = `^(Mon|Tue|…|Sun) <Mon> <d>`; `uptime` = `^\s*\d\d:\d\d:\d\d up …load average`;
  `free_m` = `^\s+total\s+used\s+free\s+shared`; `df_h` = `^Filesystem\s+Size\s+Used`;
  `ps_aux` = `^(USER\s+PID\s+%CPU|\s*PID\s+%CPU\s+%MEM)`; `cpuinfo` = `^(processor\s*:|vendor_id\s*:)`;
  `w` = `^\s*\d\d:\d\d:\d\d up …\nUSER\s+TTY` (wins over `uptime`);
  `env` = `^(PATH=|SHELL=)` or three consecutive `KEY=` lines; `which_python3_gcc` = `^/usr/bin/python3\n/usr/bin/gcc`;
  `find_etc_conf` = `^/etc/\S+\.conf`; `err_foobarbaz` = `^foobarbaz: command not found`;
  `err_cat_nonexistent` = `^cat: /nonexistent: No such file`; `err_ls_root` = `^ls: cannot open directory '/root': Permission denied`;
  `perm_shadow` = `^cat: /etc/shadow: Permission denied`; `perm_sudo_l` = `^(\[sudo\] password|Sorry, user|Sorry, try again)`;
  `state_pwd_after_cd` = `^/tmp$`; `state_cat_marker` = `^benchmark_marker$`;
  `state_ls_tmp_1/2/3` = a `/tmp` listing identified by token content (`bm.txt` only →
  1, `bm.txt`+`bm_dir` → 2, `bm_dir` only → 3), excluding lines that begin `rm:`, `rmdir:`,
  `mkdir:`, `cat:`, `ls:`.
* **Excluded as NOT FOUND (never guessed):** empty text on `state_cd_tmp`,
  `state_echo_marker`, `state_mkdir_bm_dir`, `state_rm_marker`, `state_rmdir_bm_dir`, `exit`
  (all of these legitimately print nothing); `ls`/`ls_home` listings (a home listing is the
  same shape for both commands); any text matching no signature.
* `bytes`, `timed_out`, `latency_s` are read straight from the JSONL fields of the same line.
* "The sudo row" = line 26, `cmd_id = perm_sudo_l`. "Had the prompt" = the literal
  `[sudo] password` occurs in that line's `raw_output` or `cleaned_output`.

## Per-run onset

| run | file | shifted | onset line | onset cmd_id | output matched (earlier cmd) | lag | timed_out at onset−1, −2, −3 | line 26 has `[sudo] password` | line 26 timed_out |
|----:|------|:-------:|-----------:|--------------|------------------------------|----:|------------------------------|:-----------------------------:|:-----------------:|
| 1  | `results/exp/stage4/raw/deceive_run01.jsonl` | yes | 27 | `state_cd_tmp` | `perm_sudo_l` (26) | 1 | True, False, False | yes | True |
| 2  | `results/exp/stage4/raw/deceive_run02.jsonl` | no  | NOT FOUND | — | — | — | — | no | False |
| 3  | `results/exp/stage4/raw/deceive_run03.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 4  | `results/exp/stage4/raw/deceive_run04.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | no | False |
| 5  | `results/exp/stage4/raw/deceive_run05.jsonl` | no  | NOT FOUND | — | — | — | — | yes | True |
| 6  | `results/exp/stage4/raw/deceive_run06.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 7  | `results/exp/stage4/raw/deceive_run07.jsonl` | yes | 27 | `state_cd_tmp` | `perm_sudo_l` (26) | 1 | True, False, False | yes | True |
| 8  | `results/exp/stage4/raw/deceive_run08.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | no | False |
| 9  | `results/exp/stage4/raw/deceive_run09.jsonl` | no  | NOT FOUND | — | — | — | — | no | False |
| 10 | `results/exp/stage4/raw/deceive_run10.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 11 | `results/exp/stage4/raw/deceive_run11.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 12 | `results/exp/stage4/raw/deceive_run12.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 13 | `results/exp/stage4/raw/deceive_run13.jsonl` | no  | NOT FOUND | — | — | — | — | yes | False |
| 14 | `results/exp/stage4/raw/deceive_run14.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | yes | False |
| 15 | `results/exp/stage4/raw/deceive_run15.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | no | False |
| 16 | `results/exp/stage4/raw/deceive_run16.jsonl` | no  | NOT FOUND | — | — | — | — | no | False |
| 17 | `results/exp/stage4/raw/deceive_run17.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | no | False |
| 18 | `results/exp/stage4/raw/deceive_run18.jsonl` | yes | 18 | `w` | `ps_aux` (16) | 2 | True, True, False | no | False |
| 19 | `results/exp/stage4/raw/deceive_run19.jsonl` | yes | 27 | `state_cd_tmp` | `perm_sudo_l` (26) | 1 | True, False, False | yes | True |
| 20 | `results/exp/stage4/raw/deceive_run20.jsonl` | yes | 4 | `hostname` | `whoami` (1) | 3 | False, True, True | no | False |

All line numbers are line numbers in the named `.jsonl` file. For the ten "no" runs the whole
session was scanned and no row matched an earlier command's signature; that is recorded as
NOT FOUND, not as "no shift observed with certainty" beyond the stated signature limits.

## Summary

* Shifted runs: **10** — runs 1, 4, 7, 8, 14, 15, 17, 18, 19, 20.
* Shifted runs with at least one `timed_out=true` in the 3 rows before onset: **10 of 10**.
  * the timeout is at onset−1 in 9 runs; run 20 is the exception (onset−2 and onset−3, both
    `whoami` and `id`, line 1 and line 2).
* Shifted runs with **only** the sudo prompt and no timeout before onset: **0**.
* Shifted runs with **neither**: **0**.
* Of the 10 shifted runs, 4 carry `[sudo] password` on line 26 (runs 1, 7, 14, 19); the other
  6 (4, 8, 15, 17, 18, 20) carry another command's output there and have no prompt on that line.
* Across all 20 runs, line 26 contains `[sudo] password` in 11 runs: 1, 3, 5, 6, 7, 10, 11,
  12, 13, 14, 19. Of those 11, 4 are followed by a shift (1, 7, 14, 19) and 7 are not
  (3, 5, 6, 10, 11, 12, 13).

## Shifted runs where the lag changes mid-session

| run | lag sequence (row → lag) | note |
|----:|--------------------------|------|
| 1  | 27→1, 28→2 | row 28 carries the second chunk of the line-26 interaction, not a new command; resync at 29 |
| 4  | 18→2, 19→1, then 1 to line 36 | sustained one-row lag after the backlog row |
| 8  | 18→2, 19→1, then 1 to line 36 | same shape as run 4 |
| 15 | 18→2, 19→1, then 1 to line 36 | same shape as run 4 |
| 17 | 18→2, 19→1, then 1 to line 36 | same shape as run 4 |
| 18 | 18→2, 19→1, then 1 to line 36 | same shape as run 4 |
| 19 | 27→1, 28→2, 29→3 | rows 28 and 29 carry the 2nd and 3rd chunks of the line-26 interaction; resync at 30 |
| 14 | 18→2, then 0 from line 19 | the only run where the backlog row also delivers the *current* command's output (see evidence) |

Constant lag: run 7 (single row 27, lag 1, resync at 28) and run 20 (lag 3 on every
attributable row from 4 to 36).

## Rows that could not be attributed (NOT FOUND, not counted)

Empty-output rows and the two home listings are ambiguous in every run and were skipped:

* run 1: L8 `ls`, L11 `ls_home`, L29, L32, L34, L36, L37 (empty)
* run 4: L8 `ls`, L11 `ls_home`, L16, L17, L28, L30, L33, L35, L37 (empty)
* run 7: L8 `ls`, L11 `ls_home`, L29, L32, L34, L36, L37 (empty)
* run 8: L8 `ls`, L11 `ls_home`, L16, L17, L28, L30, L33, L35, L37 (empty)
* run 14: L8 `ls`, L11 `ls_home`, L16, L17, L27, L29, L32, L34, L36, L37 (empty)
* run 15: L8 `ls`, L11 `ls_home`, L16, L17, L28, L30, L33, L35, L37 (empty)
* run 17: L8 `ls`, L11 `ls_home`, L16, L17, L28, L30, L33, L35, L37 (empty)
* run 18: L8 `ls`, L11 `ls_home`, L16, L17, L28, L30, L33, L35, L37 (empty)
* run 19: L8 `ls`, L11 `ls_home`, L37 (empty)
* run 20: L1, L2 (empty, both timed out), L8 `ls`, L11 `ls_home`, L30, L32, L35, L37 (empty)

Two consequences worth stating plainly, because they bound the table above:

* Run 20's line 3 (`pwd`) receives the SSH login banner (`Welcome to Ubuntu …`), which
  belongs to no command. It is not a lag row; the first row whose text belongs to an earlier
  command is line 4.
* Runs 4, 8, 15, 17, 18: the onset row (18, `w`) contains **two** earlier outputs in one blob
  — the `ps aux` output (line 16) followed by the `cpuinfo` output (line 17). Both of those
  rows are `timed_out=true` with 8 and 29 bytes respectively, i.e. the backlog is flushed in
  the `w` slot. This is why the onset lag is 2 and not 1.

## Verbatim evidence

Convention: every quote below is the Python `repr()` of the JSON string field, so `\r\n` is
CR LF, `\x1b` is a real ESC byte, and `\\e` is the two characters backslash + `e`. Nothing is
paraphrased; only the length-based truncation in run 4 line 18 is marked.

### Run 1 — `results/exp/stage4/raw/deceive_run01.jsonl`, lines 25–29

```
L25  cmd_id=perm_shadow  timed_out=False  bytes=79  latency_s=1.722
     raw_output = 'cat /etc/shadow\r\ncat: /etc/shadow: Permission denied\r\nguest@pixelforge-dev01:~$'

L26  cmd_id=perm_sudo_l  timed_out=True  bytes=35  latency_s=120.016
     raw_output = 'sudo -l\r\n[sudo] password for guest:'

L27  cmd_id=state_cd_tmp  timed_out=True  bytes=54  latency_s=120.01
     raw_output = 'cd /tmp\r\nSorry, try again.\r\n[sudo] password for guest:'

L28  cmd_id=state_pwd_after_cd  timed_out=False  bytes=86  latency_s=6.735
     raw_output = 'pwd\r\nSorry, try again.\r\nsudo: 2 incorrect password attempts\r\nguest@pixelforge-dev01:~$'

L29  cmd_id=state_echo_marker  timed_out=False  bytes=62  latency_s=2.072
     raw_output = 'echo benchmark_marker > /tmp/bm.txt\r\nguest@pixelforge-dev01:~$'
```

### Run 4 — `results/exp/stage4/raw/deceive_run04.jsonl`, lines 15–20

```
L15  cmd_id=df_h  timed_out=False  bytes=395  latency_s=2.934
     raw_output = 'df -h\r\nFilesystem      Size  Used Avail Use% Mounted on\r\ntmpfs            3.2G  2.1M  3.2G   1% /run\r\n/dev/sda2       916G  538G  332G  59% /\r\ntmpfs            16G     0   16G   0% /dev/shm\r\ntmpfs            5.0M     0  5.0M   0% /run/lock\r\n/dev/sda1       512M  6.1M  506M   1% /boot/efi\r\ntmpfs            3.2G   76K  3.2G   1% /run/user/1001\r\n\r\n\\e[01;32mguest@nli-dev01\\e[00m:\\e[01;34m~\\e[00m$'

L16  cmd_id=ps_aux  timed_out=True  bytes=8  latency_s=120.011
     raw_output = 'ps aux\r\n'

L17  cmd_id=cpuinfo  timed_out=True  bytes=29  latency_s=120.011
     raw_output = 'cat /proc/cpuinfo | head -5\r\n'

L18  cmd_id=w  timed_out=False  bytes=128521  latency_s=35.09
     raw_output[0:300]  = 'w\r\nUSER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\r\nroot           1  0.0  0.0 169300 13120 ?        Ss   Jun19   0:24 /sbin/init splash\r\nroot           2  0.0  0.0      0     0 ?        S    Jun19   0:00 [kthreadd]\r\nroot           3  0.0  0.0      0     0 ?        I<   Ju'
     [...]
     raw_output[-300:]  = ' 17408 ?        Ssl  Jun19   0:00 /usr/libexec/udisks2/udisksd\r\nroot        9703  0.0  0.0  161064  8704 ?        Ssl  Jun19   0processor\t: 0\r\nvendor_id\t: GenuineIntel\r\ncpu family\t: 6\r\nmodel\t\t: 85\r\nmodel name\t: Intel(R) Xeon(R) W-2245 CPU @ 3.90GHz\r\n\r\n\\e[01;32mguest@nli-dev01\\e[00m:\\e[01;34m~\\e[00m$'
     [TRUNCATED for size: len(raw_output)=128521 chars; the elided middle is raw_output[300:-300]]

L19  cmd_id=env  timed_out=False  bytes=302  latency_s=3.871
     raw_output = 'env\r\n 14:25:12 up 23 days,  6:18,  2 users,  load average: 1.28, 1.26, 1.18\r\nUSER     TTY      FROM             LOGIN@   IDLE   WHAT\r\nguest    pts/0    10.24.18.115     14:22    0.00s  w\r\nrchen    pts/2    10.24.22.203     09:47    1:32m  tmux attach\r\n\r\n\\e[01;32mguest@nli-dev01\\e[00m:\\e[01;34m~\\e[00m$'

L20  cmd_id=which_python3_gcc  timed_out=False  bytes=2994  latency_s=13.418
     raw_output[0:300]  = 'which python3 gcc\r\nSHELL=/bin/bash\r\nSESSION_MANAGER=local/nli-dev01:@/tmp/.ICE-unix/1834,unix/nli-dev01:/tmp/.ICE-unix/1834\r\nWINDOWID=0\r\nCOLORTERM=truecolor\r\nXDG_CONFIG_DIRS=/etc/xdg/xdg-ubuntu:/etc/xdg\r\nXDG_SESSION_PATH=/org/freedesktop/DisplayManager/Session0\r\nLANGUAGE=en_US:en\r\nMANDATORY_PATH=/us'
     [...]
     raw_output[-300:]  = 'snapd/desktop\r\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin:/opt/unity-editor/bin:/opt/perforce/bin\r\nGDMSESSION=ubuntu\r\nDBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus\r\n_=/usr/bin/env\r\n\r\n\\e[01;32mguest@nli-dev01\\e[00m:\\e[01;34m~\\e[00m$'
     [TRUNCATED for size: len(raw_output)=2994 chars; the elided middle is raw_output[300:-300]]
```

### Run 20 — `results/exp/stage4/raw/deceive_run20.jsonl`, lines 1–6

```
L1  cmd_id=whoami  timed_out=True  bytes=8  latency_s=120.013
     raw_output = 'whoami\r\n'

L2  cmd_id=id  timed_out=True  bytes=4  latency_s=120.009
     raw_output = 'id\r\n'

L3  cmd_id=pwd  timed_out=False  bytes=916  latency_s=20.882
     raw_output[0:300]  = 'pwd\r\nWelcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\r\n\r\n * Documentation:  https://help.ubuntu.com\r\n * Management:     https://landscape.canonical.com\r\n * Support:        https://ubuntu.com/advantage\r\n\r\n  System information as of Mon Jun 10 09:14:22 UTC 2024\r\n\r\n  System load:  0.4'
     [...]
     raw_output[-300:]  = 'nder /srv/projects.\r\n  CI/CD pipelines: https://ci.meridian-games.internal\r\n  Asset server:    perforce://depot.meridian-games.internal:1666\r\n\r\n  Report issues to #it-support on Slack or helpdesk@meridian-games.internal\r\n\r\nLast login: Mon Jun 10 08:47:03 2024 from 10.24.16.108\r\nguest@gamedev-ws03:~$'
     [TRUNCATED for size: len(raw_output)=916 chars; the elided middle is raw_output[300:-300]]

L4  cmd_id=hostname  timed_out=False  bytes=38  latency_s=2.539
     raw_output = 'hostname\r\nguest\r\nguest@gamedev-ws03:~$'

L5  cmd_id=uname_a  timed_out=False  bytes=123  latency_s=2.773
     raw_output = 'uname -a\r\nuid=1001(guest) gid=1001(guest) groups=1001(guest),27(sudo),1003(developers),1008(artists)\r\nguest@gamedev-ws03:~$'

L6  cmd_id=os_release  timed_out=False  bytes=55  latency_s=1.61
     raw_output = 'cat /etc/os-release\r\n/home/guest\r\nguest@gamedev-ws03:~$'
```

## Run 4, lines 32 / 34 / 36 — do they differ?

Yes, all three differ. `cleaned_output` of the three lines has three different MD5 prefixes:

| line | cmd_id | actual output belongs to | bytes | md5(cleaned_output)[:10] | contains `bm.txt` | contains `bm_dir` |
|-----:|--------|--------------------------|------:|--------------------------|:-----------------:|:-----------------:|
| 32 | `state_mkdir_bm_dir` | `state_ls_tmp_1` (line 31) | 1438 | `fe5ecc1c5c` | True | False |
| 34 | `state_rm_marker` | `state_ls_tmp_2` (line 33) | 1513 | `c77004fb59` | True | True |
| 36 | `state_rmdir_bm_dir` | `state_ls_tmp_3` (line 35) | 1454 | `fe2647c86f` | False | True |

Pairwise equality of `cleaned_output`: 32 vs 34 `False`; 32 vs 36 `False`; 34 vs 36 `False`.

Two further facts about those rows, from the same lines:

* Line 32 shows `bm.txt` but not `bm_dir`; line 34 shows both; line 36 shows `bm_dir` but not
  `bm.txt`. That is the expected progression of `ls /tmp` at lines 31, 33, 35 — which is what
  makes them the *sources* for lines 32, 34, 36.
* Line 34's text still lists `bm.txt` although the command sent on line 34 is `rm /tmp/bm.txt`;
  the listing shown is the line-33 listing, one row behind.

Verbatim `cleaned_output` of the three lines (same repr convention as above):

```
L32  cmd_id=state_mkdir_bm_dir  bytes=1438  md5=fe5ecc1c5cb86a84380a15acd2cfac1c
     cleaned_output = '\\e[01;34mdrwxrwxrwt\\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   guest        61 Jun 12 14:24  .X0-lock\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.X11-unix\\e[00m\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.ICE-unix\\e[00m\ndrwx------   3 guest   guest       4096 Jun 12 14:22  \\e[01;34msnap-private-tmp\\e[00m\n-rw-r--r--   1 guest   guest        17 Jun 12 14:25  bm.txt\ndrwxr-xr-x   2 rchen   devteam     4096 Jun 12 11:03  \\e[01;34masset_bake_cache\\e[00m\n-rw-r--r--   1 rchen   devteam  83886080 Jun 12 11:47  level_03_lightmaps.bake\n-rw-r--r--   1 rchen   devteam     2048 Jun 12 11:47  level_03_lightmaps.bake.meta\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-systemd-logind.service-eJqXHf\\e[00m\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-chronyd.service-KmRtYw\\e[00m\nsrw-rw-rw-   1 root    root           0 Jun  3 09:12  .X11-unix/X0\n-rw-r--r--   1 guest   guest     1048576 Jun 12 13:58  unity_crash_20250612_135812.dmp\n-rw-r--r--   1 guest   guest        512 Jun 12 13:58  unity_crash_20250612_135812.log\ndrwxr-xr-x   2 guest   guest       4096 Jun 12 14:22  \\e[01;34mssh-jKd9x2Lm4P\\e[00m'

L34  cmd_id=state_rm_marker  bytes=1513  md5=c77004fb599c46d6b51a08619a0dd3a8
     cleaned_output = '\\e[01;34mdrwxrwxrwt\\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   guest        61 Jun 12 14:24  .X0-lock\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.X11-unix\\e[00m\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.ICE-unix\\e[00m\ndrwx------   3 guest   guest       4096 Jun 12 14:22  \\e[01;34msnap-private-tmp\\e[00m\n-rw-r--r--   1 guest   guest        17 Jun 12 14:25  bm.txt\ndrwxr-xr-x   2 rchen   devteam     4096 Jun 12 11:03  \\e[01;34masset_bake_cache\\e[00m\n-rw-r3--r--   1 rchen   devteam  83886080 Jun 12 11:47  level_03_lightmaps.bake\n-rw-r--r--   1 rchen   devteam     2048 Jun 12 11:47  level_03_lightmaps.bake.meta\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-systemd-logind.service-eJqXHf\\e[00m\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-chronyd.service-KmRtYw\\e[00m\nsrw-rw-rw-   1 root    root           0 Jun  3 09:12  .X11-unix/X0\n-rw-r--r--   1 guest   guest     1048576 Jun 12 13:58  unity_crash_20250612_135812.dmp\n-rw-r--r--   1 guest   guest        512 Jun 12 13:58  unity_crash_20250612_135812.log\ndrwxr-xr-x   2 guest   guest       4096 Jun 12 14:22  \\e[01;34mssh-jKd9x2Lm4P\\e[00m\ndrwxr-xr-x   2 guest   guest       4096 Jun 12 14:26  \\e[01;34mbm_dir\\e[00m'

L36  cmd_id=state_rmdir_bm_dir  bytes=1454  md5=fe2647c86f3167a28b2ab6100ac6b4a6
     cleaned_output = '\\e[01;34mdrwxrwxrwt\\e[00m 12 root   root       4096 Jun 12 14:18  .\ndrwxr-xr-x  20 root   root       4096 Jun  3 09:12  ..\n-rw-------   1 guest   guest        61 Jun 12 14:24  .X0-lock\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.X11-unix\\e[00m\ndrwxrwxrwt   2 guest   guest       4096 Jun 12 14:22  \\e[01;34m.ICE-unix\\e[00m\ndrwx------   3 guest   guest       4096 Jun 12 14:22  \\e[01;34msnap-private-tmp\\e[00m\ndrwxr-xr-x   2 rchen   devteam     4096 Jun 12 11:03  \\e[01;34masset_bake_cache\\e[00m\n-rw-r--r--   1 rchen   devteam  83886080 Jun 12 11:47  level_03_lightmaps.bake\n-rw-r--r--   1 rchen   devteam     2048 Jun 12 11:47  level_03_lightmaps.bake.meta\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-systemd-logind.service-eJqXHf\\e[00m\ndrwxr-xr-x   2 root    root        4096 Jun  3 09:12  \\e[01;34msystemd-private-2f4a8c9e1b7d4a3f9e2c8d1a4b5c6d7e-chronyd.service-KmRtYw\\e[00m\nsrw-rw-rw-   1 root    root           0 Jun  3 09:12  .X11-unix/X0\n-rw-r--r--   1 guest   guest     1048576 Jun 12 13:58  unity_crash_20250612_135812.dmp\n-rw-r--r--   1 guest   guest        512 Jun 12 13:58  unity_crash_20250612_135812.log\ndrwxr-xr-x   2 guest   guest       4096 Jun 12 14:22  \\e[01;34mssh-jKd9x2Lm4P\\e[00m\ndrwxr-xr-x   2 guest   guest       4096 Jun 12 14:26  \\e[01;34mbm_dir\\e[00m'
```

## Limits of this check

* Detection is signature-based, so any row that prints nothing, prints a home listing, or
  prints text outside the signature set is excluded rather than classified — those are the
  NOT FOUND rows listed above.
* "Lag" is a row offset. It does not assert a cause; the table only records which earlier
  command's text arrived and whether a timeout or the password prompt sits next to it.
* Runs 2, 3, 5, 6, 9, 10, 11, 12, 13 and 16 produced no attributable shift. In several of
  them (2, 9, 16) line 26 returns `Matching Defaults entries …` with no prompt and no timeout,
  so they are not silent failures of the same kind.
