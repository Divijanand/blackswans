## Batch-classifies news events through OpenRouter using a classifier prompt.
##
## Core guarantees:
## 1. Concurrent model calls with ThreadPoolExecutor.
## 2. Checkpointing via JSONL append-as-completed.
## 3. Structured JSON outputs (via the OpenAI client's Pydantic-backed
##    structured outputs) with parse fallback.
## 4. Resume support: already-processed event_ids are skipped.
## 5. Failed rows are saved instead of crashing the whole run.
##
## Example:
##
##     export OPENROUTER_API_KEY="sk-or-..."
##
##     python scripts/parallel_classifier.py \
##       --input data/events.jsonl \
##       --output runs/results.jsonl \
##       --prompt prompts/classifier.md \
##       --model "<openrouter-model-id>" \
##       --workers 10
##
## Input formats supported:
## - .jsonl: one JSON object per line
## - .json: either a list of objects, or {"events": [...]}
## - .csv: header row becomes event fields

from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Type

from openai import APIStatusError, OpenAI
from pydantic import BaseModel, Field, create_model


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

REQUIRED_MODEL_FIELDS = [
    "classification",
    "check1_verdict",
    "check2_verdict",
    "check3_verdict",
    "load_bearing_assumption",
    "reasoning",
]

DEFAULT_LABELS = [
    "Black Swan",
    "Gray Rhino",
    "Gray Swan",
    "Broken Prior",
    "Not Relevant",
]

COMMON_TEXT_FIELDS = [
    "description",
    "summary",
    "title",
    "content",
    "body",
    "text",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_event_id(event: Dict[str, Any]) -> str:
    ## Creates a stable fallback ID if the input event has no explicit event_id/id.
    canonical = json.dumps(event, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def parse_labels(labels_arg: str) -> List[str]:
    labels = [x.strip() for x in labels_arg.split(",") if x.strip()]
    if not labels:
        raise ValueError("At least one classification label is required.")
    return labels


def load_prompt(prompt_path: Path) -> str:
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. "
            "Pass the real classifier prompt path with --prompt."
        )

    prompt = prompt_path.read_text(encoding="utf-8").strip()

    if not prompt:
        raise ValueError(f"Prompt file is empty: {prompt_path}")

    return prompt


def load_events(input_path: Path) -> List[Dict[str, Any]]:
    ## Loads events from JSONL, JSON, or CSV.
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()

    if suffix == ".jsonl":
        events: List[Dict[str, Any]] = []

        with input_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON on line {line_no} of {input_path}: {exc}"
                    ) from exc

                if not isinstance(obj, dict):
                    raise ValueError(
                        f"Line {line_no} of {input_path} is not a JSON object."
                    )

                events.append(obj)

        return events

    if suffix == ".json":
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            events = data
        elif isinstance(data, dict) and isinstance(data.get("events"), list):
            events = data["events"]
        else:
            raise ValueError(
                "JSON input must be either a list of event objects or "
                'an object shaped like {"events": [...]}'
            )

        if not all(isinstance(e, dict) for e in events):
            raise ValueError("Every event in the JSON input must be an object.")

        return events

    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    raise ValueError(
        f"Unsupported input format: {suffix}. Use .jsonl, .json, or .csv."
    )


def event_to_text(event: Dict[str, Any], text_field: Optional[str]) -> str:
    ## Turns an event object into the text shown to the model.
    if text_field:
        value = event.get(text_field)

        if value is not None and str(value).strip():
            return str(value).strip()

    pieces: List[str] = []

    for key in COMMON_TEXT_FIELDS:
        value = event.get(key)

        if value is not None and str(value).strip():
            pieces.append(f"{key}: {value}")

    if pieces:
        return "\n".join(pieces)

    return json.dumps(event, ensure_ascii=False, sort_keys=True)


def normalize_events(
    raw_events: List[Dict[str, Any]],
    id_field: str,
    text_field: Optional[str],
) -> List[Dict[str, Any]]:
    ## Ensures every event has internal _event_id and _event_text fields.
    ## These underscore fields are used by the script only.
    normalized: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for idx, raw_event in enumerate(raw_events):
        event = dict(raw_event)

        raw_id = (
            event.get(id_field)
            or event.get("event_id")
            or event.get("id")
            or stable_event_id(event)
        )

        event_id = str(raw_id).strip()

        if not event_id:
            event_id = stable_event_id(event)

        if event_id in seen_ids:
            raise ValueError(
                f"Duplicate event_id found: {event_id}. "
                "Checkpointing requires unique event IDs."
            )

        seen_ids.add(event_id)

        event_text = event_to_text(event, text_field).strip()

        if not event_text:
            raise ValueError(f"Event at index {idx} has no usable text.")

        event["_event_id"] = event_id
        event["_event_text"] = event_text

        normalized.append(event)

    return normalized


