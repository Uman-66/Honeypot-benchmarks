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

## Detector Target: llm-honeypot

*This target is excluded from all fidelity, similarity, and aggregate metrics.*

The llm-honeypot Cowrie fork hides prompt-injection instructions in ANSI
conceal sequences (ESC[8m … ESC[0m) in the output of `pwd`, `whoami`, `ps`,
`ls`, and `df`.  The harness records whether the trap markers appear in the
raw output and whether they survive ANSI stripping into the cleaned output.

No data found for llm-honeypot.

---

## HTTP Targets
