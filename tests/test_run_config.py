import json

from parallel_classifier import (
    MODEL_TIER_WORKERS,
    add_usage,
    build_run_manifest,
    estimate_cost,
    manifest_path_for,
    resolve_workers,
    write_run_manifest,
)


# -- resolve_workers ------------------------------------------------------

def test_resolve_workers_explicit_value_wins_over_tier():
    assert resolve_workers(7, "tier3") == 7


def test_resolve_workers_uses_tier_default():
    for tier, expected in MODEL_TIER_WORKERS.items():
        assert resolve_workers(None, tier) == expected


def test_resolve_workers_falls_back_to_flat_default():
    assert resolve_workers(None, None) == 10


# -- usage/cost aggregation -----------------------------------------------

def test_add_usage_accumulates_across_calls():
    totals: dict = {}
    add_usage(totals, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    add_usage(totals, {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5})
    assert totals == {"prompt_tokens": 13, "completion_tokens": 7, "total_tokens": 20}


def test_add_usage_ignores_missing_or_none_usage():
    totals: dict = {}
    add_usage(totals, None)
    add_usage(totals, {})
    assert totals == {}


def test_estimate_cost_none_when_rates_missing():
    assert estimate_cost({"prompt_tokens": 1000, "completion_tokens": 1000}, None, None) is None
    assert estimate_cost({"prompt_tokens": 1000, "completion_tokens": 1000}, 1.0, None) is None


def test_estimate_cost_computes_weighted_total():
    totals = {"prompt_tokens": 1_000_000, "completion_tokens": 500_000}
    ## $2 per 1M input + $4 per 1M output at half the volume = $2 + $2 = $4
    assert estimate_cost(totals, 2.0, 4.0) == 4.0


# -- manifest ---------------------------------------------------------------

def test_manifest_path_for_appends_suffix(tmp_path):
    output = tmp_path / "results.jsonl"
    assert manifest_path_for(output) == tmp_path / "results.jsonl.manifest.json"


def test_build_run_manifest_captures_run_config(tmp_path):
    manifest = build_run_manifest(
        input_path=tmp_path / "events.jsonl",
        output_path=tmp_path / "results.jsonl",
        prompt_path=tmp_path / "prompt.md",
        model_id="test-model",
        labels=["Black Swan", "Gray Rhino"],
        structured_mode="json_schema",
        fallback_structured_mode=True,
        temperature=0.0,
        max_tokens=2000,
        workers=10,
        id_field="event_id",
        text_field=None,
        target_entity_field="target_entity",
        default_target_entity="Apple",
        event_count=5,
    )
    assert manifest["model"] == "test-model"
    assert manifest["labels"] == ["Black Swan", "Gray Rhino"]
    assert manifest["default_target_entity"] == "Apple"
    assert manifest["event_count"] == 5
    assert manifest["max_tokens"] == 2000
    assert "started_at" in manifest


def test_write_run_manifest_writes_valid_json(tmp_path):
    output_path = tmp_path / "runs" / "results.jsonl"
    manifest = {"model": "test-model"}

    written_path = write_run_manifest(output_path, manifest)

    assert written_path == manifest_path_for(output_path)
    assert json.loads(written_path.read_text(encoding="utf-8")) == manifest
