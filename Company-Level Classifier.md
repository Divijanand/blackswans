# The Relativity of Shocks: Company-Level Classifier

While macroeconomic shocks reset entire domains, the perception of a shock is highly relative. A Black Swan for a victim is often a meticulously executed business plan (a White Swan) for the perpetrator. 

To operationalize this, we must extend the domain-agnostic classifier into a **Company-Level Perspective**. This parallel framework evaluates a shock not by its impact on the abstract market, but by how it violently intersects with a *specific entity's* internal planning assumptions.

---

## 1. The Company-Level Decision Procedure

To classify an event from the perspective of a specific company (Target Entity), run the event through these modified gatekeeper checks:

### Check 1: The Internal Topology Shift (Strategic Impact)
*   **The Heuristic Gut-Check:** *Which of this specific company's load-bearing business assumptions does this event violate?*
*   **Question A:** Did this event break the Target Entity’s baseline operational, financial, or product mathematics, forcing the C-suite to fundamentally rewrite their strategic direction or capital allocation?
*   **Question B:** Did it permanently alter the Target Entity's specific position on the competitive leaderboard (either vaulting them forward or severely degrading their moat)?
*   **Decision:**
    *   If **YES** to both, proceed to Check 2.
    *   If **NO** to either, run the sub-check: *Was this an anticipated threat or dependency for the Target Entity that failed to materialize, breaking their expensive defensive hedges?* (If YES -> **Broken Prior**. If NO -> **Neither / Standard Volatility**).

### Check 2: The Internal Horizon Test (Strategic Radar)
*   **Question:** Was this specific event explicitly documented in the Target Entity’s internal risk registers, competitive intelligence briefs, or strategic planning assumptions? Was the leadership actively hedging against or engineering it?
*   **Decision:**
    *   If **YES, and they were the victim/bystander:** Classify as a **Gray Rhino** (They saw it coming but failed to dodge).
    *   If **YES, and they engineered it:** Classify as a **White Swan** (The Prime Mover).
    *   If **NO (It was completely off their internal radar):** Proceed to Check 3.

### Check 3: The Internal Architectural Mechanics (Probability Type)
*   **Question:** Within the Target Entity's specific competitive and supply-chain model, was this disruption a structural certainty (e.g., a known supplier bottleneck, an inevitable regulatory cliff, a predictable competitor capability), with only the precise timing or magnitude acting as a surprise?
*   **Decision:**
    *   If **YES:** Classify as a **Gray Swan**.
    *   If **NO:** Classify as a **Black Swan**.

---

## 2. Benchmark Case Study: The NASDAQ / SpaceX Listing

This case study perfectly demonstrates why shocks must be classified relative to the observer. 

**The Scenario:** To secure the listing of SpaceX (a massive, unprecedented private mega-cap), NASDAQ unexpectedly and aggressively bends its historical listing rules and index-weighting caps, fundamentally rewiring the underlying mechanics of the QQQ index overnight.

### Perspective A: The Passive Retail QQQ Investor
*   **Target Entity:** Passive Retail Index Investor
*   **Check 1 (Internal Topology Shift):** **PASSED.** The core assumption of their portfolio—that the QQQ tracks a predictable, rule-bound tech index—is broken. Their exposure profile is radically altered without their consent.
*   **Check 2 (Internal Horizon Test):** **FAILED.** Retail investors do not have access to backroom negotiations between stock exchanges and private space companies. This was entirely off their radar.
*   **Check 3 (Internal Architectural Mechanics):** **FAILED.** Exchanges altering foundational weighting rules for a single private entity is not a structural certainty of passive investing; it is an unprecedented breach of index protocol.
*   **Classification for Retail:** **Black Swan.** (An unpredicted, exogenous shock that violently alters their financial reality).

### Perspective B: Elon Musk / SpaceX Leadership
*   **Target Entity:** SpaceX Executive Team
*   **Check 1 (Internal Topology Shift):** **PASSED.** It fundamentally rewrites their cap table, unlocks massive liquid capital, and alters their long-term strategic trajectory.
*   **Check 2 (Internal Horizon Test):** **PASSED.** They didn't just see it coming; they spent months in closed-door negotiations actively leveraging their private valuation to force NASDAQ's hand. 
*   **Classification for SpaceX:** **White Swan (Engineered).** (A meticulously planned, highly visible execution of corporate strategy).

---

## 3. Company-Level Classifier Prompt Template

To execute this dynamically, use this prompt template:

```markdown
Your task is to act as an elite corporate strategist and classify the following candidate event strictly from the perspective of a specific Target Entity.

### Inputs:
- **The Event:** [ INSERT EVENT ]
- **The Target Entity:** [ INSERT SPECIFIC COMPANY / ACTOR ]

### Detailed Analysis Requirements:
Pass the event through the Company-Level Decision Procedure. Define your reasoning explicitly for each check.

1. **The Internal Topology Shift Test:**
   - **Load-Bearing Assumption Violated:** (What core belief or financial model of the Target Entity did this shatter?)
   - Did this force the Target Entity to rewrite its strategic direction?
   - Did it permanently alter their specific position on the leaderboard?
   - *(If NO to either, classify as Broken Prior or Neither/Volatility).*

2. **The Internal Horizon Test:**
   - Was this explicitly on the Target Entity's internal planning radar? Were they hedging it or engineering it?
   - *(If YES and victim: Gray Rhino. If YES and prime mover: White Swan. If NO: Proceed to Check 3).*

3. **The Internal Architectural Mechanics Test:**
   - Was this a structural certainty within their specific supply-chain or competitive model, just with uncertain timing?
   - *(If YES: Gray Swan. If NO: Black Swan).*

### Output Format:
Provide your evaluation using these explicit headers:
- **Target Entity Context:** (1-sentence framing)
- **Load-Bearing Assumption Violated:** (1 sentence)
- **Step-by-Step Check Walkthrough:** (Document Check 1, 2, and 3)
- **Final Taxonomic Classification for Target Entity:** [ Black Swan / Gray Rhino / Gray Swan / White Swan / Broken Prior / Neither ]
- **Strategic Impact on Target:** (How did their internal math change?)
