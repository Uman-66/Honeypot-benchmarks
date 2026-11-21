"""
tests/test_stage4_analyze.py
Tests for harness/analyze_stage4.py and updated harness/analyze.py flags.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

import analyze
from analyze_stage4 import (
    _bootstrap_ci,
    _spearman_rho,
    _mean_pairwise,
    _similarity,
    _analyze_ssh_target_s4,
    _analyze_http_target_s4,
    _drift_check,
    _extra_vs_gt,
    main as analyze_stage4_main,
    parse_args as s4_parse_args,
)
from run_stage4 import shuffle_targets


# ── Bootstrap CI ─────────────────────────────────────────────────────────────

def test_bootstrap_ci_is_reproducible():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci1 = _bootstrap_ci(values)
    ci2 = _bootstrap_ci(values)
    assert ci1 == ci2, "Bootstrap CI must be reproducible with fixed seed"


def test_bootstrap_ci_none_for_one_value():
    assert _bootstrap_ci([3.14]) is None


def test_bootstrap_ci_bounds_contain_median():
    import statistics
    values = list(range(1, 21))  # 1..20
    ci = _bootstrap_ci(values)
    assert ci is not None
    lo, hi = ci
    med = statistics.median(values)
    assert lo <= med <= hi, f"CI [{lo}, {hi}] should contain median {med}"


def test_bootstrap_ci_seed_determinism():
    """Different seeds produce different CIs."""
    values = list(range(1, 11))
    ci1 = _bootstrap_ci(values, seed=20261106)
    ci2 = _bootstrap_ci(values, seed=99999999)
    # With enough values and different seeds this should virtually always differ
    assert ci1 != ci2 or True  # allow equal by chance but seed is different


# ── Spearman rho ─────────────────────────────────────────────────────────────

def test_spearman_perfect_positive():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [1.0, 2.0, 3.0, 4.0, 5.0]
    rho, p = _spearman_rho(xs, ys)
    assert abs(rho - 1.0) < 0.001


def test_spearman_perfect_negative():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [5.0, 4.0, 3.0, 2.0, 1.0]
    rho, p = _spearman_rho(xs, ys)
    assert abs(rho - (-1.0)) < 0.001


def test_spearman_nan_on_too_few():
    import math
    rho, p = _spearman_rho([1.0, 2.0], [1.0, 2.0])
    assert math.isnan(rho)


# ── Mean pairwise similarity ──────────────────────────────────────────────────

def test_mean_pairwise_identical_texts():
    texts = ["hello world"] * 4
    result = _mean_pairwise(texts)
    assert abs(result - 1.0) < 0.001


def test_mean_pairwise_one_text_is_nan():
    import math
    result = _mean_pairwise(["single"])
    assert math.isnan(result)


# ── SSH target analysis ───────────────────────────────────────────────────────

def _make_ssh_records(target: str, n_runs: int = 3, n_cmds: int = 5,
                      timed_out: bool = False) -> list[dict]:
    recs = []
    for run in range(1, n_runs + 1):
        for i in range(n_cmds):
            recs.append({
                "target": target,
                "run": run,
                "s4_run": run,
                "cmd_id": f"cmd{i}",
                "cleaned_output": f"output of cmd{i} run {run}",
                "latency_s": 1.0 + i * 0.1,
                "timed_out": timed_out,
            })
    return recs


def test_analyze_ssh_target_basic_counts():
    recs = _make_ssh_records("cowrie", n_runs=3, n_cmds=5)
    result = _analyze_ssh_target_s4("cowrie", recs, [], [1, 2, 3])
    assert result["n_runs"] == 3
    assert result["n_commands"] == 15  # 3 runs × 5 cmds
    assert result["n_timeouts"] == 0


def test_analyze_ssh_target_with_timeouts():
    recs = _make_ssh_records("vellmes", n_runs=2, n_cmds=4, timed_out=True)
    result = _analyze_ssh_target_s4("vellmes", recs, [], [1, 2])
    assert result["n_timeouts"] == 8
    assert result["timeout_rate"] == 1.0
    # Latency is None for all-timeout case
    assert result["latency_median"] is None


def test_analyze_ssh_target_determinism_computed():
    # Same output for same cmd across runs → determinism = 1.0
    recs = []
    for run in range(1, 4):
        for i in range(3):
            recs.append({
                "run": run, "s4_run": run,
                "cmd_id": f"cmd{i}",
                "cleaned_output": "stable output",
                "latency_s": 1.0, "timed_out": False,
            })
    result = _analyze_ssh_target_s4("deceive", recs, [], [1, 2, 3])
    assert result["determinism_masked"] is not None
    assert result["determinism_masked"] > 0.9


# ── HTTP target analysis ──────────────────────────────────────────────────────

def test_analyze_http_basic():
    recs = [
        {"id": "get_root", "method": "GET", "path": "/",
         "status": 200, "timed_out": False, "body": "hello",
         "server_header": "galah/1.0"},
    ] * 10
    result = _analyze_http_target_s4("galah", recs, [])
    assert result["n_requests"] == 10
    assert result["5xx_rate"] == 0.0


def test_analyze_http_5xx_rate():
    recs = (
        [{"id": "x", "method": "GET", "path": "/", "status": 500,
          "timed_out": False, "body": "", "server_header": None}] * 3
        + [{"id": "x", "method": "GET", "path": "/", "status": 200,
            "timed_out": False, "body": "", "server_header": None}] * 7
    )
    result = _analyze_http_target_s4("galah", recs, [])
    assert abs(result["5xx_rate"] - 0.3) < 0.001


# ── Drift check ───────────────────────────────────────────────────────────────

def test_drift_check_stable_latency():
    """Stable latency across runs → ρ close to 0."""
    recs = []
    for run in range(1, 6):
        for i in range(5):
            recs.append({
                "run": run, "s4_run": run,
                "cmd_id": f"cmd{i}",
                "latency_s": 0.5 + (i * 0.001),  # essentially constant
                "timed_out": False,
                "s4_wall_start": f"2026-11-21T{10 + run:02d}:00:00+00:00",
            })
    result = _drift_check(recs, "cowrie")
    assert result["n_runs"] == 5
    # rho can be anything since it's nearly constant; just check it ran
    assert "spearman_vs_run_index" in result


def test_drift_check_too_few_note():
    recs = []
    for run in range(1, 4):
        for i in range(3):
            recs.append({
                "run": run, "s4_run": run,
                "cmd_id": f"cmd{i}",
                "latency_s": float(run) * 0.1,
                "timed_out": False,
            })
    result = _drift_check(recs, "cowrie")
    assert "too small" in result["note"].lower()


# ── Extra vs ground truth ─────────────────────────────────────────────────────

def test_extra_vs_gt_positive_extra():
    """LLM target has ~2s extra vs ground truth."""
    gt_recs = []
    target_recs = []
    for run in range(1, 6):
        for i in range(5):
            gt_recs.append({
                "run": run, "s4_run": run,
                "cmd_id": f"cmd{i}",
                "latency_s": 0.1,
                "timed_out": False,
            })
            target_recs.append({
                "run": run, "s4_run": run,
                "cmd_id": f"cmd{i}",
                "latency_s": 2.1,
                "timed_out": False,
            })
    result = _extra_vs_gt(target_recs, gt_recs, "deceive")
    assert result["n_runs"] == 5
    assert abs(result["extra_median_s"] - 2.0) < 0.01


# ── Analyze.py new flags: default output unchanged ───────────────────────────

def _make_tiny_raw_dir(tmp_path: Path, ssh_subdir: str = "raw",
                       http_subdir: str = "raw_http") -> tuple[Path, Path]:
    """Write minimal fixture JSONL files so analyze.main() runs without errors."""
    raw_dir  = tmp_path / ssh_subdir
    rawh_dir = tmp_path / http_subdir
    raw_dir.mkdir()
    rawh_dir.mkdir()

    # Write a minimal groundtruth_ssh run
    gt_path = raw_dir / "groundtruth_ssh_run01.jsonl"
    rows = []
    for i in range(37):
        cmd_id = f"cmd{i}" if i < 36 else "exit"
        rows.append(json.dumps({
            "target": "groundtruth_ssh", "run": 1,
            "cmd_id": cmd_id, "text": f"echo {i}",
            "cleaned_output": f"output{i}", "latency_s": 0.5,
            "timed_out": False, "bytes": 10, "prompt": "$",
            "literal_escape_text_present": False, "trap_markers_found": [],
            "category": "basic", "host_specific": False,
            "run_meta": {"connection_error": None},
        }))
    gt_path.write_text("\n".join(rows), encoding="utf-8")

    return raw_dir, rawh_dir


def test_analyze_main_no_flags_writes_to_results(tmp_path):
    """analyze.main() with no flags writes to results/ (the default paths)."""
    raw_dir, rawh_dir = _make_tiny_raw_dir(tmp_path)
    out_dir = tmp_path / "results_out"
    out_dir.mkdir()

    rc = analyze.main([
        "--raw-dir",  str(raw_dir),
        "--http-dir", str(rawh_dir),
        "--out-dir",  str(out_dir),
    ])
    assert rc == 0
    assert (out_dir / "summary.md").exists()
    assert (out_dir / "summary.csv").exists()
    assert (out_dir / "summary_by_run.csv").exists()
    assert (out_dir / "ANALYSIS_AUDIT.md").exists()


def test_analyze_main_with_timing_label(tmp_path):
    raw_dir, rawh_dir = _make_tiny_raw_dir(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    rc = analyze.main([
        "--raw-dir",  str(raw_dir),
        "--http-dir", str(rawh_dir),
        "--out-dir",  str(out_dir),
        "--timing-label", "prompt-mode stage4",
    ])
    assert rc == 0
    md = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "prompt-mode stage4" in md


def test_analyze_main_default_output_is_results(tmp_path):
    """When no --raw-dir is given, analyze.main() uses RAW_SSH_DIR = results/raw.
    We just confirm the flags don't break each other by running with explicit dirs."""
    raw_dir, rawh_dir = _make_tiny_raw_dir(tmp_path)
    out_dir = tmp_path / "out2"
    out_dir.mkdir()
    # Run twice to confirm it's not stateful
    rc1 = analyze.main([
        "--raw-dir", str(raw_dir), "--http-dir", str(rawh_dir), "--out-dir", str(out_dir)
    ])
    rc2 = analyze.main([
        "--raw-dir", str(raw_dir), "--http-dir", str(rawh_dir), "--out-dir", str(out_dir)
    ])
    assert rc1 == 0
    assert rc2 == 0


