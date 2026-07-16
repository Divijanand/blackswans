import json

from parallel_classifier import load_existing_results


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_load_existing_results_missing_file_returns_empty(tmp_path):
    assert load_existing_results(tmp_path / "missing.jsonl", retry_failed=False) == set()


def test_load_existing_results_default_skips_every_seen_id(tmp_path):
    path = tmp_path / "results.jsonl"
    _write_jsonl(
        path,
        [
            {"event_id": "1", "status": "ok"},
            {"event_id": "2", "status": "request_error"},
        ],
    )
    assert load_existing_results(path, retry_failed=False) == {"1", "2"}


def test_load_existing_results_retry_failed_only_skips_ok(tmp_path):
    path = tmp_path / "results.jsonl"
    _write_jsonl(
        path,
        [
            {"event_id": "1", "status": "ok"},
            {"event_id": "2", "status": "request_error"},
            {"event_id": "3", "status": "parse_error"},
        ],
    )
    assert load_existing_results(path, retry_failed=True) == {"1"}


def test_load_existing_results_ignores_malformed_lines(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text(
        '{"event_id": "1", "status": "ok"}\nnot json\n\n{"event_id": "2", "status": "ok"}\n',
        encoding="utf-8",
    )
    assert load_existing_results(path, retry_failed=False) == {"1", "2"}


def test_load_existing_results_ignores_rows_without_event_id(tmp_path):
    path = tmp_path / "results.jsonl"
    _write_jsonl(path, [{"status": "ok"}, {"event_id": "1", "status": "ok"}])
    assert load_existing_results(path, retry_failed=False) == {"1"}
