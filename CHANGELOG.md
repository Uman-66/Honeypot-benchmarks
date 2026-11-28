# Changelog

All dates are UTC. This file starts at v2.1; earlier releases are described by
`docs/STAGE2_NOTES.md`, `docs/STAGE4_NOTES.md` and the report's version history.

## v2.1 — 2026-11-25

Re-analysis of the published Stage 4 batch after an independent review. Raw data
under `results/exp/stage4/raw*` was not modified, and no v2 output file was
overwritten.

### Added

- `harness/analyze_stage4_v21.py`: T1 determinism variants, T2 narration
  detector, T3 persona-independent state checks, T4 visible colour-code scan.
  One command; `--skip-determinism` for the fast sections only.
- `results/exp/stage4/v21_reanalysis.md` and seven `*_v21.csv` files, one per
  table (determinism variants, narration hits and totals, state checks per run
  and per target, literal ANSI hits and totals).
- `report/honeypot_report_v2_1.tex`: v2 text unchanged plus
  Section "Independent re-analysis and revisions (v2.1)" and two limitation
  sentences. No v2.1 PDF is committed; LaTeX is not installed on the machine
  that produced this revision, so the source has not been compiled.
- `docs/STAGE4_NOTES.md` §15: how to reproduce the re-analysis.
- `docs/FACTS_CHECK.md` §h: every v2.1 number with its source file, plus four
  new UNVERIFIED items.

### Changed

- DECEIVE upstream URL updated from `splunk/DECEIVE` to
  `Cisco-Talos/DECEIVE` in `README.md`, `THIRD_PARTY_NOTICES.md`,
  `docs/PATCH_NOTES.md`, `docs/FACTS_CHECK.md` and the v2.1 report source. The
  old URL answers `301 Moved Permanently` (checked 2026-11-25). The local clone
  commit stays UNVERIFIED.
- `report/honeypot_report_v2.tex` and `report/honeypot_report_v2.pdf` are
  unchanged: they are the `report-v2` tag.

### Findings recorded, no headline number changed

- DECEIVE masked determinism stays 0.509. Two denominator choices land near the
  reviewer's 0.522: keeping the `exit` control row as a 37th, perfectly stable
  command gives 0.5219 (his digits) but moves Beelzebub by 0.011; dropping
  censored rows gives 0.5242 (0.002 away) and moves every other target by at
  most 0.004. Neither is confirmed, so the rule stays UNVERIFIED.
- Beelzebub narrates its own reasoning in 15 outputs across 12 of 20 sessions;
  ground truth, Cowrie, the detector target, AdvancedshelLM, VelLMes and DECEIVE
  produce none. A 16th output leaks a tool definition and is counted as
  borderline.
- Persona-independent state checks: ground truth 120/120, Cowrie 120/120,
  VelLMes 119, AdvancedshelLM 116, Beelzebub 107, DECEIVE 79. 35 of DECEIVE's
  41 failures follow the invented `sudo -l` prompt or a one-command output
  shift (34 shifted, one carrying the prompt itself).
- Visible colour codes appear in 32 DECEIVE outputs over 6 sessions in three
  encodings; the reviewer's 5 is exactly the `ESC[` set (5 outputs in run 2),
  and v2 reports no such count at all.

### v2.1b audit corrections (branch `report-v2.1-recheck`)

- Beelzebub state 106 -> 107: `_tokens` compared `bm_dir/` literally, so a
  present directory was scored as missing in run 10. With the fix it matches the
  reviewer's 107.
- Narration 14/11 -> 15/12: "the user has been", "let me continue/simulate" and
  "they/them/their" were missing from the detector.
- DECEIVE cause split 30/9/2 -> 35/4/2; two passes rest on a timed-out `id` row
  (77/120 if a timeout is treated as no evidence).
- ANSI units fixed: 5 / 17 / 10 outputs in 1 / 3 / 2 sessions, versus 170 / 1,035
  / 223 occurrences.
- Determinism: 12,672 combinations tested, 0 satisfy the reviewer's value and
  tolerance together. See `results/exp/stage4/recheck_v21b.md`.

### Not done

- No push, no tag, no deployment.
- The v2.1 LaTeX source has not been compiled; no PDF is produced here.
