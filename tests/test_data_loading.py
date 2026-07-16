import json

import pytest

from parallel_classifier import (
    event_to_text,
    load_events,
    load_prompt,
    normalize_events,
    parse_labels,
    resolve_target_entity,
    stable_event_id,
)


# -- parse_labels --------------------------------------------------------

def test_parse_labels_splits_and_strips():
    assert parse_labels("Black Swan, Gray Rhino ,Gray Swan") == [
        "Black Swan",
        "Gray Rhino",
        "Gray Swan",
    ]


def test_parse_labels_rejects_empty():
    with pytest.raises(ValueError):
        parse_labels("  ,  ,")


# -- load_prompt ----------------------------------------------------------

def test_load_prompt_reads_and_strips(tmp_path):
    path = tmp_path / "prompt.md"
    path.write_text("\n  Classify this.  \n", encoding="utf-8")
    assert load_prompt(path) == "Classify this."


def test_load_prompt_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompt(tmp_path / "does-not-exist.md")


def test_load_prompt_empty_file_raises(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_prompt(path)


# -- load_events ------------------------------------------------------------

def test_load_events_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"id": "1", "title": "A"}\n\n{"id": "2", "title": "B"}\n',
        encoding="utf-8",
    )
    events = load_events(path)
    assert events == [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]


def test_load_events_jsonl_invalid_json_raises(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_events(path)


def test_load_events_jsonl_non_object_line_raises(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_events(path)


def test_load_events_json_list(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps([{"id": "1"}, {"id": "2"}]), encoding="utf-8")
    assert load_events(path) == [{"id": "1"}, {"id": "2"}]


def test_load_events_json_events_wrapper(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": [{"id": "1"}]}), encoding="utf-8")
    assert load_events(path) == [{"id": "1"}]


def test_load_events_json_bad_shape_raises(tmp_path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"not_events": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_events(path)


def test_load_events_csv(tmp_path):
    path = tmp_path / "events.csv"
    path.write_text("id,title\n1,Alpha\n2,Beta\n", encoding="utf-8")
    events = load_events(path)
    assert events == [
        {"id": "1", "title": "Alpha"},
        {"id": "2", "title": "Beta"},
    ]


def test_load_events_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_events(tmp_path / "nope.jsonl")


def test_load_events_unsupported_suffix_raises(tmp_path):
    path = tmp_path / "events.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        load_events(path)


# -- event_to_text ----------------------------------------------------------

def test_event_to_text_prefers_explicit_text_field():
    event = {"description": "fallback", "summary": "the real text"}
    assert event_to_text(event, "summary") == "the real text"


def test_event_to_text_falls_back_to_common_fields():
    event = {"title": "Headline", "description": "Body text"}
    text = event_to_text(event, None)
    assert "description: Body text" in text
    assert "title: Headline" in text


def test_event_to_text_falls_back_to_full_json_dump():
    event = {"custom_field": "value"}
    text = event_to_text(event, None)
    assert json.loads(text) == event


# -- stable_event_id ----------------------------------------------------------

def test_stable_event_id_is_deterministic():
    event = {"title": "A", "date": "2026-01-01"}
    assert stable_event_id(event) == stable_event_id(dict(event))


def test_stable_event_id_differs_for_different_events():
    assert stable_event_id({"title": "A"}) != stable_event_id({"title": "B"})


def test_stable_event_id_is_16_hex_chars():
    event_id = stable_event_id({"title": "A"})
    assert len(event_id) == 16
    int(event_id, 16)  # raises ValueError if not hex


# -- resolve_target_entity ---------------------------------------------------

def test_resolve_target_entity_prefers_per_event_value():
    event = {"target_entity": "Apple"}
    assert resolve_target_entity(event, "target_entity", "OpenAI") == "Apple"


def test_resolve_target_entity_falls_back_to_default():
    event = {}
    assert resolve_target_entity(event, "target_entity", "OpenAI") == "OpenAI"


def test_resolve_target_entity_strips_whitespace():
    event = {"target_entity": "  Apple  "}
    assert resolve_target_entity(event, "target_entity", None) == "Apple"


def test_resolve_target_entity_raises_without_either():
    with pytest.raises(ValueError):
        resolve_target_entity({}, "target_entity", None)


def test_resolve_target_entity_ignores_blank_event_value():
    event = {"target_entity": "   "}
    assert resolve_target_entity(event, "target_entity", "OpenAI") == "OpenAI"


# -- normalize_events ---------------------------------------------------------

def _normalize(events, **overrides):
    kwargs = dict(
        id_field="event_id",
        text_field=None,
        target_entity_field="target_entity",
        default_target_entity=None,
    )
    kwargs.update(overrides)
    return normalize_events(events, **kwargs)


def test_normalize_events_assigns_internal_fields():
    events = [
        {"event_id": "1", "title": "A", "description": "d", "target_entity": "Apple"}
    ]
    [event] = _normalize(events)
    assert event["_event_id"] == "1"
    assert event["_target_entity"] == "Apple"
    assert "d" in event["_event_text"] or "A" in event["_event_text"]


def test_normalize_events_id_falls_back_through_chain():
    ## id_field ("ref") absent -> falls back to "id" -> falls back to hash.
    events = [{"id": "abc", "title": "A", "target_entity": "Apple"}]
    [event] = _normalize(events, id_field="ref")
    assert event["_event_id"] == "abc"


def test_normalize_events_id_falls_back_to_hash_when_nothing_set():
    events = [{"title": "A", "target_entity": "Apple"}]
    [event] = _normalize(events, id_field="ref")
    assert event["_event_id"] == stable_event_id({"title": "A", "target_entity": "Apple"})


def test_normalize_events_duplicate_id_raises():
    events = [
        {"event_id": "1", "title": "A", "target_entity": "Apple"},
        {"event_id": "1", "title": "B", "target_entity": "Apple"},
    ]
    with pytest.raises(ValueError, match="Duplicate event_id"):
        _normalize(events)


def test_normalize_events_falls_back_to_json_dump_when_no_text_fields_present():
    ## event_to_text's final fallback (dump the whole event as text) means
    ## normalize_events' "no usable text" guard can't actually trigger unless
    ## event_to_text itself is changed to allow returning "".
    events = [{"event_id": "1", "target_entity": "Apple"}]
    [event] = _normalize(events)
    assert json.loads(event["_event_text"]) == events[0]


def test_normalize_events_missing_target_entity_raises():
    events = [{"event_id": "1", "title": "A"}]
    with pytest.raises(ValueError, match="target entity"):
        _normalize(events)


def test_normalize_events_default_target_entity_applies_to_all():
    events = [
        {"event_id": "1", "title": "A"},
        {"event_id": "2", "title": "B", "target_entity": "Apple"},
    ]
    normalized = _normalize(events, default_target_entity="OpenAI")
    assert normalized[0]["_target_entity"] == "OpenAI"
    assert normalized[1]["_target_entity"] == "Apple"
