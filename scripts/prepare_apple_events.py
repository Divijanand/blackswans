#!/usr/bin/env python3
"""Converts Yevhen's mcp_company_market_events CSV export into the JSONL shape
parallel_classifier.py expects, stripping pipeline-internal fields (verdict,
trust_tier, certainty, etc.) out of the prompt path and into a separate
sidecar file so they never leak into FULL_EVENT_JSON.
"""

import argparse
import csv
import json
from pathlib import Path

# Fields Yevhen flagged as containing real news content; llm_synthesis
# preferred since description sometimes holds raw scrape boilerplate
# (e.g. a YouTube page's nav/footer text) instead of the actual event text.
MIN_TEXT_LEN = 20

SIDECAR_FIELDS = [
    "type",
    "verdict",
    "certainty",
    "trust_tier",
    "hitl_status",
    "impact_eval_status",
    "is_validated_url",
    "source_kind",
    "magnitude",
    "tool_used",
    "research_round",
    "collection_run",
]


def best_text(row: dict) -> str:
    synthesis = (row.get("llm_synthesis") or "").strip()

    if len(synthesis) >= MIN_TEXT_LEN:
        return synthesis

    return (row.get("description") or "").strip()


def convert(input_csv: Path, output_events: Path, output_metadata: Path) -> int:
    with input_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    with output_events.open("w", encoding="utf-8") as events_f, \
            output_metadata.open("w", encoding="utf-8") as meta_f:
        for row in rows:
            event_id = row["_id"]

            event = {
                "event_id": event_id,
                "title": row.get("eventTitle", "").strip(),
                "description": best_text(row),
                "date": row.get("occurance_time", "").strip(),
                "url": row.get("urlSources[0]", "").strip(),
            }
            events_f.write(json.dumps(event, ensure_ascii=False) + "\n")

            metadata = {"event_id": event_id}
            metadata.update({k: row.get(k, "") for k in SIDECAR_FIELDS})
            meta_f.write(json.dumps(metadata, ensure_ascii=False) + "\n")

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-events", required=True, type=Path)
    parser.add_argument("--output-metadata", required=True, type=Path)
    args = parser.parse_args()

    count = convert(args.input, args.output_events, args.output_metadata)
    print(f"Wrote {count} events to {args.output_events}")
    print(f"Wrote {count} metadata rows to {args.output_metadata}")


if __name__ == "__main__":
    main()