def load_existing_results(output_path: Path, retry_failed: bool) -> Set[str]:
    ## Reads the output JSONL and returns event_ids that should be skipped.
    ##
    ## If retry_failed is False:
    ##     Any prior row with event_id is considered checkpointed.
    ##
    ## If retry_failed is True:
    ##     Only prior rows with status == "ok" are considered done.
    ##     Failed/parse_error/request_error rows will be retried.
    done_ids: Set[str] = set()

    if not output_path.exists():
        return done_ids

    with output_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"Warning: ignoring invalid JSONL result line {line_no}",
                    file=sys.stderr,
                )
                continue

            event_id = row.get("event_id")

            if event_id is None:
                continue

            event_id = str(event_id)

            if retry_failed:
                if row.get("status") == "ok":
                    done_ids.add(event_id)
            else:
                done_ids.add(event_id)

    return done_ids


def make_response_model(labels: Sequence[str]) -> Type[BaseModel]:
    ## Pydantic model used for OpenAI/OpenRouter structured outputs.
    ## The classification field's allowed values are derived from --labels.
    classification_type = Literal[tuple(labels)]  # type: ignore[valid-type]
    verdict_type = Literal["YES", "NO"]

    return create_model(
        "EventClassification",
        classification=(
            classification_type,
            Field(description="Final event classification."),
        ),
        check1_verdict=(
            verdict_type,
            Field(description="Verdict for classifier check 1."),
        ),
        check2_verdict=(
            verdict_type,
            Field(description="Verdict for classifier check 2."),
        ),
        check3_verdict=(
            verdict_type,
            Field(description="Verdict for classifier check 3."),
        ),
        load_bearing_assumption=(
            str,
            Field(description="The assumption whose failure makes this event matter."),
        ),
        reasoning=(
            str,
            Field(description="Concise reasoning for the classification."),
        ),
    )


def build_messages(
    classifier_prompt: str,
    event: Dict[str, Any],
    labels: Sequence[str],
) -> List[Dict[str, str]]:
    ## Builds OpenRouter chat messages.
    clean_event = {
        key: value
        for key, value in event.items()
        if not key.startswith("_")
    }

    json_instruction = "\n".join(
        [
            "You must return ONLY a valid JSON object.",
            "",
            "Allowed classification labels:",
            json.dumps(list(labels), ensure_ascii=False),
            "",
            "Required JSON fields:",
            "- classification",
            "- check1_verdict",
            "- check2_verdict",
            "- check3_verdict",
            "- load_bearing_assumption",
            "- reasoning",
            "",
            'The three verdict fields must be exactly "YES" or "NO".',
            "Do not include markdown.",
            "Do not wrap the JSON in code fences.",
            "Do not add commentary outside the JSON.",
        ]
    )

    system_content = f"{classifier_prompt}\n\n{json_instruction}"

    user_content = "\n".join(
        [
            "Classify the following news event.",
            "",
            "EVENT_ID:",
            str(event["_event_id"]),
            "",
            "EVENT_TEXT:",
            str(event["_event_text"]),
            "",
            "FULL_EVENT_JSON:",
            json.dumps(clean_event, ensure_ascii=False, indent=2),
        ]
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def openrouter_headers() -> Dict[str, str]:
    ## Optional OpenRouter metadata headers, sent on every request via the
    ## client's default_headers. Safe to omit.
    headers: Dict[str, str] = {}

    referer = os.getenv("OPENROUTER_HTTP_REFERER")
    app_title = os.getenv("OPENROUTER_APP_TITLE", "Project Jupiter Classifier")

    if referer:
        headers["HTTP-Referer"] = referer

    if app_title:
        headers["X-Title"] = app_title

    return headers


def build_client(api_key: str, timeout: int, max_retries: int) -> OpenAI:
    ## OpenAI client pointed at OpenRouter's OpenAI-compatible endpoint.
    ## max_retries/timeout are handled by the client (429/5xx/connection
    ## errors are retried with backoff automatically).
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
        default_headers=openrouter_headers(),
    )


