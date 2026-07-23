## Exercises call_openrouter()'s structured-mode fallback chain against a
## fake OpenAI client, so nothing here makes a real network call.

import httpx
import pytest
from openai import APIStatusError
from pydantic import BaseModel

from parallel_classifier import call_openrouter, make_response_model


LABELS = ["Black Swan", "Gray Rhino", "Gray Swan", "White Swan", "Broken Prior", "Neither"]

MESSAGES = [
    {"role": "system", "content": "Classify this event."},
    {"role": "user", "content": "EVENT_ID:\n1"},
]


class FakeMessage:
    def __init__(self, content=None, refusal=None, parsed=None):
        self.content = content
        self.refusal = refusal
        self.parsed = parsed


class FakeChoice:
    def __init__(self, message, finish_reason="stop"):
        self.message = message
        self.finish_reason = finish_reason


class FakeUsage:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


class FakeCompletion:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


class FakeCompletions:
    ## parse_side_effects/create_side_effects are lists consumed one call at a
    ## time; each entry is either a return value or an exception instance.
    def __init__(self, parse_side_effects=None, create_side_effects=None):
        self._parse_side_effects = list(parse_side_effects or [])
        self._create_side_effects = list(create_side_effects or [])
        self.parse_calls = []
        self.create_calls = []

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        result = self._parse_side_effects.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        result = self._create_side_effects.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, completions):
        self.chat = FakeChat(completions)


def api_status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json={"error": "nope"})
    return APIStatusError(f"error {status_code}", response=response, body=None)


@pytest.fixture
def response_model():
    return make_response_model(LABELS)


def test_json_schema_mode_returns_parsed_object(response_model):
    parsed = response_model(
        target_entity_context="x",
        load_bearing_assumption="x",
        check_walkthrough="x",
        classification="Black Swan",
        strategic_impact="x",
    )
    completions = FakeCompletions(
        parse_side_effects=[
            FakeCompletion(
                choices=[FakeChoice(FakeMessage(content="{}", parsed=parsed))],
                usage=FakeUsage({"total_tokens": 42}),
            )
        ]
    )
    client = FakeClient(completions)

    raw_content, usage, mode_used, parsed_obj = call_openrouter(
        client=client,
        model_id="test-model",
        messages=MESSAGES,
        labels=LABELS,
        response_model=response_model,
        structured_mode="json_schema",
        fallback_structured_mode=True,
        temperature=0.0,
        max_tokens=1000,
    )

    assert mode_used == "json_schema"
    assert parsed_obj is parsed
    assert usage == {"total_tokens": 42}
    assert len(completions.parse_calls) == 1
    assert completions.parse_calls[0]["response_format"] is response_model


def test_json_schema_refusal_raises_without_trying_fallback(response_model):
    completions = FakeCompletions(
        parse_side_effects=[
            FakeCompletion(choices=[FakeChoice(FakeMessage(refusal="I can't help with that"))])
        ]
    )
    client = FakeClient(completions)

    with pytest.raises(ValueError, match="refused"):
        call_openrouter(
            client=client,
            model_id="test-model",
            messages=MESSAGES,
            labels=LABELS,
            response_model=response_model,
            structured_mode="json_schema",
            fallback_structured_mode=True,
            temperature=0.0,
            max_tokens=1000,
        )

    ## A refusal isn't a schema-support problem, so it shouldn't fall back.
    assert len(completions.create_calls) == 0


def test_json_schema_truncation_raises(response_model):
    completions = FakeCompletions(
        parse_side_effects=[
            FakeCompletion(choices=[FakeChoice(FakeMessage(content="{"), finish_reason="length")])
        ]
    )
    client = FakeClient(completions)

    with pytest.raises(ValueError, match="truncated"):
        call_openrouter(
            client=client,
            model_id="test-model",
            messages=MESSAGES,
            labels=LABELS,
            response_model=response_model,
            structured_mode="json_schema",
            fallback_structured_mode=True,
            temperature=0.0,
            max_tokens=1000,
        )


def test_falls_back_to_json_object_on_400(response_model):
    completions = FakeCompletions(
        parse_side_effects=[api_status_error(400)],
        create_side_effects=[
            FakeCompletion(choices=[FakeChoice(FakeMessage(content='{"classification": "Black Swan"}'))])
        ],
    )
    client = FakeClient(completions)

    raw_content, usage, mode_used, parsed_obj = call_openrouter(
        client=client,
        model_id="test-model",
        messages=MESSAGES,
        labels=LABELS,
        response_model=response_model,
        structured_mode="json_schema",
        fallback_structured_mode=True,
        temperature=0.0,
        max_tokens=1000,
    )

    assert mode_used == "json_object"
    assert parsed_obj is None
    assert raw_content == '{"classification": "Black Swan"}'
    assert completions.create_calls[0]["response_format"] == {"type": "json_object"}


def test_fallback_messages_include_json_forcing_instruction(response_model):
    completions = FakeCompletions(
        parse_side_effects=[api_status_error(400)],
        create_side_effects=[
            FakeCompletion(choices=[FakeChoice(FakeMessage(content="{}"))])
        ],
    )
    client = FakeClient(completions)

    call_openrouter(
        client=client,
        model_id="test-model",
        messages=MESSAGES,
        labels=LABELS,
        response_model=response_model,
        structured_mode="json_schema",
        fallback_structured_mode=True,
        temperature=0.0,
        max_tokens=1000,
    )

    sent_system_content = completions.create_calls[0]["messages"][0]["content"]
    assert "Required JSON fields" in sent_system_content
    ## Original messages list passed in by the caller must stay untouched.
    assert "Required JSON fields" not in MESSAGES[0]["content"]


def test_no_fallback_raises_immediately_on_400(response_model):
    completions = FakeCompletions(parse_side_effects=[api_status_error(400)])
    client = FakeClient(completions)

    with pytest.raises(RuntimeError, match="400"):
        call_openrouter(
            client=client,
            model_id="test-model",
            messages=MESSAGES,
            labels=LABELS,
            response_model=response_model,
            structured_mode="json_schema",
            fallback_structured_mode=False,
            temperature=0.0,
            max_tokens=1000,
        )

    assert len(completions.create_calls) == 0


def test_exhausts_all_fallback_modes_and_raises(response_model):
    completions = FakeCompletions(
        parse_side_effects=[api_status_error(400)],
        create_side_effects=[api_status_error(400), api_status_error(400)],
    )
    client = FakeClient(completions)

    with pytest.raises(RuntimeError, match="400"):
        call_openrouter(
            client=client,
            model_id="test-model",
            messages=MESSAGES,
            labels=LABELS,
            response_model=response_model,
            structured_mode="json_schema",
            fallback_structured_mode=True,
            temperature=0.0,
            max_tokens=1000,
        )

    assert len(completions.create_calls) == 2


def test_non_retryable_status_code_raises_without_fallback(response_model):
    ## 401 (auth) shouldn't be treated as "model rejects structured output".
    completions = FakeCompletions(parse_side_effects=[api_status_error(401)])
    client = FakeClient(completions)

    with pytest.raises(RuntimeError, match="401"):
        call_openrouter(
            client=client,
            model_id="test-model",
            messages=MESSAGES,
            labels=LABELS,
            response_model=response_model,
            structured_mode="json_schema",
            fallback_structured_mode=True,
            temperature=0.0,
            max_tokens=1000,
        )

    assert len(completions.create_calls) == 0
