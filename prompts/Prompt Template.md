##Reusable Classifier Prompt Template

Copy and paste the raw text block below into an LLM to execute this exact classification framework on any new or speculative event.

Your task is to act as an elite macroeconomic risk architect and classify the following candidate event using the strict, domain-agnostic "Vector-of-Influence Classifier Framework."

### The Event to Analyze:
[ INSERT EVENT NAME AND BRIEF DESCRIPTION HERE ]

### Detailed Analysis Requirements:
Pass the event through the following ordered decision procedure. Define your reasoning explicitly for each check.

1. **The Topology Shift Test (Impact & Breadth):**
   - **The Heuristic Gut-Check:** *Which load-bearing assumption does this event violate?* (Identify the core industry belief this event shatters—e.g., "Frontier AI requires infinite CapEx" or "Apple never opens iOS").
   - Did this event break the baseline operational or financial assumptions of the ecosystem, forcing a meaningful share of market players (not just the immediate parties) to rewrite their strategic direction?
   - Did it structurally rearrange the competitive leaderboard (who's ahead, who's behind, who is relevant)?
   - *If NO to either:* Is this an expected disruption that failed to materialize, breaking everyone's defensive hedges? (If yes -> Classify as Broken Prior. If no -> Classify as Neither/Standard Volatility).
   - *If YES to both:* Proceed to Check 2.

2. **The Horizon Test (Insider Foresight):**
   - Was the event explicitly telegraphed, documented, or actively prepared for by informed industry insiders (even if ignored or mispriced by the broader market)?
   - *If YES:* Stop and classify as a Gray Rhino.
   - *If NO:* Proceed to Check 3.

3. **The Architectural Mechanics Test (Probability Type):**
   - Was the underlying technical, physical, or legal mechanism structurally anticipated as a long-term future certainty, with only the interface, timing, or adoption velocity acting as the surprise?
   - *If YES:* Classify as a Gray Swan.
   - *If NO:* Classify as a Black Swan.

### Output Format:
Provide your evaluation using these explicit headers:
- **Load-Bearing Assumption Violated:** (1 sentence)
- **Step-by-Step Check Walkthrough:** (Document your analysis for Check 1, Check 2, and Check 3)
- **Final Taxonomic Classification:** [ Black Swan / Gray Rhino / Gray Swan / Broken Prior / Neither ]
- **Strategic Trajectory Impact:** (Explain exactly how the leaderboard or operational math was reset).
