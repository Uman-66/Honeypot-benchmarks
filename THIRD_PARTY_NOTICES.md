# Third-party notices

This repository benchmarks third-party SSH/HTTP honeypots, LLM deception tools and
baselines. None of that third-party source code is redistributed here: the clones live
in directories that `.gitignore` excludes, and are re-cloned by the reader following
`README.md`.

What this repository *does* contain is (a) original harness/Docker/documentation code
under the MIT licence (see `LICENSE`), and (b) two patch files that are derivative
works of upstream source. Licence texts for every tool below are reproduced verbatim
in `LICENSES/`.

**This file is a record of what was read from each clone. It is not legal advice.**

## Tools that were patched or modified

| Tool | Upstream | Commit | Licence | Modified? |
|---|---|---|---|---|
| HoneyBee | https://github.com/yaaras/honeybee | `dbf62c42604eeae2cfbfd4d36b99bef65555c303` | Apache-2.0 | **Yes** — `patches/honeybee.patch` (28 hunks across 9 files) |
| VelLMes | Clone directory `VelLMes-AI-Deception-Framework/`; upstream URL UNVERIFIED (the clone contains no repository URL — the shelLM README references `https://github.com/stratosphereips/VelLMes-AI-Honeypot`) | `192fa5084df84b38a16f6581939fd3143c350181` | GPL-2.0 | **Yes** — `patches/vellmes.patch` (7 hunks, `VelLMes.py` only) |
| DECEIVE | https://github.com/splunk/DECEIVE | UNVERIFIED (clone has no `.git`) | MIT | Yes, by hand — no patch file (see `docs/PATCH_NOTES.md` §1) |
| Beelzebub | https://github.com/beelzebub-labs/beelzebub | UNVERIFIED (clone has no `.git`) | GPL-3.0 | Yes, by hand — no patch file (§2) |
| AdvancedshelLM | https://github.com/stratosphereips/shelLM | UNVERIFIED (clone has no `.git`) | CC BY-NC-SA 4.0 (NonCommercial) | Yes, by hand — no patch file (§3) |
| galah | https://github.com/0x4d31/galah | UNVERIFIED (clone has no `.git`) | Apache-2.0 | Yes, by hand — no patch file (§4) |
| Cowrie | https://github.com/cowrie/cowrie | v2.6.1, pinned in `README.md`; clone has no `.git` | BSD-3-Clause (`LICENSE.rst`) | No source edit — mounted configuration only (§5) |

## Tools that were run unmodified

| Tool | Upstream | Commit | Licence | Modified? |
|---|---|---|---|---|
| llm-honeypot (Palisade Research) | Repository URL UNVERIFIED — the clone's README links only its dashboard (`https://ai-honeypot.palisaderesearch.org`) and paper (arXiv:2410.13919) | UNVERIFIED (clone has no `.git`) | **No licence file found.** No upstream code is redistributed in this repo | No — run as a Cowrie overlay image |
| Cowrie "peek" overlay | Clone directory `cowrie-peek/`; URL UNVERIFIED | UNVERIFIED | No licence file found. Used read-only to inspect behaviour; nothing is redistributed | No |

## How the licence obligations are met

- **Apache-2.0 (HoneyBee, galah).** `patches/honeybee.patch` carries an Apache-2.0 header
  naming the upstream project and commit; the full licence text is in
  `LICENSES/honeybee-Apache-2.0.txt`. The Apache-2.0 NOTICE-file obligation is discharged
  by keeping that attribution with the patch.
- **GPL-2.0 (VelLMes).** `patches/vellmes.patch` is a derivative work of `VelLMes.py` and
  stays under GPL-2.0, with the full text in `LICENSES/VelLMes-GPL-2.0.txt`. Any binary
  built from the patched source carries the same licence.
- **GPL-3.0 (Beelzebub).** Built from its own source tree with its upstream Dockerfile;
  the edits are documented in `docs/PATCH_NOTES.md` §2, and the text is in
  `LICENSES/beelzebub-GPL-3.0.txt`.
- **MIT (DECEIVE).** `LICENSES/DECEIVE-MIT.txt`.
- **BSD-3-Clause (Cowrie).** `LICENSES/cowrie-BSD-3-Clause.txt`; the image is pulled/built
  unmodified and only config is mounted.
- **CC BY-NC-SA 4.0 (AdvancedshelLM).** `LICENSES/shelLM-CC-BY-NC-SA-4.0.txt`. This is a
  NonCommercial licence, so this benchmark must not be used commercially in a way that
  builds on that tool, and no shelLM code is redistributed here — the Docker image copies
  it from a local clone at build time.
- **No licence file (llm-honeypot, cowrie-peek).** No permission is granted upstream, so
  no code, patch or derivative file for these two is redistributed here; they are only
  referenced as evaluated targets and built locally from the reader's own clone.

## Verified by reading the file

Every licence name above was read from the clone's own `LICENSE` / `LICENSE.rst` on
2026-11-20, except where the row says UNVERIFIED. `docs/FACTS_CHECK.md` §d records the
same audit, including three rows that were previously wrong (DECEIVE was listed as
Apache-2.0, VelLMes as GPL-3.0, and HoneyBee as MIT).
