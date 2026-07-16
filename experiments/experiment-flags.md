# Experiment Flags and Engineering Pointers

Known risks, design decisions, and things to watch for before and during the classifier scale run.
Update this doc as issues surface during development.

---

## Flag 1: Cutoff Dates Are Often Unofficial and Disputed

Most open-source model providers do not publish exact training cutoff dates in their official documentation. The dates in `model-list.md` are sourced from model cards, community repositories, and cross-referenced secondary sources, but several are estimated rather than confirmed.

Models with contested or unconfirmed cutoffs:
- Qwen2.5 series: community sources disagree between October 2023 and June 2024
- Gemma 2 9B and 27B: Google has not officially published a cutoff; June 2024 is estimated from release timing
- DeepSeek V3 and R1: DeepSeek does not officially publish cutoffs; July 2024 is estimated from release date
- Command R+: Cohere does not publish cutoffs; approach with caution
- Llama 4 family: cutoff listed as August 2024 in community sources but not confirmed by Meta

**What this means for the experiment:** Do not use events from the 3-month window immediately after any model's estimated cutoff. Use events that are clearly 4 to 6 months post-cutoff to avoid the "thin data zone" where the model may have partial knowledge. The safest approach is to use events from 2025 onward for all Tier 1 and Tier 2 models, which clears even the most generous cutoff estimates.

---

## Flag 2: Small Models Will Struggle with Structured JSON Output

The classifier prompt requires the model to return a structured JSON object with specific fields. Models below roughly 20B parameters frequently fail at this, especially on multi-step reasoning tasks like the three-check procedure.

Expected failure modes:
- Model returns free text instead of JSON
- Model returns JSON with missing or renamed fields
- Model returns valid JSON for Check 1 but hallucinated reasoning for Checks 2 and 3
- Model truncates the output mid-JSON if max tokens is set too low

**Mitigation options:**

Option A: Add a strict JSON-only instruction at the top and bottom of the system prompt.
```
You must respond ONLY with a valid JSON object. Do not include any text before or after the JSON. Do not include markdown code fences. If you cannot classify the event, return {"classification": "UNCLASSIFIABLE", "reason": "<brief explanation>"}.
```

Option B: Use OpenRouter's structured outputs feature where supported (currently works with most frontier and some mid-tier models; not guaranteed for Tier 1 open-source).

Option C: Add a fallback JSON parser in the script that handles common malformed outputs (missing closing brace, extra text before the opening brace, etc.) and logs raw output for manual review if the parse still fails.

**Recommended approach:** Implement Option A plus Option C. Do not depend on Option B alone since not all Tier 1 models support it via OpenRouter.

---

## Flag 3: Command R+ Has Live Retrieval Enabled by Default

Cohere's Command R+ is a retrieval-augmented model. By default it searches the web when responding. This completely invalidates the retrospective-bias fix (the whole point of using post-cutoff events is to test the model on information it does not have; a model that can just search the web for the answer defeats this entirely).

**Fix:** Either exclude Command R+ from the experiment entirely, or disable retrieval by setting `connectors: []` in the API call and confirming via the response metadata that no web search was triggered.

If you include Command R+, label its results separately in the output file and note the retrieval-disabled flag in the methodology section of any paper draft.

---

## Flag 4: Grok 4.3 Has Live X/Twitter Search by Default

Same issue as Flag 3 but for Grok. xAI's Grok models default to real-time X/Twitter search, which means the model has access to current information beyond its training cutoff. If you want to test Grok on its base knowledge only, you need to explicitly disable search in the API call.

In the xAI API, pass `search_enabled: false` in the request body to disable live search. Verify this is actually disabling it by checking whether the response includes search citations.

---

## Flag 5: The Retrospective-Bias Fix Requires Careful Event Sourcing

The core methodological claim of the experiment is that feeding live or post-cutoff news removes retrospective bias. This only holds if:

1. The events are genuinely post-cutoff for the model being tested
2. The events are not already described in the model's training data under a different framing (e.g., a post-cutoff news article about an event that was already covered in pre-cutoff training data)
3. The model does not have web search access (see Flags 3 and 4)

**What Yevhen's dataset needs to include per event:**
- Event title and brief neutral description (no editorializing that hints at the classification)
- Date of the event
- Domain (which industry or market this falls under)
- Source URL (for manual review of flagged cases)

**What to strip out before feeding to the model:**
- Any language that implies how big the shock was ("the market-shattering," "the historic," etc.)
- Any reference to how the event was received retrospectively
- Any classification labels if the dataset includes pre-labeled examples used for seeding

---

## Flag 6: Domain Grounding Is the Unsolved Core Problem

Yevhen flagged this explicitly on the call. A lawsuit is "regular" in a general business context but can be a black swan inside Apple's isolated walled-garden ecosystem. The classifier prompt currently does not inject domain context into the decision procedure.

This means two events with identical surface descriptions can score differently if you know the domain mechanics, but the model will score them identically if no domain context is provided.

**Options:**