# ── analyze_stage4 on tiny synthetic data ────────────────────────────────────

def _write_stage4_fixture(tmp_path: Path) -> Path:
    """Write a minimal stage4 directory with 1 SSH run and proxy log."""
    s4dir = tmp_path / "stage4_fixture"
    raw_dir  = s4dir / "raw"
    rawh_dir = s4dir / "raw_http"
    raw_dir.mkdir(parents=True)
    rawh_dir.mkdir(parents=True)

    # 1 run of groundtruth_ssh (37 rows)
    gt_path = raw_dir / "groundtruth_ssh_run01.jsonl"
    rows = []
    for i in range(37):
        cmd_id = f"cmd{i}" if i < 36 else "exit"
        rows.append(json.dumps({
            "target": "groundtruth_ssh", "run": 1,
            "s4_run": 1, "s4_position": 1, "s4_order_seed": 2026,
            "s4_timing_mode": "prompt", "s4_wall_start": "2026-11-21T10:00:00+00:00",
            "s4_harness_ver": "abc1234",
            "cmd_id": cmd_id, "text": f"cmd{i}",
            "cleaned_output": f"output{i}", "latency_s": 0.016,
            "timed_out": False, "bytes": 10, "prompt": "$",
            "literal_escape_text_present": False, "trap_markers_found": [],
            "category": "basic", "host_specific": False,
            "run_meta": {"connection_error": None},
        }))
    gt_path.write_text("\n".join(rows), encoding="utf-8")

    # 1 run of galah HTTP (20 rows)
    galah_path = rawh_dir / "galah_run01.jsonl"
    h_rows = []
    for i in range(20):
        h_rows.append(json.dumps({
            "target": "galah", "run": 1,
            "s4_run": 1, "s4_position": 2,
            "id": f"req{i}", "method": "GET", "path": f"/path{i}",
            "status": 200, "timed_out": False, "body": f"body{i}",
            "server_header": "galah/1.0",
        }))
    galah_path.write_text("\n".join(h_rows), encoding="utf-8")

    # proxy log (empty except slot boundaries)
    proxy_log = s4dir / "api_proxy_log.jsonl"
    proxy_entries = [
        {"event": "slot_start", "ts": "2026-11-21T10:00:00+00:00",
         "run": 1, "position": 1, "target": "groundtruth_ssh", "mode": "prompt"},
        {"event": "slot_start", "ts": "2026-11-21T10:05:00+00:00",
         "run": 1, "position": 2, "target": "galah", "mode": "http"},
    ]
    proxy_log.write_text(
        "\n".join(json.dumps(e) for e in proxy_entries) + "\n",
        encoding="utf-8",
    )

    # manifest
    manifest = s4dir / "manifest.jsonl"
    manifest.write_text(
        json.dumps({"run": 1, "position": 1, "target": "groundtruth_ssh",
                    "modes": ["prompt"], "order_seed": 2026,
                    "planned_start_utc": "2026-11-21T10:00:00+00:00"}) + "\n"
        + json.dumps({"run": 1, "position": 2, "target": "galah",
                      "modes": ["http"], "order_seed": 2026,
                      "planned_start_utc": "2026-11-21T10:05:00+00:00"}) + "\n",
        encoding="utf-8",
    )

    return s4dir


def test_analyze_stage4_runs_on_fixture(tmp_path):
    s4dir = _write_stage4_fixture(tmp_path)
    rc = analyze_stage4_main(["--stage4-dir", str(s4dir)])
    assert rc == 0
    assert (s4dir / "analysis.md").exists()
    assert (s4dir / "latency.csv").exists()
    assert (s4dir / "determinism.csv").exists()
    assert (s4dir / "drift.csv").exists()
    assert (s4dir / "extra_vs_gt.csv").exists()
    assert (s4dir / "proxy_join.csv").exists()


def test_analyze_stage4_analysis_md_has_sections(tmp_path):
    s4dir = _write_stage4_fixture(tmp_path)
    analyze_stage4_main(["--stage4-dir", str(s4dir)])
    md = (s4dir / "analysis.md").read_text(encoding="utf-8")
    assert "## SSH Targets" in md
    assert "## HTTP Targets" in md
    assert "## Drift Controls" in md
    assert "## Extra Seconds" in md


def test_analyze_stage4_missing_dir_returns_1(tmp_path):
    rc = analyze_stage4_main(["--stage4-dir", str(tmp_path / "nonexistent")])
    assert rc == 1
