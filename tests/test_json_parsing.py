import pytest

from parallel_classifier import (
    normalize_classification,
    normalize_model_result,
    parse_json_object,
    strip_code_fence,
    validate_model_result,
)


LABELS = ["Black Swan", "Gray Rhino", "Gray Swan", "White Swan", "Broken Prior", "Neither"]

VALID_RESULT = {
    "target_entity_context": "x",
    "load_bearing_assumption": "x",
    "check_walkthrough": "x",
    "classification": "Black Swan",
    "strategic_impact": "x",
}


# -- strip_code_fence -----------------------------------------------------

def test_strip_code_fence_removes_fences():
    text = '```json\n{"a": 1}\n```'
    assert strip_code_fence(text) == '{"a": 1}'


def test_strip_code_fence_leaves_unfenced_text_alone():
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'


# -- parse_json_object ------------------------------------------------------

def test_parse_json_object_strict():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_handles_code_fence():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_object_finds_embedded_object():
    text = 'Sure, here is the JSON:\n{"a": 1}\nHope that helps!'
    assert parse_json_object(text) == {"a": 1}


def test_parse_json_object_raises_when_no_object_found():
    with pytest.raises(ValueError):
        parse_json_object("no json here at all")


def test_parse_json_object_raises_on_non_object_json():
    with pytest.raises(ValueError):
        parse_json_object("[1, 2, 3]")


# -- normalize_classification -------------------------------------------------

def test_normalize_classification_matches_case_insensitively():
    assert normalize_classification("black swan", LABELS) == "Black Swan"


def test_normalize_classification_passes_through_unknown_value():
    assert normalize_classification("Something Else", LABELS) == "Something Else"


def test_normalize_classification_passes_through_none():
    assert normalize_classification(None, LABELS) is None


# -- normalize_model_result -----------------------------------------------------

def test_normalize_model_result_normalizes_classification_only():
    result = {**VALID_RESULT, "classification": "black swan"}
    normalized = normalize_model_result(result, LABELS)
    assert normalized["classification"] == "Black Swan"


# -- validate_model_result -------------------------------------------------------

def test_validate_model_result_accepts_valid_result():
    assert validate_model_result(VALID_RESULT, LABELS) == []


def test_validate_model_result_flags_missing_field():
    result = dict(VALID_RESULT)
    del result["strategic_impact"]
    errors = validate_model_result(result, LABELS)
    assert any("strategic_impact" in e for e in errors)


def test_validate_model_result_flags_empty_field():
    result = {**VALID_RESULT, "load_bearing_assumption": "   "}
    errors = validate_model_result(result, LABELS)
    assert any("load_bearing_assumption" in e for e in errors)


def test_validate_model_result_flags_invalid_classification():
    result = {**VALID_RESULT, "classification": "Not A Real Label"}
    errors = validate_model_result(result, LABELS)
    assert any("Invalid classification" in e for e in errors)
