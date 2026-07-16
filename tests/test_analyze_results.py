import json

import pytest

from analyze_results import (
    classification_counts,
    estimate_cost,
    load_ground_truth,
    load_jsonl,
    load_manifest,
    per_model_breakdown,
    score_against_ground_truth,
    status_counts,
    usage_totals,
)
from parallel_classifier import write_run_manifest


ROWS = [
    {
        "event_id": "1",
        "model": "model-a",
        "status": "ok",
        "classification": "Black Swan",
        "latency_seconds": 1.0,
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    },
    {
        "event_id": "2",
        "model": "model-a",
        "status": "ok",
        "classification": "Gray Swan",
        "latency_seconds": 2.0,
        "usage": {"prompt_tokens": 200, "completion_tokens": 40, "total_tokens": 240},
    },
    {
        "event_id": "3",
        "model": "model-a",
        "status": "parse_error",
    },
]


# -- load_jsonl -------------------------------------------------------------

def test_load_jsonl_reads_rows(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"a": 2}]


def test_load_jsonl_raises_on_invalid_json(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_jsonl(path)


# -- load_manifest ------------------------------------------------------------

def test_load_manifest_returns_none_when_missing(tmp_path):
    assert load_manifest(tmp_path / "results.jsonl") is None


def test_load_manifest_reads_sidecar(tmp_path):
    results_path = tmp_path / "results.jsonl"
    write_run_manifest(results_path, {"model": "test-model"})
    assert load_manifest(results_path) == {"model": "test-model"}


# -- aggregation --------------------------------------------------------------

def test_status_counts():
    counts = status_counts(ROWS)
    assert counts["ok"] == 2
    assert counts["parse_error"] == 1


def test_classification_counts_only_counts_ok_rows():
    counts = classification_counts(ROWS)
    assert counts == {"Black Swan": 1, "Gray Swan": 1}


def test_per_model_breakdown():
    breakdown = per_model_breakdown(ROWS)
    assert breakdown["model-a"] == {"total": 3, "ok": 2}


def test_usage_totals_sums_across_rows():
    totals = usage_totals(ROWS)
    assert totals == {"prompt_tokens": 300, "completion_tokens": 60, "total_tokens": 360}


def test_estimate_cost_none_without_rates():
    assert estimate_cost(usage_totals(ROWS), None, None) is None


def test_estimate_cost_with_rates():
    totals = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}
    assert estimate_cost(totals, 1.0, 2.0) == 3.0


# -- ground truth ---------------------------------------------------------------

def test_load_ground_truth(tmp_path):
    path = tmp_path / "truth.jsonl"
    path.write_text(
        '{"event_id": "1", "expected_classification": "Black Swan"}\n'
        '{"event_id": "2", "expected_classification": "Gray Swan"}\n',
        encoding="utf-8",
    )
    assert load_ground_truth(path) == {"1": "Black Swan", "2": "Gray Swan"}


def test_load_ground_truth_raises_on_missing_fields(tmp_path):
    path = tmp_path / "truth.jsonl"
    path.write_text('{"event_id": "1"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_ground_truth(path)


def test_score_against_ground_truth_only_scores_ok_rows_that_match():
    ground_truth = {
        "1": "Black Swan",   # correct
        "2": "Black Swan",   # mismatch (actual is Gray Swan)
        "3": "Black Swan",   # status=parse_error, excluded from matched
        "4": "Black Swan",   # not in results at all
    }
    score = score_against_ground_truth(ROWS, ground_truth)
    assert score["matched"] == 2
    assert score["correct"] == 1
    assert score["accuracy"] == 0.5
    assert score["mismatches"] == [
        {"event_id": "2", "expected": "Black Swan", "actual": "Gray Swan"}
    ]


def test_score_against_ground_truth_accuracy_none_when_nothing_matched():
    score = score_against_ground_truth(ROWS, {"999": "Black Swan"})
    assert score["matched"] == 0
    assert score["accuracy"] is None
