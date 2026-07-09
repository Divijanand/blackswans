# Model List: Project Jupiter Classifier Experiment

Tiered model list for running the black swan classifier at scale via OpenRouter and DigitalOcean.
Each model is tagged with its verified training cutoff, the OpenRouter model string, pricing, and a source link for the cutoff claim.

**How to use this list:** Yevhen's events dataset should use news events that are clearly post-cutoff for each tier. For the small/open-source tier, use events from January 2024 onward. For mid-tier, use March 2024 onward. For frontier, use late 2025 onward where possible. Cutoff dates marked with a tilde (~) are estimated from release date and publicly available training notes, not officially confirmed by the provider.

---

## Tier 1: Small / Open-Source (1B to 8B) via OpenRouter

These models are the cheapest to run and fastest for parallelized batches. They are also the most likely to struggle with structured JSON output and complex multi-step reasoning. Treat results from this tier as a lower-bound baseline, not a performance target.

| Model | Provider | Params | Training Cutoff | Cutoff Source | OpenRouter Model String | OpenRouter Link | Notes |
|---|---|---|---|---|---|---|---|
| Llama 3.1 8B Instruct | Meta | 8B | December 2023 | [Meta model card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) | `meta-llama/llama-3.1-8b-instruct` | [OpenRouter](https://openrouter.ai/meta-llama/llama-3.1-8b-instruct) | Good baseline; July 2024 release date; well-documented cutoff |
| Llama 3.2 3B Instruct | Meta | 3B | August 2024 | [Meta model card](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) | `meta-llama/llama-3.2-3b-instruct` | [OpenRouter](https://openrouter.ai/meta-llama/llama-3.2-3b-instruct) | Smaller and faster than 3.1 8B; useful for volume runs |
| Phi-3 Mini 3.8B | Microsoft | 3.8B | October 2023 | [Microsoft docs](https://azure.microsoft.com/en-us/blog/introducing-phi-3-redefining-whats-possible-with-slms/) | `microsoft/phi-3-mini-128k-instruct` | [OpenRouter](https://openrouter.ai/microsoft/phi-3-mini-128k-instruct) | 128K context window; cutoff is early; use older event windows |
| Phi-4 Mini | Microsoft | ~4B | June 2024 | [PromptQuorum cutoff list](https://www.promptquorum.com/prompt-engineering/knowledge-cutoffs-and-geo) | `microsoft/phi-4-mini-instruct` | [OpenRouter](https://openrouter.ai/microsoft/phi-4-mini-instruct) | More recent cutoff than Phi-3; better for 2024 events |
| Gemma 2 9B | Google | 9B | ~June 2024 | [Gemma 3 technical report cross-reference](https://arxiv.org/pdf/2605.27296) | `google/gemma-2-9b-it` | [OpenRouter](https://openrouter.ai/google/gemma-2-9b-it) | Cutoff not officially published; estimated from release timeline (June 2024 release) |
| Qwen2.5 7B | Alibaba | 7B | ~End of 2023 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | `qwen/qwen-2.5-7b-instruct` | [OpenRouter](https://openrouter.ai/qwen/qwen-2.5-7b-instruct) | Cutoff disputed; some sources say Oct 2023, some say June 2024; treat conservatively as end of 2023 |

---

## Tier 2: Mid-Tier (24B to 72B) via OpenRouter

Better instruction-following and structured output reliability than Tier 1. More expensive per token but more likely to produce parseable JSON. Good target tier for the main experimental run.

| Model | Provider | Params | Training Cutoff | Cutoff Source | OpenRouter Model String | OpenRouter Link | Notes |
|---|---|---|---|---|---|---|---|
| Llama 3.1 70B Instruct | Meta | 70B | December 2023 | [Meta model card](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) | `meta-llama/llama-3.1-70b-instruct` | [OpenRouter](https://openrouter.ai/meta-llama/llama-3.1-70b-instruct) | Best-documented open-source cutoff; reliable JSON output |
| Llama 3.3 70B | Meta | 70B | December 2023 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | `meta-llama/llama-3.3-70b-instruct` | [OpenRouter](https://openrouter.ai/meta-llama/llama-3.3-70b-instruct) | Same cutoff as 3.1 70B but better instruction tuning; prefer this over 3.1 70B where cost allows |
| Llama 4 Maverick | Meta | 17Bx128E (MoE) | August 2024 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | `meta-llama/llama-4-maverick` | [OpenRouter](https://openrouter.ai/meta-llama/llama-4-maverick) | Later cutoff than 3.x family; better for 2024 events |
| Mistral Small 3 (24B) | Mistral | 24B | ~October 2023 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | `mistralai/mistral-small-3.1-24b-instruct` | [OpenRouter](https://openrouter.ai/mistralai/mistral-small-3.1-24b-instruct) | Ministral family cutoff listed as Oct 2023; verify against events used |
| Gemma 2 27B | Google | 27B | ~June 2024 | [Arxiv cross-reference](https://arxiv.org/pdf/2605.27296) | `google/gemma-2-27b-it` | [OpenRouter](https://openrouter.ai/google/gemma-2-27b-it) | Same caveat as Gemma 2 9B; cutoff not officially confirmed; use June 2024 as conservative estimate |
| Gemma 3 27B | Google | 27B | August 2024 | [PromptQuorum cutoff list](https://www.promptquorum.com/prompt-engineering/knowledge-cutoffs-and-geo) | `google/gemma-3-27b-it` | [OpenRouter](https://openrouter.ai/google/gemma-3-27b-it) | Multimodal; better cutoff than Gemma 2; prefer this over Gemma 2 27B for 2024 events |
| Qwen2.5 72B | Alibaba | 72B | ~End of 2023 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | `qwen/qwen-2.5-72b-instruct` | [OpenRouter](https://openrouter.ai/qwen/qwen-2.5-72b-instruct) | Same cutoff ambiguity as Qwen2.5 7B; treat conservatively |
| DeepSeek V3 | DeepSeek | 671B (MoE, 37B active) | July 2024 | [FixAEO cutoff list](https://fixaeo.com/ai-knowledge-cutoff/) | `deepseek/deepseek-chat-v3-0324` | [OpenRouter](https://openrouter.ai/deepseek/deepseek-chat-v3-0324) | Cutoff not officially published by DeepSeek; estimated from V3 December 2024 release date; good for 2023-mid-2024 events |
| DeepSeek R1 | DeepSeek | 671B (MoE, 37B active) | July 2024 | [HuggingFace discussion](https://huggingface.co/deepseek-ai/DeepSeek-R1/discussions/212) | `deepseek/deepseek-r1` | [OpenRouter](https://openrouter.ai/deepseek/deepseek-r1) | Reasoning model; higher cost; use for edge cases where reasoning chain is part of what you want to evaluate |
| Command R+ | Cohere | ~104B | ~Early 2024 | [Cohere docs](https://docs.cohere.com/docs/command-r-plus) | `cohere/command-r-plus-08-2024` | [OpenRouter](https://openrouter.ai/cohere/command-r-plus-08-2024) | Cutoff not officially stated; retrieval-augmented by default which complicates post-cutoff testing; flag this in methodology |

---

## Tier 3: Frontier via DigitalOcean / Direct APIs

These are the ground truth tier. The expectation is that frontier models produce the most reliable classifications; their outputs serve as the "correct" label against which smaller models are compared. Most expensive per token. Run on DigitalOcean GPU instances or direct provider APIs per Yevhen's infra plan.

| Model | Provider | Training Cutoff | Cutoff Source | Access Route | API Docs | Notes |
|---|---|---|---|---|---|---|
| Claude Sonnet 4.6 | Anthropic | August 2025 | [Anthropic docs](https://docs.anthropic.com) | Anthropic API direct | [API docs](https://docs.anthropic.com/en/api/getting-started) | Current production model; use this as primary frontier reference |
| Claude Opus 4.8 | Anthropic | January 2026 | [PromptQuorum cutoff list](https://www.promptquorum.com/prompt-engineering/knowledge-cutoffs-and-geo) | Anthropic API direct | [API docs](https://docs.anthropic.com/en/api/getting-started) | Most recent reliable cutoff of any model on this list; benchmark anchor for very recent events |
| GPT-5.1 | OpenAI | ~August 2025 | [FixAEO cutoff list](https://fixaeo.com/ai-knowledge-cutoff/) | OpenAI API direct | [API docs](https://platform.openai.com/docs/api-reference) | Officially listed as GPT-5.5 at Aug 2025 on some sources; treat as approximate |
| Gemini 2.5 Pro | Google | January 2025 | [PromptQuorum cutoff list](https://www.promptquorum.com/prompt-engineering/knowledge-cutoffs-and-geo) | Google AI Studio API | [API docs](https://ai.google.dev/gemini-api/docs) | Solid choice for mid-2024 to early-2025 event windows |
| Grok 4.3 | xAI | November 2024 | [HaoooWang cutoff repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) | xAI API or via OpenRouter | [API docs](https://docs.x.ai/api) | Has live X/Twitter search by default; disable for the experiment or results will be contaminated by real-time retrieval |
| DeepSeek V4 Flash | DeepSeek | ~April 2026 | [OpenRouter blog June 2026](https://openrouter.ai/blog/insights/the-open-weight-models-that-matter-june-2026/) | DeepSeek API or OpenRouter | [API docs](https://api-docs.deepseek.com/) | Most recent open-weight cutoff; MIT license; $0.14/$0.28 per million tokens in/out |

---

## Useful Reference Links

- [OpenRouter model browser](https://openrouter.ai/models) - live pricing and availability; always check here before running since free model status changes
- [HaoooWang LLM cutoff dates repo](https://github.com/HaoooWang/llm-knowledge-cutoff-dates) - community-maintained cutoff reference with primary sources
- [PromptQuorum cutoff list](https://www.promptquorum.com/prompt-engineering/knowledge-cutoffs-and-geo) - verified current cutoffs for frontier models as of June 2026
- [FixAEO cutoff database](https://fixaeo.com/ai-knowledge-cutoff/) - additional reference with sourcing notes
- [OpenRouter free models page](https://openrouter.ai/collections/free-models) - check here before spending credits; free tier rotates monthly
- [OpenRouter June 2026 open-weight rundown](https://openrouter.ai/blog/insights/the-open-weight-models-that-matter-june-2026/) - current state of open-weight models as of this writing
