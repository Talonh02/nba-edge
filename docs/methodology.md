# NBA Edge — Model Methodology

## Overview

A 6-layer prediction model synthesized from FiveThirtyEight's published Elo/RAPTOR methodology, Dean Oliver's Four Factors framework, the "Pietrus Model" approach used by sharp bettors, and academic research (MOVDA 2025, Nature Scientific Reports 2025).

The key insight: no single public source combines all these layers. Each layer alone is well-documented, but the synthesis — especially with Claude as the qualitative override — is our edge.

---

## Layer 1: Elo Power Ratings

**Source:** FiveThirtyEight (Neil Paine), nicidob analysis proving Elo ≈ logistic regression.

Elo is the simplest rating system that works. Every team starts at 1500. After each game, the winner gains points and the loser loses points. The amount depends on:
- **K-factor (K=20):** How much each game matters. Higher K = more reactive to recent results.
- **Margin of victory:** Blowouts move ratings more, but with diminishing returns (log scale). This is the MOVDA improvement from the 2025 arXiv paper.

**Win probability formula:**
```
P(A wins) = 1 / (1 + 10^((Elo_B - Elo_A) / 400))
```

**Spread conversion:** Each 25 Elo points ≈ 1 point of spread.

**Accuracy:** ~67%. Surprisingly, this barely changes with parameter tuning — Elo is robust.

**Why it works:** Elo is mathematically equivalent to logistic regression over the same features (proven by nicidob). It's auto-regressive — each game updates the model. No training set needed.

---

## Layer 2: Four Factors (Dean Oliver)

**Source:** Basketball on Paper (2004). Squared2020 analysis showing 91.4% of win variation explained.

The four things that determine basketball games:

| Factor | Weight | What it measures |
|---|---|---|
| eFG% | 40% | Shooting efficiency (accounts for 3PT value) |
| TOV% | 25% | Ball security (turnovers per possession) |
| OREB% | 20% | Second chances (offensive rebounds) |
| FTRate | 15% | Getting to the free throw line |

For each matchup, we compare:
- Team A's **offensive** factors vs Team B's **defensive** factors
- Team B's **offensive** factors vs Team A's **defensive** factors

The weighted sum of edges produces a matchup score. A team with elite eFG% against a team that allows high opponent eFG% = shooting mismatch (the most heavily weighted factor).

**Why this matters for betting:** The market knows team records and basic stats. But specific matchup interactions (e.g., "this team forces turnovers, and the opponent turns it over a lot") can be underpriced because casual bettors don't think in these terms.

---

## Layer 3: Player-Level Intelligence

**Sources:** DARKO (free, updated daily), EPM (free, updated nightly).

The team is not the same every night. Injuries change everything. Layer 3 adjusts team strength based on who's actually playing.

- **DARKO** (apanalytics.shinyapps.io/DARKO/): Bayesian/Kalman filter model. Rated #1 by NBA executives. Free.
- **EPM** (dunksandthrees.com/epm): Estimated Plus-Minus. Rated #2 by executives. Free.

**How we use it:** If a team's top DARKO-rated player is out, we estimate the team's decline. A team missing its best player by 3 DARKO points might drop ~2-3 points of expected margin.

*Status: Placeholder in v1. Manual override via Claude for now. Automated integration planned.*

---

## Layer 4: Contextual Adjustments

**Source:** FiveThirtyEight's published adjustment values.

| Factor | Adjustment | Source |
|---|---|---|
| Home court | +70 Elo (~3.5 pts) | 538 |
| Back-to-back | -46 Elo (~2.3 pts) | 538 |
| Extra rest (per day, up to 3) | +25 Elo (~1.25 pts) | 538 |
| Denver altitude | +15 Elo (~0.75 pts) | 538 |
| Cross-country travel | -10 Elo (~0.5 pts) | Estimated |

These are applied to the Elo prediction before calculating win probability.

**Why this matters:** Back-to-back is the single most exploitable contextual factor. A team on a B2B underperforms by ~2.3 points on average. The market adjusts for this, but often not enough — especially in less-publicized games.

---

## Layer 5: Market Comparison & Line Shopping

**The math that matters:**

1. **Convert odds to probability:**
   - Positive odds: `prob = 100 / (odds + 100)`
   - Negative odds: `prob = |odds| / (|odds| + 100)`

2. **Calculate edge:** `edge = model_prob - implied_prob`
   - Edge > 3% = Strong play
   - Edge 2-3% = Lean
   - Edge < 0% = Market has it right (or against us)

3. **Line shopping:** Compare the same bet across 40+ books. If DraftKings has -3.5 and FanDuel has -4.5, the 1-point difference is free value.

**Closing Line Value (CLV):** The single most important metric for long-term profitability. If you consistently bet at better odds than the closing line (the line right before tip-off), you are mathematically profitable long-term. We plan to track this.

---

## Layer 6: Qualitative Override

**Source:** The "Pietrus Model" approach (Unabated), adapted with Claude.

What models can't capture:
- Injury news that just broke (beat slow books by minutes)
- Motivation factors (revenge games, playoff clinch scenarios, tanking)
- Coaching/scheme matchups
- Public betting percentages (fade the public on large-market teams)
- Schedule spots (trap games before a marquee matchup)
- Team chemistry/drama

The roommate's intuition IS this layer. Claude helps formalize and supplement it with web-searched news and context.

---

## The Uncomfortable Truth

The betting market predicts NBA games at ~68-70% accuracy. Our model needs to beat that, not 50%. The realistic edge is 1-3 percentage points. That edge comes from:

1. **Line shopping** (literally free)
2. **Speed on injury news** (bet before books adjust)
3. **Contextual adjustments the market underprices** (B2B, rest, specific matchups)
4. **Discipline** (don't bet when there's no edge)

This tool doesn't pretend to be a money printer. It surfaces where the data disagrees with the market, explains why, and lets you decide.

---

## Key Sources

- FiveThirtyEight Elo: github.com/Neil-Paine-1/NBA-elo (MIT license)
- Elo ≈ logistic regression: nicidob.github.io/nba_elo
- MOVDA (2025): arXiv 2506.00348
- Four Factors: Dean Oliver, "Basketball on Paper" + squared2020.com
- Contextual adjustments: 538 published values
- InPredictable recency weighting: inpredictable.com/p/methodology.html
- DARKO: apanalytics.shinyapps.io/DARKO
- EPM: dunksandthrees.com/epm
- Sharp methodology: Unabated "NBA path to profitability"
- Reference project: github.com/kyleskom/NBA-Machine-Learning-Sports-Betting
