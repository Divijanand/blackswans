# Black Swans — Project Jupiter

Domain-agnostic framework for classifying market/industry events as **Black Swan**,
**Gray Rhino**, **Gray Swan**, **White Swan**, **Broken Prior**, or **Neither**, plus a
script that runs that classification at scale across LLMs via
[OpenRouter](https://openrouter.ai), evaluated relative to a specific **Target Entity**
(see [`Company-Level Classifier.md`](prompts/Company-Level%20Classifier.md)).

## Repo structure

```
prompts/      Classifier prompt templates (the reusable framework + case banks)
scripts/      parallel_classifier.py — batch-runs events; analyze_results.py — scores a run
tests/        pytest suite for scripts/*.py (no network calls)
data/         Input event sets (data/input) and processed output (data/processed)
runs/         Classifier output JSONL lands here (gitignored, .gitkeep only)
experiments/  Model tier list and engineering flags/risks for the scale run
research/     Background research and worked examples behind the classifier design
```

- **prompts/** — start with [`Prompt Template.md`](prompts/Prompt%20Template.md) for the
  copy-pasteable framework, [`Shock Classifier.md`](prompts/Shock%20Classifier.md) for the
  full write-up with benchmark cases and edge cases, and
  [`Company-Level Classifier.md`](prompts/Company-Level%20Classifier.md) for the
  entity-relative variant of the same framework.
- **experiments/** — [`model-list.md`](experiments/model-list.md) is the tiered list of
  models to run (small/open-source, mid-tier, frontier) with training cutoffs and
  OpenRouter model strings. [`experiment-flags.md`](experiments/experiment-flags.md) is
  the running list of known risks (cutoff-date uncertainty, JSON output reliability,
  live-search contamination, rate limits, domain grounding) — read it before a scale run.
- **research/** — event write-ups behind the `ai-market-blackswans` and
  `apple-ecosystem-blackswans` case sets, plus the `synthesis/` notes that motivated the
  classifier's design.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in OPENROUTER_API_KEY
```

`parallel_classifier.py` loads `.env` automatically (via `python-dotenv`), so filling in
`OPENROUTER_API_KEY` there is enough — no need to `export` it yourself unless you prefer to.

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The suite (`tests/`) covers every pure function in `scripts/parallel_classifier.py` —
event loading/normalization, target-entity resolution, the response schema, JSON
parsing/validation, checkpointing — plus `call_openrouter`'s `json_schema` →
`json_object` → `none` fallback chain against a fake OpenAI client, so none of it makes a
real network call or costs API credits. It does **not** test that a real model actually
returns a sane classification — for that, run a small `--workers 1` batch against
`data/input/test_events.jsonl` (which has 5 real seed events) and inspect the output:

```bash
python scripts/parallel_classifier.py \
  --input data/input/test_events.jsonl \
  --output runs/smoke_test.jsonl \
  --prompt "prompts/Company-Level Classifier.md" \
  --model "meta-llama/llama-3.1-8b-instruct" \
  --workers 1
```

`data/input/yehven_events.jsonl` is seeded with 5 more events from `research/` as a
placeholder (ChatGPT launch, EU AI Act, Meta publisher suit, Apple Intelligence pivot, GT
Advanced Technologies bankruptcy) — swap in Yevhen's own event set when he provides one.

## Running the classifier

`scripts/parallel_classifier.py` reads an event set, sends each event through an
OpenRouter model with a classifier prompt, and writes results to JSONL with
checkpoint/resume support (already-processed `event_id`s are skipped on rerun). It calls
OpenRouter via the [OpenAI Python client](https://github.com/openai/openai-python) pointed
at OpenRouter's OpenAI-compatible endpoint (`base_url="https://openrouter.ai/api/v1"`),
using the client's built-in [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
support to enforce the response shape.

```bash
python scripts/parallel_classifier.py \
  --input data/input/test_events.jsonl \
  --output runs/results.jsonl \
  --prompt "prompts/Company-Level Classifier.md" \
  --model "meta-llama/llama-3.3-70b-instruct" \
  --workers 10
```

(`data/input/test_events.jsonl` already sets `target_entity` per event; use
`--target-entity "Apple"` instead if your input doesn't set its own.)

Key flags (see `--help` for the full list):

- `--input` — `.jsonl`, `.json` (list or `{"events": [...]}`), or `.csv`
- `--target-entity` — default Target Entity for every event (the Company-Level Classifier
  evaluates a shock relative to a specific company/actor); an event can override this with
  its own `target_entity` field (configurable via `--target-entity-field`)
- `--labels` — comma-separated classification labels (defaults to the six taxonomic
  categories above)
- `--structured-mode` — `json_schema` (default, strict structured output via a Pydantic
  model), `json_object`, or `none`; falls back automatically if a model/provider rejects
  the stricter mode
- `--model-tier {tier1,tier2,tier3}` — sets the `--workers` default per
  [`experiments/model-list.md`](experiments/model-list.md)'s tiers (5 / 15 / 20, per
  `experiments/experiment-flags.md` Flag 7); ignored if you pass `--workers` explicitly
- `--domain-context` / `--domain-context-field` — optional domain-mechanics grounding
  (`experiments/experiment-flags.md` Flag 6, Option A), inserted into the prompt as a
  `DOMAIN_CONTEXT:` block when set per-event or as a run-wide default; omitted from the
  prompt entirely if neither is set
- `--cost-per-million-input` / `--cost-per-million-output` — USD rates for the end-of-run
  cost estimate (check the model's OpenRouter pricing page; omit to skip the estimate)
- `--dry-run` — builds and prints the first event's prompt without calling the API

The schema each model is asked to conform to is a Pydantic model
(`BlackSwanClassification`) built in
[`make_response_model`](scripts/parallel_classifier.py), with one field per header in the
Company-Level Classifier's `Output Format` section: `target_entity_context`,
`load_bearing_assumption`, `check_walkthrough`, `classification`, `strategic_impact`. The
`classification` field's allowed values come straight from `--labels`, so there's no
separate schema file to keep in sync. Because `response_format` guarantees this shape,
the prompt sent to the model doesn't need "return raw JSON" instructions in `json_schema`
mode — those are only added back in for the `json_object`/`none` fallback modes, which
aren't schema-guaranteed.

Output rows include `status` (`ok`, `invalid_schema`, `parse_error`, `request_error`,
`thread_crash`), latency, token usage, and — on failure — the raw model response for
manual review. Run output is gitignored; only `runs/.gitkeep` is tracked.

Every real run (not `--dry-run`) also writes a manifest sidecar —
`<output>.manifest.json` — recording the config that produced it (`model`, `prompt`,
`labels`, `target_entity` default, `workers`, etc.), since output rows themselves only
carry the model id. At the end of the run, the script also prints a token summary and
(if `--cost-per-million-*` was given) a cost estimate.

Before a full scale run, read [`experiments/experiment-flags.md`](experiments/experiment-flags.md)
in full — it covers event-sourcing requirements (post-cutoff, no retrospective framing),
disabling live search on Command R+/Grok, and per-tier worker limits.

## Analyzing a run

`scripts/analyze_results.py` reads a results file (and its manifest, if present) and
prints a summary: status/classification/per-model breakdowns, latency stats, token totals
and cost estimate.

```bash
python scripts/analyze_results.py --results runs/results.jsonl
```

To score accuracy against known-answer events, pass `--ground-truth` pointing at a
**separate** JSONL file of `{"event_id": ..., "expected_classification": ...}` rows —
kept out of the file you actually feed to `--input`, per
[`experiments/experiment-flags.md`](experiments/experiment-flags.md) Flag 9 (seeded
validation events must stay separate from the blind test set, and expected labels must
never end up inside a prompt sent to the model):

```bash
python scripts/analyze_results.py \
  --results runs/results.jsonl \
  --ground-truth data/input/seeded-validation-labels.jsonl \
  --cost-per-million-input 0.05 --cost-per-million-output 0.08
```

`data/input/seeded-validation-set.jsonl` / `seeded-validation-labels.jsonl` are a first
draft of that seeded set (7 events, including both perspectives of the NASDAQ/SpaceX
benchmark case study already worked out in `Company-Level Classifier.md`). **The expected
labels are Claude's draft reasoning through the framework, not yet confirmed by
Yevhen** — each row in the labels file carries a `confidence` and `source` field; one
(DeepSeek R1 vs. NVIDIA) is deliberately left "medium confidence, debatable" as a
discussion point. Treat this as a starting point for the meeting, not ground truth.

## CI

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs `pytest` on every push
and PR to `main`. It only runs the offline suite (no `OPENROUTER_API_KEY` needed/used).
