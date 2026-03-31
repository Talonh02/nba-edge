# NBA Edge — Required Improvements

Findings from code logic and betting model audits. These are real issues, not nice-to-haves.

---

## Code Logic Bugs

### Critical

- [ ] **Odds matching uses OR instead of AND** (`crunch.py:555-558`). Home OR away name match could cross-match games. Must require both teams to match.

- [ ] **Four Factors argument order is swapped** (`crunch.py:243`). Away is passed as `team_a`, home as `team_b`, but results are used as if team_a = home. Grade and flags point to the wrong team.

- [ ] **Elo timestamp records "now" not the actual end_date** (`elo.py:305`). Saves `datetime.now()` but processed through yesterday. If you run at 11pm, tomorrow's run thinks today was already processed — loses a day of Elo updates.

- [ ] **`team_stats` used before null check** (`crunch.py:549`). If cache miss returns None, `.get()` crashes with `AttributeError`.

- [ ] **Monte Carlo ignores the logistic regression probability** (`model.py:135-155`). The `home_prob` parameter is accepted but never used. MC result is completely disconnected from the LR model. This is a silent logic error.

### Moderate

- [ ] **`decimal_to_american` division by zero** (`fetch_odds_stake.py:43`). If `decimal_odds == 1.0`, divides by zero.

- [ ] **Stake fuzzy match could collide** (`crunch.py:571`). Matching on last word of team name — "Trail Blazers" vs other teams ending in similar words could misfire.

- [ ] **Hardcoded EDT offset** (`dashboard.py:99`). Wrong during EST (Nov–Mar, which is most of the NBA season). Should detect timezone automatically.

- [ ] **Timezone-naive vs aware comparison** (`cache.py:69`). Could raise TypeError if a timestamp is stored without timezone info.

---

## Betting Model Issues

### The statistical core needs real work

- [ ] **Logistic regression weights are fabricated.** No training step, no MLE, no cross-validation. Hand-picked numbers labeled "empirically calibrated." Double-counts features — `net_rating` is already `off_rating - def_rating`, yet all three get separate weights. Multicollinearity would destroy a real regression.

- [ ] **Monte Carlo simulation is theater.** The `home_prob` argument is never used. Win probability is entirely determined by score means passed in, completely independent of the logistic regression output. It produces a different probability than the model it claims to elaborate on. This is decoration, not inference.

- [ ] **"Bayesian" strength estimation is not Bayesian.** No prior distribution, no likelihood function, no posterior update. It's a weighted average with ad hoc volatility adjustment. The uncertainty intervals assume normality with no justification.

- [ ] **Player prop projections are too naive to find real edge.** Adjusting season average by a dampened team-level defensive multiplier ignores position-specific defense, minutes fluctuation, game script effects, and the fact that prop lines already price in opponent quality. The dampening factor and standard deviations are invented.

- [ ] **Four Factors: correctly structured but misapplied.** Oliver's weights explain season-level win variance, not individual game outcomes. The edge numbers are tiny and the letter-grade thresholds are arbitrary.

- [ ] **Edge calculation: right formula, unreliable inputs.** `model_prob - implied_prob` is correct math. But if model_prob comes from made-up logistic weights, the "edges" are noise.

---

## What Would Make This Genuinely Useful

1. **Fit the logistic regression on actual historical game data.** Even one season of NBA results. Learn the weights via MLE instead of guessing them.

2. **Validate against closing lines.** Track CLV (Closing Line Value) — did our bets beat the closing line? This is the #1 predictor of long-term profitability.

3. **Make Monte Carlo actually use the model's probability.** Right now it ignores it entirely.

4. **Remove redundant features.** `net_rating`, `off_rating`, `def_rating` are collinear. Pick one or let the regression sort it out.

5. **Add real injury adjustments.** Currently placeholder. Should pull injury reports and adjust team strength based on who's actually out.

6. **Position-specific prop projections.** Adjust for how the opponent defends the specific position, not just team-level defensive rating.

7. **Backtest everything.** Run the model retroactively on completed games, score predictions against outcomes, measure calibration.

---

## Bottom Line

The infrastructure is solid — data pipeline, caching, Stake integration, dashboard generation all work well. The statistical core is a confidence-generating machine, not an edge-finding one. It produces picks that *feel* rigorous but aren't calibrated against reality. The path forward is fitting real models to real data and validating against actual outcomes.
