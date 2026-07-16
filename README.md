# Black Swans — Project Jupiter

Domain-agnostic framework for classifying market/industry events as **Black Swan**,
**Gray Rhino**, **Gray Swan**, **Broken Prior**, or **Neither**, plus a script that
runs that classification at scale across LLMs via [OpenRouter](https://openrouter.ai).

## Repo structure

```
prompts/      Classifier prompt templates (the reusable framework + case banks)
scripts/      parallel_classifier.py — batch-runs events through an OpenRouter model
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
export OPENROUTER_API_KEY="sk-or-..."   # or set it in .env and source it
```

## Running the classifier

`scripts/parallel_classifier.py` reads an event set, sends each event through an
OpenRouter model with a classifier prompt, and writes results to JSONL with
checkpoint/resume support (already-processed `event_id`s are skipped on rerun).

```bash
python scripts/parallel_classifier.py \
  --input data/input/test_events.jsonl \
  --output runs/results.jsonl \
  --prompt "prompts/Shock Classifier.md" \
  --model "meta-llama/llama-3.3-70b-instruct" \
  --workers 10
```

Key flags (see `--help` for the full list):

- `--input` — `.jsonl`, `.json` (list or `{"events": [...]}`), or `.csv`
- `--labels` — comma-separated classification labels (defaults to the five taxonomic
  categories above)
- `--structured-mode` — `json_schema` (default, strict OpenRouter structured output),
  `json_object`, or `none`; falls back automatically if a model rejects the stricter mode
- `--dry-run` — builds and prints the first event's prompt without calling the API

The JSON schema each model is asked to conform to (`classification`, three check
verdicts, load-bearing assumption, reasoning) is defined in code in
[`make_response_schema`](scripts/parallel_classifier.py) inside the script — there's no
separate schema file to keep in sync.

Output rows include `status` (`ok`, `invalid_schema`, `parse_error`, `request_error`,
`thread_crash`), latency, token usage, and — on failure — the raw model response for
manual review. Run output is gitignored; only `runs/.gitkeep` is tracked.

Before a full scale run, read [`experiments/experiment-flags.md`](experiments/experiment-flags.md)
in full — it covers event-sourcing requirements (post-cutoff, no retrospective framing),
disabling live search on Command R+/Grok, and per-tier worker limits.
