# NBA Edge

NBA betting analytics tool. Pulls live stats and odds, runs statistical models, generates a dashboard showing where the value is tonight.

## What it does

- Pulls team/player stats from the NBA's official data (570+ players, 30 teams, 40+ stats each)
- Pulls live odds from Stake.com (moneylines, spreads, totals — no account needed)
- Runs statistical analysis: Elo ratings, logistic regression, Monte Carlo simulation, Four Factors matchup breakdown
- Projects player props adjusted for tonight's matchup (points, rebounds, assists over/under leans)
- Generates an HTML dashboard you open in your browser

## Setup (one time)

```bash
# 1. Make sure you have Python 3
python3 --version

# 2. Install dependencies
cd ~/Desktop/Claude/nba-edge
python3 -m pip install nba_api pandas numpy requests python-dotenv scipy cloudscraper

# 3. (Optional) Add an Odds API key for line shopping across 40+ books
#    Sign up free at the-odds-api.com, then:
echo "ODDS_API_KEY=your_key_here" > .env
```

## Run it

```bash
cd ~/Desktop/Claude/nba-edge
python3 run.py
```

That's it. It fetches everything, runs the analysis, generates the dashboard, and opens it in your browser.

The first run takes ~60 seconds (pulling stats from NBA.com). After that, stats are cached — repeat runs take ~10 seconds.

### Options

```bash
python3 run.py --refresh   # Force re-fetch all stats (ignore cache)
python3 run.py --no-open   # Don't auto-open browser
```

## What's in the dashboard

- **Per-game breakdown**: Win probabilities, projected spreads, matchup analysis
- **Stake.com odds**: Live moneylines, spreads, totals with model comparison
- **Player prop projections**: Matchup-adjusted projections with OVER/UNDER leans — this is the good stuff for parlays
- **Insight flags**: Specific edges the model found (3PT mismatches, pace mismatches, hot/cold streaks, talent gaps)
- **Elo power rankings**: All 30 teams ranked by current strength

## What the model does (plain English)

1. **Elo ratings** — tracks team strength based on wins/losses and margin of victory. Updates after every game.
2. **Four Factors** — the four things that determine basketball games (shooting efficiency, turnovers, rebounds, free throws). Compares each team's offense vs the opponent's defense.
3. **Logistic regression** — combines 18 features (efficiency, shooting, pace, recent form) into a win probability. More nuanced than Elo alone.
4. **Monte Carlo simulation** — runs 10,000 simulated games to get confidence intervals ("they win 65% of the time, but the spread could be anywhere from -5 to +20").
5. **Player prop projections** — adjusts each player's season averages based on who they're playing tonight. If a guy averages 22 PPG and faces the worst defense in the league, we project him higher.

## Honest disclaimer

This tool won't beat the sportsbooks on predicting game winners — they have quant teams too. Where it helps:

- **Player props**: Prop lines are softer than game lines. This is where recreational bettors find real edge.
- **Line shopping**: Finding the best available line across books is free money.
- **Discipline**: Seeing "no value tonight" is worth more than a bad bet.
- **Data behind intuition**: If you already have good instincts, this gives you numbers to back them up or challenge them.

## Files

```
run.py              ← run this
pipeline/           ← all the code that fetches data and runs analysis
data/cache/         ← cached stats (auto-managed)
data/nightly/       ← tonight's data
output/             ← generated dashboards (one per day)
docs/methodology.md ← full explanation of the model and its sources
```
