# Tier Comparison Findings: Self-Consistency vs. Cross-Tier Agreement

First real-data comparison for Project Jupiter's Company-Level Classifier, run against
the 1,139-event Apple-ecosystem dataset (`data/input/apple_events.jsonl`, see
`prepare_apple_events.py`). Each of two model tiers was run **twice** on the identical
input at `temperature=0`, specifically to separate two different questions that get
conflated if you only run each model once:

1. **Self-consistency** — does a model agree with itself on a second pass?
2. **Cross-tier agreement** — do the two tiers agree with each other?

Runs: `runs/apple_full_llama31_8b.jsonl` / `_run2.jsonl` (Tier 1, Llama 3.1 8B Instruct)
and `runs/apple_full_llama33_70b.jsonl` / `_run2.jsonl` (Tier 2, Llama 3.3 70B Instruct).
Run outputs are gitignored (regenerable); this file is the durable record of the findings.

## Headline result

**Self-consistency is not correlated with model size the way you'd expect.** The cheap,
small Tier 1 model agrees with itself on a second run 97.6% of the time. The larger,
more expensive Tier 2 model agrees with itself only 59.5% of the time — on the identical
1,139 events, at temperature 0. Cross-tier agreement is low and *stable* across both runs
(~37-39%), meaning the Tier 1/Tier 2 divergence is a real, structural difference in how
the two models approach the task, not noise — but Tier 2's low self-consistency means a
single Tier 2 pass can't be trusted as ground truth for what that "real difference" is.

## Per-run summary

| | Tier 1 v1 | Tier 1 v2 | Tier 2 v1 | Tier 2 v2 |
|---|---|---|---|---|
| Model | Llama 3.1 8B | Llama 3.1 8B | Llama 3.3 70B | Llama 3.3 70B |
| Success rate | 1123/1139 (98.6%) | 1117/1139 (98.1%) | 1138/1139 (99.9%) | 1138/1139 (99.9%) |
| Neither | 895 (79.7%) | 897 (80.3%) | 364 (32.0%) | 343 (30.1%) |
| Gray Swan | 182 (16.2%) | 173 (15.5%) | 306 (26.9%) | 303 (26.6%) |
| Gray Rhino | 5 (0.4%) | 6 (0.5%) | 304 (26.7%) | 323 (28.4%) |
| White Swan | 32 (2.9%) | 32 (2.9%) | 94 (8.3%) | 95 (8.3%) |
| Black Swan | 9 (0.8%) | 9 (0.8%) | 70 (6.1%) | 74 (6.5%) |
| Avg latency | 1.48s | 1.56s | 13.84s | 9.80s |
| Cost (1,139 events) | $0.046 | $0.046 | $0.361 | $0.362 |

Aggregate distributions look stable within each tier across its two runs — this is what
makes the self-consistency numbers below counterintuitive at first glance.

## Self-consistency (same model, same data, two runs)

**Tier 1 (Llama 3.1 8B): 1087/1114 = 97.6% agreement.** Where it does flip, it's almost
entirely Gray Swan ↔ Neither (21 of 27 flips) — borderline cases wobbling around the
"is this even a shock" boundary, not wholesale disagreement.

**Tier 2 (Llama 3.3 70B): 677/1137 = 59.5% agreement.** Nearly 4 in 10 events get a
*different* classification on an identical rerun. The dominant flip is Gray Swan ↔
Gray Rhino (190 of 460 flips) — the model can't reliably distinguish "structural
certainty, timing was the surprise" (Gray Swan) from "victim saw it coming but didn't
dodge it" (Gray Rhino) for the same event twice in a row.

**Implication:** the aggregate Tier 2 distribution looking stable run-to-run is
coincidental — similar totals land in each bucket, but often not for the same events.
A single Tier 2 pass is not reliable enough to trust on its own for any individual event.

## Cross-tier agreement (Tier 1 vs. Tier 2, same data)

| | Agreement |
|---|---|
| Tier 1 v1 vs. Tier 2 v1 | 435/1122 = 38.8% |
| Tier 1 v2 vs. Tier 2 v2 | 397/1116 = 35.6% |

Consistently low and consistently in the same direction both times: Tier 2 classifies
"Neither" far less often (30-32% vs. Tier 1's ~80%) and spreads the rest across
Gray Swan/Gray Rhino/Black Swan/White Swan. Top disagreement: Tier 1 says Neither where
Tier 2 says Gray Swan or Gray Rhino (roughly 700 of the ~1,120 disagreements across both
run pairs).

## A concrete false-positive example

Event: *"Visit Ukraine – Employee mobilization deferments through Diia may be suspended
until September 1"* — a story about Ukrainian military mobilization exemption rules, with
no evident connection to Apple.

- **Tier 1:** `strategic_impact`: "No significant impact on Apple's internal math or
  strategic direction." → **Neither**. Correct call.
- **Tier 2:** `load_bearing_assumption`: *"The assumption that Apple's operations and
  supply chain in Ukraine would remain unaffected by changes in mobilization exemption
  rules is violated."* → **Black Swan**. This is confabulated — no such Apple-Ukraine
  supply-chain dependency exists in the source text; the model manufactured a plausible-
  sounding justification for a shock classification that isn't there.

This is the mechanism behind the divergence: Tier 2's larger reasoning capacity, without
a mechanism to keep it honest, produces *more elaborate justifications for false
positives*, not just more sensitive true positives. Tier 1's conservatism (default to
Neither) is arguably safer precisely because it doesn't reach for the same over-explained
narratives.

## What this means for the project

1. **A single classification pass, from either tier, is not sufficient to trust.** Tier 1
   is stable but likely under-detects; Tier 2 finds more candidate shocks but can't be
   trusted run-to-run on which ones.
2. **This is now the concrete, data-backed justification for the self-consistency /
   escalation cascade** proposed in `scale-workflow.md`, rather than a hypothetical
   scale-time optimization: run twice (or more) per event, treat disagreement itself as
   the confidence signal, and escalate disagreements to a frontier model or human for
   adjudication rather than trusting any single tier's verdict.
3. **Neither tier's output should be reported as "accuracy" without a ground-truth pass.**
   The next step to actually answer "which tier is right" is running the disagreement set
   through a frontier model (or manual review) as an adjudicator — this data only
   establishes *that* the tiers disagree and *why* (confabulation risk at Tier 2, possible
   under-sensitivity at Tier 1), not which one is closer to correct.
