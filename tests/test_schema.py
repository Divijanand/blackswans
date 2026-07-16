from parallel_classifier import (
    REQUIRED_MODEL_FIELDS,
    build_messages,
    json_forcing_instruction,
    make_response_model,
)


LABELS = ["Black Swan", "Gray Rhino", "Gray Swan", "White Swan", "Broken Prior", "Neither"]


def test_make_response_model_name():
    Model = make_response_model(LABELS)
    assert Model.__name__ == "BlackSwanClassification"


def test_make_response_model_has_exactly_the_five_required_fields():
    Model = make_response_model(LABELS)
    assert set(Model.model_fields.keys()) == set(REQUIRED_MODEL_FIELDS)
    assert len(REQUIRED_MODEL_FIELDS) == 5


def test_make_response_model_all_fields_required():
    schema = make_response_model(LABELS).model_json_schema()
    assert set(schema["required"]) == set(REQUIRED_MODEL_FIELDS)


def test_make_response_model_classification_enum_matches_labels():
    schema = make_response_model(LABELS).model_json_schema()
    assert schema["properties"]["classification"]["enum"] == LABELS


def test_make_response_model_rejects_invalid_classification():
    Model = make_response_model(LABELS)
    valid_kwargs = {
        "target_entity_context": "x",
        "load_bearing_assumption": "x",
        "check_walkthrough": "x",
        "classification": "Not A Real Label",
        "strategic_impact": "x",
    }
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Model(**valid_kwargs)


def test_make_response_model_accepts_valid_payload():
    Model = make_response_model(LABELS)
    instance = Model(
        target_entity_context="x",
        load_bearing_assumption="x",
        check_walkthrough="x",
        classification="Black Swan",
        strategic_impact="x",
    )
    assert instance.classification == "Black Swan"


# -- build_messages -----------------------------------------------------------

def _event():
    return {
        "_event_id": "1",
        "_event_text": "Something happened.",
        "_target_entity": "Apple",
        "title": "Something happened",
    }


def test_build_messages_has_system_and_user_roles():
    messages = build_messages("Classify this event.", _event())
    assert [m["role"] for m in messages] == ["system", "user"]


def test_build_messages_system_content_is_just_the_prompt():
    ## response_format guarantees the shape now, so the prompt shouldn't be
    ## carrying raw-JSON-forcing instructions for the default json_schema mode.
    messages = build_messages("Classify this event.", _event())
    assert messages[0]["content"] == "Classify this event."
    assert "Required JSON fields" not in messages[0]["content"]


def test_build_messages_user_content_includes_target_entity_and_event_text():
    messages = build_messages("Classify this event.", _event())
    user_content = messages[1]["content"]
    assert "TARGET_ENTITY:\nApple" in user_content
    assert "Something happened." in user_content
    assert "EVENT_ID:\n1" in user_content


def test_build_messages_strips_underscore_fields_from_full_event_json():
    messages = build_messages("Classify this event.", _event())
    user_content = messages[1]["content"]
    assert "_event_id" not in user_content
    assert "_target_entity" not in user_content


# -- json_forcing_instruction (fallback-mode only) -----------------------------

def test_json_forcing_instruction_lists_all_required_fields():
    instruction = json_forcing_instruction(LABELS)
    for field in REQUIRED_MODEL_FIELDS:
        assert field in instruction


def test_json_forcing_instruction_includes_labels():
    instruction = json_forcing_instruction(LABELS)
    for label in LABELS:
        assert label in instruction
