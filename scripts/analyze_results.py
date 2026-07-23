## Aggregates and scores a completed parallel_classifier.py run.
##
## Reports status/classification/per-model breakdowns, latency stats, and
## total token usage (with an optional cost estimate). Optionally scores
## accuracy against a ground-truth file, per experiments/experiment-flags.md
## (Flag 9): keep known-answer events in a *separate* file from the ones fed
## to the classifier, so expected labels never leak into a model prompt.
##
## Example:
##
##     python scripts/analyze_results.py --results runs/results.jsonl
##
##     python scripts/analyze_results.py --results runs/results.jsonl \
##       --ground-truth data/input/seeded-validation-labels.jsonl \
##       --cost-per-million-input 0.05 --cost-per-million-output 0.08
##
## --ground-truth expects JSONL rows shaped like:
##     {"event_id": "...", "expected_classification": "..."}

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from parallel_classifier import manifest_path_for


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_no} of {path}: {exc}"
                ) from exc

    return rows


def dedupe_by_event_id(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ## --retry-failed appends a new row for a retried event rather than
    ## replacing the old failed one (parallel_classifier.py's checkpointing
    ## treats the file as an append log, see load_existing_results). Keep
    ## only the last row per event_id -- the most recent attempt -- so a
    ## stale failed row doesn't also get counted alongside its retry.
    deduped: Dict[Any, Dict[str, Any]] = {}

    for idx, row in enumerate(rows):
        key = row.get("event_id", ("_no_event_id", idx))
        deduped[key] = row

    return list(deduped.values())


def load_manifest(results_path: Path) -> Optional[Dict[str, Any]]:
    manifest_path = manifest_path_for(results_path)

    if not manifest_path.exists():
        return None

    return json.loads(manifest_path.read_text(encoding="utf-8"))


def status_counts(rows: Sequence[Dict[str, Any]]) -> Counter:
    return Counter(row.get("status", "unknown") for row in rows)


def classification_counts(rows: Sequence[Dict[str, Any]]) -> Counter:
    return Counter(
        row["classification"]
        for row in rows
        if row.get("status") == "ok" and row.get("classification")
    )


def per_model_breakdown(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    breakdown: Dict[str, Dict[str, int]] = {}

    for row in rows:
        model = row.get("model", "unknown")
        entry = breakdown.setdefault(model, {"total": 0, "ok": 0})
        entry["total"] += 1

        if row.get("status") == "ok":
            entry["ok"] += 1

    return breakdown


def latency_stats(rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    latencies = [
        row["latency_seconds"]
        for row in rows
        if isinstance(row.get("latency_seconds"), (int, float))
    ]

    if not latencies:
        return None

    return {
        "count": len(latencies),
        "avg": round(statistics.mean(latencies), 3),
        "median": round(statistics.median(latencies), 3),
        "min": round(min(latencies), 3),
        "max": round(max(latencies), 3),
    }


def usage_totals(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for row in rows:
        usage = row.get("usage")

        if not usage:
            continue

        for key in totals:
            value = usage.get(key)

            if isinstance(value, (int, float)):
                totals[key] += value

    return totals


def estimate_cost(
    totals: Dict[str, int],
    cost_per_million_input: Optional[float],
    cost_per_million_output: Optional[float],
) -> Optional[float]:
    if cost_per_million_input is None or cost_per_million_output is None:
        return None

    input_cost = totals.get("prompt_tokens", 0) / 1_000_000 * cost_per_million_input
    output_cost = totals.get("completion_tokens", 0) / 1_000_000 * cost_per_million_output

    return round(input_cost + output_cost, 6)


def load_ground_truth(path: Path) -> Dict[str, str]:
    truth: Dict[str, str] = {}

    for row in load_jsonl(path):
        event_id = row.get("event_id")
        expected = row.get("expected_classification")

        if event_id is None or expected is None:
            raise ValueError(
                "Ground-truth row missing event_id/expected_classification: "
                f"{row}"
            )

        truth[str(event_id)] = expected

    return truth


def score_against_ground_truth(
    rows: Sequence[Dict[str, Any]],
    ground_truth: Dict[str, str],
) -> Dict[str, Any]:
    matched = 0
    correct = 0
    mismatches: List[Dict[str, Any]] = []

    for row in rows:
        event_id = str(row.get("event_id"))

        if event_id not in ground_truth or row.get("status") != "ok":
            continue

        matched += 1
        expected = ground_truth[event_id]
        actual = row.get("classification")

        if actual == expected:
            correct += 1
        else:
            mismatches.append(
                {"event_id": event_id, "expected": expected, "actual": actual}
            )

    accuracy = round(correct / matched, 4) if matched else None

    return {
        "matched": matched,
        "correct": correct,
        "accuracy": accuracy,
        "mismatches": mismatches,
    }


def print_report(
    rows: Sequence[Dict[str, Any]],
    manifest: Optional[Dict[str, Any]],
    ground_truth: Optional[Dict[str, str]],
    cost_per_million_input: Optional[float],
    cost_per_million_output: Optional[float],
) -> None:
    if manifest:
        print("Run config (from manifest):")
        print(f"  model: {manifest.get('model')}")
        print(f"  prompt: {manifest.get('prompt')}")
        print(f"  labels: {manifest.get('labels')}")
        print(f"  target_entity default: {manifest.get('default_target_entity')}")
        print(f"  started_at: {manifest.get('started_at')}")
        print()

    print(f"Total rows: {len(rows)}")

    print("\nStatus breakdown:")
    for status, count in status_counts(rows).most_common():
        print(f"  {status}: {count}")

    print("\nClassification breakdown (status=ok):")
    for label, count in classification_counts(rows).most_common():
        print(f"  {label}: {count}")

    print("\nPer-model breakdown:")
    for model, stats in per_model_breakdown(rows).items():
        print(f"  {model}: {stats['ok']}/{stats['total']} ok")

    latency = latency_stats(rows)

    if latency:
        print(
            f"\nLatency (seconds): avg={latency['avg']} median={latency['median']} "
            f"min={latency['min']} max={latency['max']} (n={latency['count']})"
        )

    totals = usage_totals(rows)
    print(
        f"\nTokens: prompt={totals['prompt_tokens']} "
        f"completion={totals['completion_tokens']} total={totals['total_tokens']}"
    )

    cost = estimate_cost(totals, cost_per_million_input, cost_per_million_output)

    if cost is not None:
        print(f"Estimated cost: ${cost:.4f}")

    if ground_truth is not None:
        score = score_against_ground_truth(rows, ground_truth)
        accuracy_pct = (
            f" ({score['accuracy'] * 100:.1f}%)" if score["accuracy"] is not None else ""
        )
        print(f"\nGround-truth accuracy: {score['correct']}/{score['matched']}{accuracy_pct}")

        if score["mismatches"]:
            print("Mismatches:")

            for mismatch in score["mismatches"]:
                print(
                    f"  {mismatch['event_id']}: expected={mismatch['expected']!r} "
                    f"actual={mismatch['actual']!r}"
                )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate and score a parallel_classifier.py run."
    )

    parser.add_argument(
        "--results",
        required=True,
        type=Path,
        help="Path to a results JSONL file written by parallel_classifier.py.",
    )

    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help=(
            'Optional JSONL file of {"event_id": ..., "expected_classification": ...} '
            "rows to score accuracy against. Keep this separate from --input so "
            "expected labels never end up in the classifier prompt."
        ),
    )

    parser.add_argument(
        "--cost-per-million-input",
        type=float,
        default=None,
        help="USD per 1M prompt tokens.",
    )

    parser.add_argument(
        "--cost-per-million-output",
        type=float,
        default=None,
        help="USD per 1M completion tokens.",
    )

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    rows = load_jsonl(args.results)

    if not rows:
        print(f"No rows found in {args.results}")
        return 0

    deduped_rows = dedupe_by_event_id(rows)

    if len(deduped_rows) != len(rows):
        print(
            f"Note: {len(rows) - len(deduped_rows)} duplicate event_id row(s) "
            "found (likely from --retry-failed); keeping the latest attempt "
            "for each."
        )

    rows = deduped_rows

    manifest = load_manifest(args.results)
    ground_truth = load_ground_truth(args.ground_truth) if args.ground_truth else None

    print_report(
        rows,
        manifest,
        ground_truth,
        args.cost_per_million_input,
        args.cost_per_million_output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