def call_openrouter(
    client: OpenAI,
    model_id: str,
    messages: List[Dict[str, str]],
    response_model: Type[BaseModel],
    structured_mode: str,
    fallback_structured_mode: bool,
    temperature: float,
) -> Tuple[str, Optional[Dict[str, Any]], str, Optional[BaseModel]]:
    ## Calls OpenRouter through the OpenAI client.
    ##
    ## Returns:
    ##     raw_content, usage, structured_mode_used, parsed_model
    ##     parsed_model is only set when structured_mode_used == "json_schema".
    modes_to_try = [structured_mode]

    if fallback_structured_mode:
        if structured_mode == "json_schema":
            modes_to_try.extend(["json_object", "none"])
        elif structured_mode == "json_object":
            modes_to_try.append("none")

    ## Remove duplicates while preserving order.
    deduped_modes = list(dict.fromkeys(modes_to_try))

    last_error: Optional[BaseException] = None

    for idx, mode in enumerate(deduped_modes):
        try:
            if mode == "json_schema":
                completion = client.chat.completions.parse(
                    model=model_id,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_model,
                )
                choice = completion.choices[0]

                if choice.finish_reason == "length":
                    raise ValueError("Response truncated (finish_reason=length).")

                if choice.message.refusal:
                    raise ValueError(f"Model refused to respond: {choice.message.refusal}")

                usage = completion.usage.model_dump() if completion.usage else None
                return choice.message.content or "", usage, mode, choice.message.parsed

            create_kwargs: Dict[str, Any] = {}

            if mode == "json_object":
                create_kwargs["response_format"] = {"type": "json_object"}

            completion = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                **create_kwargs,
            )
            choice = completion.choices[0]

            if choice.finish_reason == "length":
                raise ValueError("Response truncated (finish_reason=length).")

            usage = completion.usage.model_dump() if completion.usage else None
            return choice.message.content or "", usage, mode, None

        except APIStatusError as exc:
            last_error = exc

            ## Some models/providers may reject structured output modes.
            ## If so, fall back to weaker JSON forcing instead of killing the run.
            if exc.status_code in (400, 422) and idx < len(deduped_modes) - 1:
                continue

            raise RuntimeError(
                f"OpenRouter HTTP error {exc.status_code}: {str(exc)[:1000]}"
            ) from exc

    raise RuntimeError(f"OpenRouter call failed: {last_error}")


def strip_code_fence(text: str) -> str:
    ## Handles models that return fenced JSON despite being told not to.
    text = text.strip()

    if not text.startswith("```"):
        return text

    lines = text.splitlines()

    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]

    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines).strip()


def parse_json_object(raw_content: str) -> Dict[str, Any]:
    ## Parses a JSON object from the model response.
    ##
    ## First tries strict parsing.
    ## Then strips code fences.
    ## Then tries to decode the first JSON object embedded in the text.
    text = raw_content.strip()

    try:
        obj = json.loads(text)

        if not isinstance(obj, dict):
            raise ValueError("Model returned JSON, but not a JSON object.")

        return obj

    except json.JSONDecodeError:
        pass

    text = strip_code_fence(text)

    try:
        obj = json.loads(text)

        if not isinstance(obj, dict):
            raise ValueError("Model returned JSON, but not a JSON object.")

        return obj

    except json.JSONDecodeError:
        pass

    start = text.find("{")

    if start == -1:
        raise ValueError("No JSON object found in model response.")

    decoder = json.JSONDecoder()

    try:
        obj, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON object: {exc}") from exc

    if not isinstance(obj, dict):
        raise ValueError("Decoded JSON is not an object.")

    return obj


def normalize_classification(value: Any, labels: Sequence[str]) -> Any:
    if value is None:
        return value

    value_str = str(value).strip()

    for label in labels:
        if value_str.lower() == label.lower():
            return label

    return value_str


def normalize_verdict(value: Any) -> Any:
    if isinstance(value, bool):
        return "YES" if value else "NO"

    if value is None:
        return value

    value_str = str(value).strip().upper()

    if value_str in {"YES", "Y", "TRUE", "1"}:
        return "YES"

    if value_str in {"NO", "N", "FALSE", "0"}:
        return "NO"

    return value_str


def normalize_model_result(
    result: Dict[str, Any],
    labels: Sequence[str],
) -> Dict[str, Any]:
    result = dict(result)

    if "classification" in result:
        result["classification"] = normalize_classification(
            result["classification"],
            labels,
        )

    for key in ["check1_verdict", "check2_verdict", "check3_verdict"]:
        if key in result:
            result[key] = normalize_verdict(result[key])

    return result