Option A: Prepend a domain context block to each event before passing it to the classifier. Example:
```
Domain context: This event occurred in the iOS developer ecosystem, where Apple has historically enforced a strict 30% commission on all in-app purchases and prohibited alternative payment systems. Third-party app distribution outside the App Store has been technically and legally restricted since 2008.
Event: [event description]
```

Option B: Add a "Domain Mechanics" field to the classifier prompt asking the model to first describe the relevant domain before classifying. This forces the model to surface its domain knowledge before scoring.

Option C: Accept domain-agnostic scoring as a known limitation and seed the labeled dataset with enough domain-specific examples that Yevhen can manually verify edge cases during the 0.1% review step.

**Recommended approach for this phase:** Option C is the pragmatic choice for getting first results quickly. Options A and B become important for the paper methodology section and should be implemented for the validation run.

**Status:** Option A is implemented. `scripts/parallel_classifier.py` accepts an optional per-event `domain_context` field (configurable via `--domain-context-field`, or a single default via `--domain-context`), inserted into the prompt as a `DOMAIN_CONTEXT:` block right after `TARGET_ENTITY:` when set. It's opt-in — events without it are unaffected. `data/input/test_events.jsonl` and `data/input/seeded-validation-set.jsonl` both set it per event as a reference example. Option B (asking the model to surface domain mechanics itself before classifying) is not implemented; still worth doing for the validation-run methodology section per the original recommendation above.

---

## Flag 7: Rate Limits Will Bite During Parallelized Runs

OpenRouter enforces per-model rate limits that vary by provider and tier. Running 20 concurrent threads against a single model will hit rate limits fast, especially for Tier 1 free models which have the strictest daily request caps.

**Mitigation:**
- Set `max_workers` per model based on its tier (suggest 5 for Tier 1 free models, 15 for paid Tier 1 and 2, 20 for Tier 3 frontier)
- Add exponential backoff with jitter on 429 responses
- Log rate limit hits separately so you can see which models are the bottleneck
- For free models specifically, check the current daily request limit on [OpenRouter's free models page](https://openrouter.ai/collections/free-models) before batching; limits change without notice

---

## Flag 8: Max Tokens Must Be Set High Enough for the Full JSON Response

The classifier requires a structured JSON output covering Load-Bearing Assumption, three check walkthroughs, Final Classification, and Strategic Trajectory Impact. A complete response is typically 400 to 800 tokens.

If you set `max_tokens` too low, the model will truncate mid-response, producing malformed JSON that fails to parse. Set a minimum of 1000 tokens for all classifier runs. For reasoning models like DeepSeek R1 which produce chain-of-thought before the JSON, set 2000 or higher.

---

## Flag 9: Seeded Positive Examples Must Be Kept Separate from the Blind Test Set

The experiment plan includes seeding the labeled dataset with known black swan and gray rhino examples (DeepSeek R1, Epic v. Apple, etc.) to validate that the classifier produces correct verdicts on known cases.

These seeded examples must not be mixed into the blind test set that measures how well the classifier handles novel events. Keep two separate files:
- `seeded-validation-set.jsonl` - known examples with ground-truth labels; used to verify the classifier is working
- `blind-test-set.jsonl` - post-cutoff events the model has not seen; used to generate forward-looking classifications

If you mix these, your accuracy numbers will be inflated by the model's ability to recognize famous events it already knows about, not its ability to classify genuinely novel ones.

**Status:** A first draft exists — `data/input/seeded-validation-set.jsonl` (7 events: the 5 real events also in `test_events.jsonl`, plus both perspectives of the NASDAQ/SpaceX benchmark case study from `Company-Level Classifier.md`). One deviation from the wording above: the expected labels live in a **separate** file, `data/input/seeded-validation-labels.jsonl` ({event_id, expected_classification}), not inline in the event JSON — an inline `expected_classification` field would flow straight into `FULL_EVENT_JSON` in the prompt and leak the answer to the model. Score a run against it with `python scripts/analyze_results.py --results <path> --ground-truth data/input/seeded-validation-labels.jsonl`. The labels themselves are Claude's draft reasoning through the framework, not yet confirmed by Yevhen — flagged per-row with a confidence level and source (some match this repo's own existing worked examples in `Shock Classifier.md`/`Altman Firing.md`/etc.; one — DeepSeek R1 vs. NVIDIA — is deliberately left as "medium confidence, debatable" as a discussion point). No `blind-test-set.jsonl` yet.

---

## General Engineering Checklist Before First Run

- [ ] OpenRouter key stored in `.env` and not committed to the repo (add `.env` to `.gitignore` now if not already there)
- [ ] JSONL output file path set to a location outside the repo or excluded via `.gitignore` (results files will be large)
- [ ] Checkpoint/resume logic tested on a small batch of 10 events before running at full scale
- [ ] Rate limit handling tested by intentionally hitting a free model's limit and verifying the backoff works
- [ ] Structured output parsing tested on outputs from each model tier to confirm JSON extraction works across formats
- [ ] Grok search disabled and Command R+ retrieval disabled if either model is included in the run
- [ ] Domain context decision made and documented before the run so it is consistent across all events
- [ ] Seeded validation set and blind test set kept in separate files from the start
