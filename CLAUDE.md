# NBA Edge — Claude Code Workflow

## What This Is
NBA sports betting analytics tool. Python pipeline fetches data, Claude agents analyze it, produces an HTML dashboard with ~12 nightly picks.

## How to Run

When user says "run tonight", "run the analysis", "what's good tonight", or similar:

### Step 1: Run the data pipeline
```bash
cd ~/Desktop/nba-edge/pipeline
python3 fetch_schedule.py
python3 fetch_stats.py
python3 fetch_odds.py
python3 crunch.py
```

Run these sequentially. fetch_stats.py is cache-aware — it skips if data is fresh (<12h old). fetch_schedule.py and fetch_odds.py always fetch fresh data.

If fetch_odds.py warns about missing API key, tell the user to sign up at the-odds-api.com (free) and add the key to .env.

### Step 2: Launch 3 analysis agents in parallel

Read `data/nightly/YYYY-MM-DD/analysis.json` (today's date). Then launch these agents simultaneously:

**Agent 1 — Matchup Analyst:**
Read the analysis.json, team_stats from cache, and player_stats from cache. For each game tonight, write a narrative matchup analysis: which team has the statistical edge and why, key player advantages, pace/style implications, Four Factors breakdown. Save to `data/nightly/YYYY-MM-DD/insights/matchups.md`.

**Agent 2 — Odds & Value Analyst:**
Read analysis.json and the odds.json. For each pick in the analysis, explain WHY the model disagrees with the market. Identify the sharpest line shopping opportunities. Flag any suspicious odds movement. Save to `data/nightly/YYYY-MM-DD/insights/odds_value.md`.

**Agent 3 — Context & News:**
Do web searches for each team playing tonight: injuries, lineup changes, rest situations, recent news, playoff/tanking implications. Look for factors the quantitative model can't capture. Save to `data/nightly/YYYY-MM-DD/insights/context.md`.

### Step 3: Generate the HTML dashboard

Read ALL of these files:
- `data/nightly/YYYY-MM-DD/analysis.json`
- `data/nightly/YYYY-MM-DD/insights/matchups.md`
- `data/nightly/YYYY-MM-DD/insights/odds_value.md`
- `data/nightly/YYYY-MM-DD/insights/context.md`

Generate `output/YYYY-MM-DD.html` — a single-file HTML dashboard following the design system below.

## Dashboard Design System

**Fonts** (from Google Fonts):
- Playfair Display — headings
- DM Sans — body text
- DM Mono — numbers, labels, section eyebrows

**Colors:**
- Page bg: #FAF7F2 (cream)
- Dark sections: #0F0F0F
- Primary text: #1A1A1A
- Coral (warning/negative): #D4603A
- Teal (positive): #2A7D6F
- Amber (secondary): #C8831A
- Muted: #7A7570
- Border: #E2DDD5

**Chart.js** from CDN: https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js
- Teal for positive/series 1, Amber for series 2, Coral for negative

**Dashboard sections:**
1. **Dark hero** — date, game count, headline summary of picks
2. **The Picks (~12)** — tiered: Strong Plays, Leans, Fades. Each card shows: the bet, the book, confidence, edge %, one-line rationale
3. **Per-game breakdowns** — matchup grades, stat comparisons, odds across books, Claude's qualitative paragraph
4. **Line shopping table** — best available lines across all books
5. **Model Transparency** — Elo ratings, Four Factors grades, adjustments applied
6. **Footer** — sources, timestamp, disclaimer

## Model Reference
See `docs/methodology.md` for the full 6-layer model explanation.

## Key Files
- `pipeline/` — all data fetching and analysis scripts
- `data/cache/` — persistent cached data (stats, Elo ratings)
- `data/nightly/YYYY-MM-DD/` — tonight's data
- `output/YYYY-MM-DD.html` — tonight's dashboard
- `docs/methodology.md` — model methodology and sources