def validate_model_result(
    result: Dict[str, Any],
    labels: Sequence[str],
) -> List[str]:
    errors: List[str] = []

    for field in REQUIRED_MODEL_FIELDS:
        if field not in result:
            errors.append(f"Missing required field: {field}")
        elif result[field] is None or str(result[field]).strip() == "":
            errors.append(f"Empty required field: {field}")

    classification = result.get("classification")

    if classification is not None and classification not in labels:
        errors.append(
            f"Invalid classification: {classification!r}. "
            f"Expected one of: {list(labels)}"
        )

    for key in ["check1_verdict", "check2_verdict", "check3_verdict"]:
        verdict = result.get(key)

        if verdict is not None and verdict not in {"YES", "NO"}:
            errors.append(
                f"Invalid {key}: {verdict!r}. Expected 'YES' or 'NO'."
            )

    return errors


def event_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    ## Keeps useful trace fields in the output without blindly copying huge input blobs.
    keep_keys = [
        "title",
        "date",
        "source",
        "url",
        "domain",
        "category",
        "description",
        "summary",
    ]

    return {
        key: event[key]
        for key in keep_keys
        if key in event and event[key] is not None
    }


def classify_event(
    event: Dict[str, Any],
    client: OpenAI,
    model_id: str,
    classifier_prompt: str,
    labels: Sequence[str],
    response_model: Type[BaseModel],
    structured_mode: str,
    fallback_structured_mode: bool,
    temperature: float,
) -> Dict[str, Any]:
    event_id = event["_event_id"]
    started = time.time()

    base: Dict[str, Any] = {
        "event_id": event_id,
        "model": model_id,
        "classified_at": utc_now_iso(),
        "event": event_metadata(event),
    }

    messages = build_messages(
        classifier_prompt=classifier_prompt,
        event=event,
        labels=labels,
    )

    try:
        raw_content, usage, mode_used, parsed_obj = call_openrouter(
            client=client,
            model_id=model_id,
            messages=messages,
            response_model=response_model,
            structured_mode=structured_mode,
            fallback_structured_mode=fallback_structured_mode,
            temperature=temperature,
        )

        try:
            if parsed_obj is not None:
                ## response_format=response_model already validated required
                ## fields and enum values, so there's nothing left to check.
                parsed = parsed_obj.model_dump()
                schema_errors: List[str] = []
            else:
                parsed = parse_json_object(raw_content)
                parsed = normalize_model_result(parsed, labels)
                schema_errors = validate_model_result(parsed, labels)

            status = "ok" if not schema_errors else "invalid_schema"

            output: Dict[str, Any] = {
                **base,
                **parsed,
                "status": status,
                "structured_mode_used": mode_used,
                "latency_seconds": round(time.time() - started, 3),
            }

            if usage is not None:
                output["usage"] = usage

            if schema_errors:
                output["schema_errors"] = schema_errors
                output["raw_response"] = raw_content

            return output

        except Exception as parse_exc:
            return {
                **base,
                "status": "parse_error",
                "error": str(parse_exc),
                "raw_response": raw_content,
                "latency_seconds": round(time.time() - started, 3),
            }

    except Exception as request_exc:
        return {
            **base,
            "status": "request_error",
            "error": repr(request_exc),
            "latency_seconds": round(time.time() - started, 3),
        }


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def run_classifier(
    events: List[Dict[str, Any]],
    client: OpenAI,
    model_id: str,
    classifier_prompt: str,
    labels: Sequence[str],
    response_model: Type[BaseModel],
    output_path: Path,
    workers: int,
    structured_mode: str,
    fallback_structured_mode: bool,
    temperature: float,
    retry_failed: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    done_ids = load_existing_results(output_path, retry_failed=retry_failed)

    remaining_events = [
        event for event in events
        if event["_event_id"] not in done_ids
    ]

    print(
        f"Total events: {len(events)} | "
        f"Cached/skipped: {len(done_ids)} | "
        f"Remaining: {len(remaining_events)} | "
        f"Workers: {workers}"
    )

    if not remaining_events:
        print("Nothing to do.")
        return

    completed = 0
    ok_count = 0
    fail_count = 0

    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_event_id = {
            executor.submit(
                classify_event,
                event,
                client,
                model_id,
                classifier_prompt,
                labels,
                response_model,
                structured_mode,
                fallback_structured_mode,
                temperature,
            ): event["_event_id"]
            for event in remaining_events
        }

        for future in futures.as_completed(future_to_event_id):
            event_id = future_to_event_id[future]

            try:
                result = future.result()

            except Exception as exc:
                ## This should be rare because classify_event catches most errors.
                result = {
                    "event_id": event_id,
                    "model": model_id,
                    "classified_at": utc_now_iso(),
                    "status": "thread_crash",
                    "error": repr(exc),
                }

            append_jsonl(output_path, result)

            completed += 1

            if result.get("status") == "ok":
                ok_count += 1
            else:
                fail_count += 1

            print(
                f"[{completed}/{len(remaining_events)}] "
                f"{event_id} -> {result.get('status')} "
                f"| ok={ok_count} fail={fail_count}"
            )

    print(
        f"Done. Wrote results to {output_path}. "
        f"ok={ok_count}, failed_or_invalid={fail_count}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parallel OpenRouter classifier for Project Jupiter events."
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input events file: .jsonl, .json, or .csv",
    )

    parser.add_argument(
        "--output",
        default=Path("results.jsonl"),
        type=Path,
        help="Output JSONL file. Existing rows are used as checkpoint cache.",
    )

    parser.add_argument(
        "--prompt",
        required=True,
        type=Path,
        help="Path to the existing classifier prompt in the repo.",
    )

    parser.add_argument(
        "--model",
        required=True,
        help="OpenRouter model identifier.",
    )

    parser.add_argument(
        "--workers",
        default=10,
        type=int,
        help="Number of concurrent requests. Start with 5-10 before increasing.",
    )

    parser.add_argument(
        "--id-field",
        default="event_id",
        help="Field containing unique event ID. Falls back to event_id/id/hash.",
    )

    parser.add_argument(
        "--text-field",
        default=None,
        help="Optional field to use as main event text, e.g. description or summary.",
    )

    parser.add_argument(
        "--labels",
        default=",".join(DEFAULT_LABELS),
        help=(
            "Comma-separated classification labels. "
            "Must match the labels expected by your classifier prompt."
        ),
    )

    parser.add_argument(
        "--structured-mode",
        default="json_schema",
        choices=["json_schema", "json_object", "none"],
        help="How strongly to force structured output.",
    )

    parser.add_argument(
        "--no-structured-fallback",
        action="store_true",
        help=(
            "Disable fallback from json_schema -> json_object -> prompt-only "
            "when a model/provider rejects structured output."
        ),
    )

    parser.add_argument(
        "--temperature",
        default=0.0,
        type=float,
        help="Model temperature. Keep at 0 for classification consistency.",
    )

    parser.add_argument(
        "--timeout",
        default=90,
        type=int,
        help="Per-request timeout in seconds.",
    )

    parser.add_argument(
        "--max-retries",
        default=4,
        type=int,
        help="Client-side retries for 429/5xx/connection errors.",
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help=(
            "Retry previous rows whose status was not ok. "
            "By default, every existing event_id is skipped."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load inputs and print the first prompt without calling OpenRouter.",
    )

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be >= 1")

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key and not args.dry_run:
        print(
            "Missing OPENROUTER_API_KEY environment variable.\n"
            'Run: export OPENROUTER_API_KEY="sk-or-..."',
            file=sys.stderr,
        )
        return 2

    labels = parse_labels(args.labels)
    response_model = make_response_model(labels)

    classifier_prompt = load_prompt(args.prompt)

    raw_events = load_events(args.input)

    events = normalize_events(
        raw_events=raw_events,
        id_field=args.id_field,
        text_field=args.text_field,
    )

    print(f"Loaded {len(events)} events from {args.input}")
    print(f"Using labels: {labels}")

    if args.dry_run:
        first = events[0]

        messages = build_messages(
            classifier_prompt=classifier_prompt,
            event=first,
            labels=labels,
        )

        print("\n--- DRY RUN: first event messages ---\n")
        print(json.dumps(messages, ensure_ascii=False, indent=2))
        print("\nNo API calls made.")

        return 0

    client = build_client(
        api_key=api_key or "",
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    run_classifier(
        events=events,
        client=client,
        model_id=args.model,
        classifier_prompt=classifier_prompt,
        labels=labels,
        response_model=response_model,
        output_path=args.output,
        workers=args.workers,
        structured_mode=args.structured_mode,
        fallback_structured_mode=not args.no_structured_fallback,
        temperature=args.temperature,
        retry_failed=args.retry_failed,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
