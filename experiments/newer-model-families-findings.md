# Newer Model Families: GLM 4.6, Qwen3.6 27B, Gemma 4 31B

Yevhen flagged that the Llama family in `model-list.md` is dated and suggested testing
newer releases instead — GLM, Qwen3.6, Gemma 4. Ran one representative model from each
family against the same 1,139-event Apple dataset used in
[tier-comparison-findings.md](tier-comparison-findings.md), at the same `--model-tier
tier2` settings (15 workers, temperature 0). **This run is incomplete** — two of the three
models are blocked on the OpenRouter key's spending limit, addressed below.

## Result summary

| Model | Success | Cost (this run) | Cost / 1,000 events | Status |
|---|---|---|---|---|
| Llama 3.1 8B *(baseline)* | 1123/1139 (98.6%) | $0.046 | $0.04 | complete |
| Llama 3.3 70B *(baseline)* | 1138/1139 (99.9%) | $0.361 | $0.32 | complete |
| **Gemma 4 31B** | 1136/1139 (99.7%) | $0.376 | $0.33 | **complete, clean** |
| **Qwen3.6 27B** | 982/1139 (86.2%) | $4.25 | $4.33 | **incomplete — credit-limited** |
| **GLM 4.6** | 80/1139 (7.0%) | $0.32 (partial) | n/a | **incomplete — mostly failed** |

## Finding 1: the newer "reasoning-style" models need a much bigger token budget

The `--max-tokens 2000` default (set after the earlier runaway-generation bug fix — see
`experiment-flags.md` Flag 8/10) was tuned against Llama's behavior. Both GLM 4.6 and
Qwen3.6 blow past it constantly:

- **Qwen3.6 27B** at `--max-tokens 2000`: 524/1139 failed on `LengthFinishReasonError`
  (46%). Retried the failures at `--max-tokens 8000`: success jumped from 499 to 982/1139,
  confirming this model generates far more tokens per response (likely extended
  reasoning/thinking content) than Llama ever did — 1.5M completion tokens across 982
  successful calls vs. ~465K for Llama 3.3 70B across 1138 calls, roughly **3x the tokens
  per classification**.
- **GLM 4.6** is worse: 813/1139 (71%) failed the same way even before any retry. It
  likely needs a budget larger than the 8000 that helped Qwen3.6 — not yet tested, see
  blocker below.

**Implication:** these aren't drop-in swaps for the Llama tiers in a cost-sensitive
pipeline. Any model evaluation going forward needs a model-specific `--max-tokens` pass
(or a first small-batch calibration run) before trusting a large-batch result — a fixed
default across model families produces misleadingly high failure rates, not a fair
comparison.

## Finding 2: cost-per-classification varies far more than model tier alone suggests

Even on the reduced/partial successful subset, Qwen3.6 27B cost **~$4.33 per 1,000
events** — roughly **13x** Llama 3.3 70B and **~100x** Llama 3.1 8B, driven almost
entirely by verbose completions, not input size. This is a direct, concrete data point
for the cost lever discussed in `scale-workflow.md` (`Section 7`): at the ~1M-article
scale the fellowship is ultimately aiming at, the cost difference between "verbose
reasoning model" and "concise instruct model" for the *same tier* of parameter count is
large enough to be the dominant cost driver, not the tier itself.

## Finding 3: distribution shifts again, but not comparable yet

Gemma 4 31B's classification spread (complete, trustworthy): Neither 64.2%, Gray Rhino
19.2%, White Swan 10.6%, Gray Swan 2.6%, Broken Prior 2.3%, Black Swan 1.2% — notably the
first model to produce meaningful **Broken Prior** counts (26 events), a label both Llama
tiers essentially never used. Qwen3.6's and GLM's distributions (78.2%/81.3% Neither
respectively) aren't reported here as comparable findings — they're partial samples
biased toward whichever events happened to fit inside the token budget on a given
attempt, not a fair read on those models' actual classification behavior.

## Blocker: OpenRouter key hit its spending limit

Both GLM 4.6 and Qwen3.6 runs are hitting **HTTP 402** errors mid-run — OpenRouter's own
message: *"This request requires more credits, or fewer max_tokens... visit
[workspace]/keys/... and adjust the key's monthly limit."* This is a hard stop, not
something retryable from this side. 233 of GLM's failures and 112 of Qwen3.6's remaining
failures are this error, on top of the token-budget issue above.

**Next steps (deferred — Yevhen to raise the key's limit):**
1. Raise the OpenRouter key's monthly spending limit.
2. Re-run GLM 4.6 with a calibrated `--max-tokens` (try 8000, likely needs more given its
   813/1139 failure rate even exceeded Qwen3.6's at the same setting).
3. Finish the remaining 157 Qwen3.6 events once budget allows.
4. Once both are complete and clean, add them to a same-shape comparison table against
   the Llama tiers, and — given `tier-comparison-findings.md`'s result that single-pass
   classification isn't trustworthy — run each newer model twice for a self-consistency
   check before drawing any "this model is better" conclusion.

Until then, **Gemma 4 31B is the only newer-family model with a complete, trustworthy
result**, and is the closest usable substitute for the aging Llama tiers if one is needed
before the credit limit is resolved.
