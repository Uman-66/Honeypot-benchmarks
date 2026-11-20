# Withheld files

Some benchmark outputs are deliberately **not published** in this repository. They stay
on the author's disk unchanged; the SHA-256 values below let a reviewer confirm that any
copy supplied on request is the one used for the report.

## Why these files are withheld

These galah HTTP raw bodies contain model-fabricated credential-like strings that trigger
GitHub secret scanning. Their provenance cannot be certified, so they are not published.
The galah counts in `BENCHMARK.md` and `summary.md` derive from these files and cannot be
re-derived from this repo. Files available to reviewers on request.

Concretely: galah is an LLM-driven HTTP honeypot, so its responses are generated text. Its
output includes realistic-looking `sk_live_…` / `sk_prod_…` strings that the model
invented. GitHub push protection rejects any push containing them (`GH013`, "Push cannot
contain secrets"), and the author cannot prove whether a given string is fabricated or a
value the model memorised from training data. Publishing them would be worse than
withholding them, and rewriting the bodies would break the claim that the raw output is
unmodified.

Earlier revisions of `.gitignore` excluded this whole directory for exactly this reason.

## Files withheld (9)

| Path | Bytes | SHA-256 |
|---|---:|---|
| `results/raw_http/galah_run01.jsonl` | 27,805 | `b8e50732bbf7a85bcb276d75f00cd3e905a8230b8890b7da5a78eeb2966abf66` |
| `results/raw_http/galah_run02.jsonl` | 29,717 | `d107bcc753658868b155544b053a8aea773b7f82655ca5a1d3c79d504fbed490` |
| `results/raw_http/galah_run03.jsonl` | 31,464 | `c47425fd8a1c489e5b97a27908badd1874baf6a295df128a7d6fcec6023a6107` |
| `results/raw_http/galah_run04.jsonl` | 25,749 | `4286a1b991816cfac05e2fb8b45894eff8d6081f260894537f327da66c239592` |
| `results_pilot/raw_http/galah_run02.jsonl` | 33,471 | `ee0905c5d0033cd4e1beb348b9fe2f65d366cb9e977af37db65e192dadba7ba0` |
| `results_pilot/raw_http/galah_run03.jsonl` | 31,166 | `0c76f2e7fd64415dbfb4a943c5cf9604201f9cc19ccc57313a1708d8b1e4f15c` |
| `results_pilot/raw_http/galah_run04.jsonl` | 29,243 | `ee67f4eb63e111b09f8fdc0d75975c4abc89d6e61beda611a529b4e43ce5c61d` |
| `results_pilot/raw_http/galah_run05.jsonl` | 28,934 | `e4e2316c94f6cb4a4de427c2e805d41366a1f9902689ef220c9ce7f435f01cc9` |
| `results_pilot/honeypot_logs/galah/galah.json` | 6,698 | `2c14c38ef8f53c3f80bf5fe8724693e74aef5be05f8d0fc97efb6b1d365fb788` |

Verify a supplied copy with:

```
sha256sum results/raw_http/galah_run01.jsonl
```

## What remains published

The galah evidence that does not contain those strings is in the repository and can be
checked directly:

- `results/summary.md` and `results/summary.csv` — the galah row: 11/100 HTTP 5xx,
  six distinct `Server` header values, 12 header-name-set inconsistencies, 0.2364 repeat
  similarity, 25/94 comparable statuses against nginx.
- `results/http_requests_long.csv` — the per-request table for galah and ground truth
  (scanned clean; it carries no response body text).
- `results/raw_http/groundtruth_http_run01..05.jsonl` — the nginx side of every comparison.
- `results/raw_http/galah_run05.jsonl` and `results_pilot/raw_http/galah_run01.jsonl` —
  the two galah runs that contained none of the matched strings, so they stayed in.

## Effect on reproducibility

Re-running the harness (`harness/run_http.py` against `docker/galah.compose.yaml`)
regenerates these files, but a regenerated run will not be byte-identical to the withheld
ones: galah's responses come from a shared LLM endpoint and vary run to run. The published
`summary.md` values are therefore the record for the reported batch.
