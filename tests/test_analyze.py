import sys
import csv
import time
from pathlib import Path


ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

from analyze import (
    _analyze_ssh_target,
    _latency_stats,
    _similarity,
)
from run_http import _csv_without_pair


def test_latency_stats_censors_timeout_values():
    stats = _latency_stats([1.0, 3.0], timeout_count=2)
    assert stats["median"] == 2.0
    assert stats["p95"] == 2.9
    assert stats["timeout_count"] == 2


def test_analyzer_accounts_exit_and_malformed_rows():
    commands = {
        "state_pwd_after_cd": {"host_specific": False},
        "exit": {"host_specific": False},
    }
    records = [
        {"run": 1, "cmd_id": "state_pwd_after_cd", "latency_s": 1.0,
         "timed_out": False, "cleaned_output": "/tmp"},
        {"run": 1, "cmd_id": "exit"},
        {"run": 1, "cmd_id": "", "latency_s": 0.0, "timed_out": False},
    ]
    result = _analyze_ssh_target("synthetic", records, None, "llm", commands)
    assert result["accounting"]["n_expected"] == 1
    assert result["accounting"]["n_used"] == 1
    assert result["accounting"]["n_excluded_malformed"] == 1


def test_state_check_is_invalid_when_dependency_times_out():
    commands = {
        "state_pwd_after_cd": {"host_specific": False},
        "exit": {"host_specific": False},
    }
    records = [
        {"run": 1, "cmd_id": "state_pwd_after_cd", "latency_s": 90.0,
         "timed_out": True, "cleaned_output": ""},
    ]
    result = _analyze_ssh_target("synthetic", records, None, "llm", commands)
    assert result["state_consistency"][0]["pwd_after_cd_is_tmp"] == "invalid (timeout)"


def test_csv_without_pair_handles_large_field(tmp_path):
    csv_path = tmp_path / "records.csv"
    large_value = "x" * 200_000
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["target", "run", "value"])
        writer.writeheader()
        writer.writerow({"target": "keep", "run": 1, "value": large_value})
        writer.writerow({"target": "remove", "run": 1, "value": "small"})

    _csv_without_pair(csv_path, "remove", 1)

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{"target": "keep", "run": "1", "value": large_value}]


def test_similarity_caps_large_outputs_and_finishes_quickly():
    large_value = "x" * 200_000
    started = time.perf_counter()
    similarity = _similarity(large_value, large_value)
    elapsed = time.perf_counter() - started

    assert similarity == 1.0
    assert elapsed < 3


def test_output_metrics_report_leaked_and_clean_prompts():
    large_value = "x" * 200_001
    records = [
        {
            "run": 1,
            "cmd_id": "command",
            "cleaned_output": f"output\nuser@host:~$ \n{large_value}",
        },
        {
            "run": 2,
            "cmd_id": "command",
            "cleaned_output": "output\nuser@host:~$ ",
        },
    ]

    result = _analyze_ssh_target(
        "synthetic",
        records,
        None,
        "llm",
        {"command": {"host_specific": False}},
    )

    assert result["output_length_stats"]["max"] == len(
        records[0]["cleaned_output"]
    )
    assert result["output_length_stats"]["oversized_outputs"] == 1
    assert result["transcript_leakage"] == {
        "leaked": 1,
        "total": 2,
        "rate": 0.5,
    }
    assert result["similarity_comparisons_truncated"] == 1
