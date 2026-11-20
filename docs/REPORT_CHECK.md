# Report verification

The report uses only verified content from `BENCHMARK.md`, `README.md`,
`docs/DOC_VERIFICATION.md`, `docs/FACTS_CHECK.md`, and `results/summary.md`.
No external figure files are used; the report contains tables only.

| Report object | Source line(s) |
|---|---|
| Table 1, final target inventory | `docs/DOC_VERIFICATION.md:152-164` (verified paths, ports, and target inventory sources) |
| Table 2, recorded target configuration | `docs/DOC_VERIFICATION.md:129-139` |
| Table 3, SSH results | `results/summary.md:25-401` (SSH target sections; `docs/DOC_VERIFICATION.md:29-42` confirms completed counts) |
| Table 4, SSH timeout detail | `docs/FACTS_CHECK.md:4-40` |
| HTTP results paragraph | `results/summary.md:586-635` |
| HoneyBee results paragraph | `docs/FACTS_CHECK.md:43-52`; `docs/DOC_VERIFICATION.md:117-127` |
| Findings section | `docs/DOC_VERIFICATION.md:141-149`; `results/summary.md:25-635` |
| Data-quality notes | `docs/DOC_VERIFICATION.md:7-17`, `82-115`; `docs/FACTS_CHECK.md:80-90` |
| Limitations section | `docs/DOC_VERIFICATION.md:166-173`; `docs/FACTS_CHECK.md:80-90` |
| Next steps | `docs/DOC_VERIFICATION.md:141-149`; `BENCHMARK.md:236-240` |
| Figures | None; no figure number is applicable |

## Compilation check

`where pdflatex` and `where latexmk` produced no executable paths in the
available environment, so the report was not compiled. Page count and
overfull-box output are therefore unavailable; no compilation is claimed.
