"""
Dashboard generator for NBA Edge.
Reads analysis.json, odds_stake.json, and elo_ratings.json,
then generates a self-contained HTML dashboard at output/YYYY-MM-DD.html.
"""
import json
import os
from datetime import datetime

from cache import load_nightly, load_cached, normalize_abbr, get_today_dir

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


# ── Helpers ────────────────────────────────────────────────────────────

def safe(val, fmt=".1f", fallback="—"):
    """Format a number safely; return fallback if None."""
    if val is None:
        return fallback
    try:
        return f"{val:{fmt}}"
    except (ValueError, TypeError):
        return str(val)


def pct(val, fallback="—"):
    """Format a decimal as a percentage string like '47.8%'."""
    if val is None:
        return fallback
    try:
        return f"{val * 100:.1f}%"
    except (ValueError, TypeError):
        return fallback


def rank_class(rank_str):
    """Return a CSS class based on a rank string like '#4 (top 5)'."""
    if not rank_str:
        return ""
    r = rank_str.lower()
    if "elite" in r or "top 5" in r or "top 3" in r:
        return "rank-top"
    if "bottom 5" in r or "bottom 3" in r or "bottom 10" in r:
        return "rank-bot"
    return ""


def rank_num(rank_str):
    """Extract numeric rank from string like '#4 (top 5)' -> 4."""
    if not rank_str:
        return 16  # middle-of-pack default
    try:
        return int(rank_str.split("#")[1].split(" ")[0])
    except (IndexError, ValueError):
        return 16


def sign(val):
    """Return '+' prefix for positive numbers."""
    if val is None:
        return "—"
    return f"+{val}" if val > 0 else str(val)


def edge_class(edge_pct):
    """Return CSS class if edge is large enough to highlight."""
    if abs(edge_pct) >= 3:
        return "edge-highlight"
    return ""


def match_stake_game(analysis_game, stake_games):
    """
    Find the Stake.com odds game that matches an analysis game.
    Matches on BOTH home and away team names to avoid duplicates
    (e.g. two different Lakers games on the same night).
    """
    home_name = analysis_game["home_profile"]["team_name"]
    away_name = analysis_game["away_profile"]["team_name"]

    for sg in stake_games:
        # Check if the full team names match (or substring match)
        home_match = (home_name in sg["home_team"]) or (sg["home_team"] in home_name)
        away_match = (away_name in sg["away_team"]) or (sg["away_team"] in away_name)
        if home_match and away_match:
            return sg
    return None


def format_tipoff(tipoff_str):
    """Format ISO tipoff to readable time like '9:00 PM ET'."""
    try:
        dt = datetime.fromisoformat(tipoff_str.replace("Z", "+00:00"))
        # Convert UTC to ET (UTC-4 during EDT)
        from datetime import timedelta
        et = dt - timedelta(hours=4)
        return et.strftime("%-I:%M %p ET")
    except Exception:
        return tipoff_str or "TBD"


def flag_icon(flag_type):
    """Return an icon character for each flag type."""
    icons = {
        "four_factors": "&#x25C6;",    # diamond
        "pace": "&#x25B6;",            # play/arrow
        "trend": "&#x2191;",           # up arrow
        "mismatch": "&#x26A0;",        # warning
        "shooting": "&#x25CE;",        # bullseye
        "turnovers": "&#x21BA;",       # cycle arrow
        "identity": "&#x2605;",        # star
    }
    return icons.get(flag_type, "&#x25CF;")  # default: filled circle


def flag_color(flag_type):
    """Return a color for each flag type."""
    colors = {
        "four_factors": "#2A7D6F",
        "pace": "#C8831A",
        "trend": "#D4603A",
        "mismatch": "#D4603A",
        "shooting": "#2A7D6F",
        "turnovers": "#C8831A",
        "identity": "#2A7D6F",
    }
    return colors.get(flag_type, "#7A7570")


# ── Section Builders ───────────────────────────────────────────────────

def build_hero(analysis):
    """Build the dark hero section at the top of the dashboard."""
    date = analysis.get("date", "")
    game_count = analysis.get("game_count", 0)
    games = analysis.get("games", [])

    # Count non-final games
    active_games = [g for g in games if g.get("status") != "Final"]

    # Count total insight flags across all games
    total_flags = sum(len(g.get("matchup", {}).get("flags", [])) for g in games)

    # Count total player props
    total_props = sum(
        len(g.get("statistical_model", {}).get("player_props", []))
        for g in games
    )

    # Count non-neutral prop directions
    actionable_props = 0
    for g in games:
        for prop in g.get("statistical_model", {}).get("player_props", []):
            edge = prop.get("edge", {})
            for d in ["pts_direction", "reb_direction", "ast_direction"]:
                if edge.get(d) in ("OVER", "UNDER"):
                    actionable_props += 1

    # Average model confidence
    confidences = []
    for g in games:
        elo = g.get("elo", {})
        wp = max(elo.get("home_win_prob", 0.5), elo.get("away_win_prob", 0.5))
        confidences.append(wp)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

    return f"""
    <section class="hero">
      <div class="hero-blob blob-1"></div>
      <div class="hero-blob blob-2"></div>
      <div class="hero-blob blob-3"></div>
      <div class="hero-content">
        <p class="eyebrow">NBA EDGE</p>
        <h1>Tonight's <em>Edge</em></h1>
        <p class="hero-date">{date}</p>
        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat-num">{len(active_games)}</span>
            <span class="hero-stat-label">Games Analyzed</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{total_flags}</span>
            <span class="hero-stat-label">Insight Flags</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{actionable_props}</span>
            <span class="hero-stat-label">Actionable Props</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{avg_conf * 100:.0f}%</span>
            <span class="hero-stat-label">Avg Model Confidence</span>
          </div>
        </div>
      </div>
    </section>
    """


def build_game_header(game):
    """Build the dark strip header for a single game."""
    home = game["home_profile"]
    away = game["away_profile"]
    venue = game.get("venue", "")
    tipoff = format_tipoff(game.get("tipoff", ""))

    return f"""
    <div class="game-header">
      <div class="game-header-teams">
        <span class="game-team away-team">{away["team_name"]}</span>
        <span class="game-at">@</span>
        <span class="game-team home-team">{home["team_name"]}</span>
      </div>
      <div class="game-header-meta">
        <span>{away["record"]} vs {home["record"]}</span>
        <span class="meta-sep">|</span>
        <span>{venue}</span>
        <span class="meta-sep">|</span>
        <span>{tipoff}</span>
      </div>
    </div>
    """


def build_win_probability(game):
    """Build the win probability section with Elo, logistic regression, Monte Carlo, Bayesian."""
    elo = game.get("elo", {})
    stat_model = game.get("statistical_model", {})
    lr = stat_model.get("logistic_regression", {})
    mc = stat_model.get("monte_carlo", {})
    bayes = stat_model.get("bayesian_strength", {})
    score_dist = mc.get("score_dist", {})

    home = game["home_profile"]["team_name"].split()[-1]
    away = game["away_profile"]["team_name"].split()[-1]
    home_abbr = game["home_profile"]["abbreviation"]
    away_abbr = game["away_profile"]["abbreviation"]

    # Elo probabilities
    elo_home = elo.get("home_win_prob", 0.5)
    elo_away = elo.get("away_win_prob", 0.5)
    elo_spread = elo.get("projected_spread", 0)

    # Logistic regression
    lr_home = lr.get("home_win_prob", 0.5)
    lr_away = lr.get("away_win_prob", 0.5)
    lr_spread = lr.get("projected_spread", 0)

    # Monte Carlo
    mc_margin = mc.get("mean_margin", 0)
    mc_ci = mc.get("ci_90_margin", [0, 0])
    mc_close = mc.get("prob_close_game", 0)
    mc_blowout_h = mc.get("prob_blowout_home", 0)
    mc_blowout_a = mc.get("prob_blowout_away", 0)
    mc_home_wp = mc.get("simulated_home_win_pct", 0.5)

    # Projected total
    proj_total = score_dist.get("projected_total", 0)
    home_mean_score = score_dist.get("home_mean", 0)
    away_mean_score = score_dist.get("away_mean", 0)

    # Bayesian
    bayes_home = bayes.get("home", {})
    bayes_away = bayes.get("away", {})

    return f"""
    <div class="section-block">
      <h3 class="section-title">Win Probability</h3>
      <div class="prob-grid">

        <!-- Elo Model -->
        <div class="prob-card">
          <p class="prob-label">Elo Model</p>
          <div class="prob-bar-container">
            <div class="prob-bar-away" style="width:{elo_away * 100:.1f}%">
              <span>{away_abbr} {elo_away * 100:.0f}%</span>
            </div>
            <div class="prob-bar-home" style="width:{elo_home * 100:.1f}%">
              <span>{home_abbr} {elo_home * 100:.0f}%</span>
            </div>
          </div>
          <p class="prob-detail">Projected spread: <strong>{away_abbr} {sign(elo_spread)}</strong></p>
        </div>

        <!-- Logistic Regression -->
        <div class="prob-card">
          <p class="prob-label">Logistic Regression</p>
          <div class="prob-bar-container">
            <div class="prob-bar-away" style="width:{lr_away * 100:.1f}%">
              <span>{away_abbr} {lr_away * 100:.0f}%</span>
            </div>
            <div class="prob-bar-home" style="width:{lr_home * 100:.1f}%">
              <span>{home_abbr} {lr_home * 100:.0f}%</span>
            </div>
          </div>
          <p class="prob-detail">Projected spread: <strong>{away_abbr} {sign(lr_spread)}</strong> &middot; {lr.get("features_used", 0)} features</p>
        </div>

        <!-- Monte Carlo -->
        <div class="prob-card">
          <p class="prob-label">Monte Carlo ({mc.get("n_sims", 10000):,} sims)</p>
          <div class="prob-bar-container">
            <div class="prob-bar-away" style="width:{(1 - mc_home_wp) * 100:.1f}%">
              <span>{away_abbr} {(1 - mc_home_wp) * 100:.0f}%</span>
            </div>
            <div class="prob-bar-home" style="width:{mc_home_wp * 100:.1f}%">
              <span>{home_abbr} {mc_home_wp * 100:.0f}%</span>
            </div>
          </div>
          <div class="mc-details">
            <span>Mean margin: <strong>{sign(mc_margin)}</strong></span>
            <span>90% CI: [{safe(mc_ci[0])}, {safe(mc_ci[1])}]</span>
            <span>P(close): {mc_close * 100:.0f}%</span>
            <span>P(blowout {home_abbr}): {mc_blowout_h * 100:.0f}%</span>
            <span>P(blowout {away_abbr}): {mc_blowout_a * 100:.0f}%</span>
          </div>
        </div>

        <!-- Score Projection -->
        <div class="prob-card">
          <p class="prob-label">Score Projection</p>
          <div class="score-proj">
            <span class="score-team">{away_abbr} <strong>{safe(away_mean_score)}</strong></span>
            <span class="score-sep">-</span>
            <span class="score-team">{home_abbr} <strong>{safe(home_mean_score)}</strong></span>
          </div>
          <p class="prob-detail">Projected total: <strong>{safe(proj_total)}</strong></p>
        </div>
      </div>

      <!-- Bayesian Strength -->
      <div class="bayes-row">
        <div class="bayes-card">
          <p class="prob-label">{home_abbr} Bayesian Strength</p>
          <p class="bayes-mean">{sign(bayes_home.get("mean", 0))} <span class="bayes-std">&plusmn; {safe(bayes_home.get("std", 0))}</span></p>
          <p class="prob-detail">Confidence: <strong>{bayes_home.get("confidence", "—")}</strong> &middot; Volatility: {safe(bayes_home.get("volatility", 0))}</p>
        </div>
        <div class="bayes-card">
          <p class="prob-label">{away_abbr} Bayesian Strength</p>
          <p class="bayes-mean">{sign(bayes_away.get("mean", 0))} <span class="bayes-std">&plusmn; {safe(bayes_away.get("std", 0))}</span></p>
          <p class="prob-detail">Confidence: <strong>{bayes_away.get("confidence", "—")}</strong> &middot; Volatility: {safe(bayes_away.get("volatility", 0))}</p>
        </div>
      </div>
    </div>
    """


def build_stake_odds(game, stake_game):
    """Build the Stake.com odds section for a game."""
    if not stake_game:
        return """
        <div class="section-block">
          <h3 class="section-title">Stake.com Odds</h3>
          <p class="no-data">No Stake.com odds data available for this game.</p>
        </div>
        """

    markets = stake_game.get("markets", {})
    elo = game.get("elo", {})

    # Moneyline (can be None even when key exists)
    ml = markets.get("moneyline") or {}
    ml_outcomes = ml.get("outcomes", [])

    # Build moneyline rows
    ml_rows = ""
    for outcome in ml_outcomes:
        name = outcome.get("name", "")
        decimal = outcome.get("odds_decimal", 0)
        american = outcome.get("odds_american", 0)
        implied = outcome.get("implied_prob", 0)

        # Determine if this is home or away for edge calculation
        model_prob = 0
        if any(word in name for word in game["home_profile"]["team_name"].split()):
            model_prob = elo.get("home_win_prob", 0.5)
        else:
            model_prob = elo.get("away_win_prob", 0.5)

        edge = (model_prob - implied) * 100
        edge_cls = "edge-pos" if edge > 3 else ("edge-neg" if edge < -3 else "")
        am_str = f"+{american}" if american > 0 else str(american)

        ml_rows += f"""
        <tr class="{edge_cls}">
          <td>{name}</td>
          <td class="mono">{decimal:.2f}</td>
          <td class="mono">{am_str}</td>
          <td class="mono">{implied * 100:.1f}%</td>
          <td class="mono">{model_prob * 100:.1f}%</td>
          <td class="mono edge-cell {edge_cls}">{sign(round(edge, 1))}%</td>
        </tr>
        """

    # Spreads (show first 3 most relevant)
    spreads = markets.get("spreads", [])
    spread_rows = ""
    for sp in spreads[:4]:
        outcomes = sp.get("outcomes", [])
        for o in outcomes:
            name = o.get("name", "")
            decimal = o.get("odds_decimal", 0)
            american = o.get("odds_american", 0)
            implied = o.get("implied_prob", 0)
            am_str = f"+{american}" if american > 0 else str(american)
            spread_rows += f"""
            <tr>
              <td>{name}</td>
              <td class="mono">{decimal:.2f}</td>
              <td class="mono">{am_str}</td>
              <td class="mono">{implied * 100:.1f}%</td>
            </tr>
            """

    # Totals (show first 3)
    totals = markets.get("totals", [])
    total_rows = ""
    for t in totals[:4]:
        outcomes = t.get("outcomes", [])
        for o in outcomes:
            name = o.get("name", "")
            decimal = o.get("odds_decimal", 0)
            american = o.get("odds_american", 0)
            implied = o.get("implied_prob", 0)
            am_str = f"+{american}" if american > 0 else str(american)
            total_rows += f"""
            <tr>
              <td>{name}</td>
              <td class="mono">{decimal:.2f}</td>
              <td class="mono">{am_str}</td>
              <td class="mono">{implied * 100:.1f}%</td>
            </tr>
            """

    return f"""
    <div class="section-block">
      <h3 class="section-title">Stake.com Odds</h3>

      <div class="odds-grid">
        <div class="odds-table-wrap">
          <p class="odds-subtitle">Moneyline</p>
          <table class="odds-table">
            <thead>
              <tr>
                <th>Team</th><th>Decimal</th><th>American</th>
                <th>Implied %</th><th>Model %</th><th>Edge</th>
              </tr>
            </thead>
            <tbody>{ml_rows}</tbody>
          </table>
        </div>

        <div class="odds-table-wrap">
          <p class="odds-subtitle">Spreads</p>
          <table class="odds-table">
            <thead>
              <tr><th>Line</th><th>Decimal</th><th>American</th><th>Implied %</th></tr>
            </thead>
            <tbody>{spread_rows}</tbody>
          </table>
        </div>

        <div class="odds-table-wrap">
          <p class="odds-subtitle">Totals</p>
          <table class="odds-table">
            <thead>
              <tr><th>Line</th><th>Decimal</th><th>American</th><th>Implied %</th></tr>
            </thead>
            <tbody>{total_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
    """


def build_team_comparison(game):
    """Build a side-by-side stat comparison table for home and away teams."""
    home = game["home_profile"]
    away = game["away_profile"]
    home_abbr = home["abbreviation"]
    away_abbr = away["abbreviation"]
    ho = home["offense"]
    hd = home["defense"]
    ao = away["offense"]
    ad = away["defense"]

    # Each row: (label, away_val, away_rank, home_val, home_rank, format_fn)
    rows_data = [
        ("ORTG", ao["rating"], ao["rank"], ho["rating"], ho["rank"], safe),
        ("DRTG", ad["rating"], ad["rank"], hd["rating"], hd["rank"], safe),
        ("Net Rating", away["net_rating"], away["net_rating_rank"],
         home["net_rating"], home["net_rating_rank"], lambda v: sign(v)),
        ("PPG", ao["ppg"], ao["ppg_rank"], ho["ppg"], ho["ppg_rank"], safe),
        ("FG%", ao["fg_pct"], None, ho["fg_pct"], None, pct),
        ("3PT%", ao["fg3_pct"], None, ho["fg3_pct"], None, pct),
        ("FT%", ao["ft_pct"], None, ho["ft_pct"], None, pct),
        ("TS%", ao["ts_pct"], ao["ts_rank"], ho["ts_pct"], ho["ts_rank"], pct),
        ("eFG%", ao["efg_pct"], ao["efg_rank"], ho["efg_pct"], ho["efg_rank"], pct),
        ("APG", ao["apg"], ao["apg_rank"], ho["apg"], ho["apg_rank"], safe),
        ("TOV/g", ao["tov_pg"], ao["tov_rank"], ho["tov_pg"], ho["tov_rank"], safe),
        ("OREB%", ao["oreb_pct"], ao["oreb_rank"], ho["oreb_pct"], ho["oreb_rank"], pct),
        ("Pace", ao["pace"], ao["pace_rank"], ho["pace"], ho["pace_rank"], safe),
        ("SPG", ad["spg"], ad["spg_rank"], hd["spg"], hd["spg_rank"], safe),
        ("BPG", ad["bpg"], ad["bpg_rank"], hd["bpg"], hd["bpg_rank"], safe),
        ("DREB%", ad["dreb_pct"], ad["dreb_rank"], hd["dreb_pct"], hd["dreb_rank"], pct),
    ]

    rows = ""
    for label, a_val, a_rank, h_val, h_rank, fmt_fn in rows_data:
        a_cls = rank_class(a_rank) if a_rank else ""
        h_cls = rank_class(h_rank) if h_rank else ""
        a_rank_str = f'<span class="rank-tag">{a_rank}</span>' if a_rank else ""
        h_rank_str = f'<span class="rank-tag">{h_rank}</span>' if h_rank else ""

        rows += f"""
        <tr>
          <td class="comp-val {a_cls}">{fmt_fn(a_val)} {a_rank_str}</td>
          <td class="comp-label">{label}</td>
          <td class="comp-val {h_cls}">{fmt_fn(h_val)} {h_rank_str}</td>
        </tr>
        """

    return f"""
    <div class="section-block">
      <h3 class="section-title">Team Comparison</h3>
      <table class="comp-table">
        <thead>
          <tr>
            <th class="comp-th-team">{away_abbr}</th>
            <th class="comp-th-stat">Stat</th>
            <th class="comp-th-team">{home_abbr}</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


def build_four_factors(game):
    """Build the Four Factors matchup section."""
    ff = game.get("matchup", {}).get("four_factors", {})
    if not ff:
        return ""

    team_a = ff.get("team_a", "AWAY")
    team_b = ff.get("team_b", "HOME")
    grade = ff.get("grade", "—")
    grade_favors = ff.get("grade_favors", "")
    details = ff.get("details", {})

    # Build rows for each matchup direction
    def factor_rows(matchup_data, off_team, def_team, off_key="a_offense", def_key="b_defense"):
        rows = ""
        factor_names = {"efg": "eFG%", "tov": "TOV%", "oreb": "OREB%", "ft_rate": "FT Rate"}
        for key, label in factor_names.items():
            f = matchup_data.get(key, {})
            off_val = f.get(off_key, f.get("b_offense", 0))
            def_val = f.get(def_key, f.get("a_defense", 0))
            edge = f.get("edge", 0)
            weight = f.get("weight", 0)
            edge_sign = "+" if edge > 0 else ""
            rows += f"""
            <tr>
              <td>{label}</td>
              <td class="mono">{pct(off_val)}</td>
              <td class="mono">{pct(def_val)}</td>
              <td class="mono">{edge_sign}{edge * 100:.1f}%</td>
              <td class="mono">{weight * 100:.0f}%</td>
            </tr>
            """
        return rows

    # First direction: team_a offense vs team_b defense
    key_a = f"{team_a}_offense_vs_{team_b}_defense"
    data_a = details.get(key_a, {})

    # Second direction: team_b offense vs team_a defense
    key_b = f"{team_b}_offense_vs_{team_a}_defense"
    data_b = details.get(key_b, {})

    a_score = ff.get("a_offensive_score", 0)
    b_score = ff.get("b_offensive_score", 0)
    net_adv = ff.get("net_advantage", 0)

    return f"""
    <div class="section-block">
      <h3 class="section-title">Four Factors Matchup</h3>
      <div class="ff-summary">
        <span class="ff-grade">Grade: <strong>{grade}</strong></span>
        <span class="ff-favors">Favors: <strong>{grade_favors}</strong></span>
        <span class="ff-scores">{team_a} off score: {a_score:.4f} &middot; {team_b} off score: {b_score:.4f}</span>
      </div>

      <div class="ff-tables">
        <div class="ff-table-wrap">
          <p class="odds-subtitle">{team_a} Offense vs {team_b} Defense</p>
          <table class="odds-table">
            <thead>
              <tr><th>Factor</th><th>Offense</th><th>Defense</th><th>Edge</th><th>Weight</th></tr>
            </thead>
            <tbody>{factor_rows(data_a, team_a, team_b)}</tbody>
          </table>
        </div>
        <div class="ff-table-wrap">
          <p class="odds-subtitle">{team_b} Offense vs {team_a} Defense</p>
          <table class="odds-table">
            <thead>
              <tr><th>Factor</th><th>Offense</th><th>Defense</th><th>Edge</th><th>Weight</th></tr>
            </thead>
            <tbody>{factor_rows(data_b, team_b, team_a, "b_offense", "a_defense")}</tbody>
          </table>
        </div>
      </div>
    </div>
    """


def build_flags(game):
    """Build insight flags section with colored callout boxes."""
    flags = game.get("matchup", {}).get("flags", [])
    if not flags:
        return ""

    flag_html = ""
    for f in flags:
        ftype = f.get("type", "")
        text = f.get("text", "")
        color = flag_color(ftype)
        icon = flag_icon(ftype)
        flag_html += f"""
        <div class="flag-box" style="border-left-color:{color}">
          <span class="flag-icon" style="color:{color}">{icon}</span>
          <span class="flag-text">{text}</span>
          <span class="flag-type" style="color:{color}">{ftype.upper()}</span>
        </div>
        """

    return f"""
    <div class="section-block">
      <h3 class="section-title">Insight Flags</h3>
      <div class="flags-container">{flag_html}</div>
    </div>
    """


def build_player_props(game):
    """Build the player props section -- the most important section."""
    props = game.get("statistical_model", {}).get("player_props", [])
    if not props:
        return ""

    home_abbr = game["home_profile"]["abbreviation"]
    away_abbr = game["away_profile"]["abbreviation"]

    rows = ""
    for p in props:
        name = p.get("name", "")
        team = p.get("team", "")
        avg = p.get("season_avg", {})
        proj = p.get("projected", {})
        edge = p.get("edge", {})
        conf = p.get("confidence", {})
        ctx = p.get("matchup_context", {})

        pts_dir = edge.get("pts_direction", "NEUTRAL")
        reb_dir = edge.get("reb_direction", "NEUTRAL")
        ast_dir = edge.get("ast_direction", "NEUTRAL")

        # Highlight class for actionable directions
        pts_cls = "dir-over" if pts_dir == "OVER" else ("dir-under" if pts_dir == "UNDER" else "dir-neutral")
        reb_cls = "dir-over" if reb_dir == "OVER" else ("dir-under" if reb_dir == "UNDER" else "dir-neutral")
        ast_cls = "dir-over" if ast_dir == "OVER" else ("dir-under" if ast_dir == "UNDER" else "dir-neutral")

        # Row highlight if any prop is actionable
        row_cls = "prop-actionable" if any(
            d in ("OVER", "UNDER")
            for d in [pts_dir, reb_dir, ast_dir]
        ) else ""

        opp_rank = ctx.get("opp_ppg_rank", "")
        multiplier = ctx.get("scoring_multiplier", 1.0)

        rows += f"""
        <tr class="{row_cls}">
          <td class="prop-name">
            <strong>{name}</strong>
            <span class="prop-team">{team}</span>
          </td>
          <td class="mono">{safe(avg.get('ppg'))}</td>
          <td class="mono"><strong>{safe(proj.get('ppg'))}</strong></td>
          <td class="mono {pts_cls}">{sign(edge.get('pts', 0))}</td>
          <td class="{pts_cls}">{pts_dir}</td>
          <td class="mono">{safe(avg.get('rpg'))}</td>
          <td class="mono"><strong>{safe(proj.get('rpg'))}</strong></td>
          <td class="mono {reb_cls}">{sign(edge.get('reb', 0))}</td>
          <td class="{reb_cls}">{reb_dir}</td>
          <td class="mono">{safe(avg.get('apg'))}</td>
          <td class="mono"><strong>{safe(proj.get('apg'))}</strong></td>
          <td class="mono {ast_cls}">{sign(edge.get('ast', 0))}</td>
          <td class="{ast_cls}">{ast_dir}</td>
          <td class="mono">{multiplier:.2f}x</td>
        </tr>
        """

    return f"""
    <div class="section-block props-section">
      <h3 class="section-title">Player Props <span class="section-badge">KEY SECTION</span></h3>
      <div class="props-table-wrap">
        <table class="props-table">
          <thead>
            <tr>
              <th>Player</th>
              <th colspan="4" class="group-header">Points</th>
              <th colspan="4" class="group-header">Rebounds</th>
              <th colspan="4" class="group-header">Assists</th>
              <th>Mult</th>
            </tr>
            <tr class="sub-header">
              <th></th>
              <th>Avg</th><th>Proj</th><th>Edge</th><th>Dir</th>
              <th>Avg</th><th>Proj</th><th>Edge</th><th>Dir</th>
              <th>Avg</th><th>Proj</th><th>Edge</th><th>Dir</th>
              <th></th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>
    """


def build_recent_form(game):
    """Build the recent form section showing L5 and L10 records."""
    rf = game.get("matchup", {}).get("recent_form", {})
    if not rf:
        return ""

    home_abbr = game["home_profile"]["abbreviation"]
    away_abbr = game["away_profile"]["abbreviation"]

    return f"""
    <div class="section-block">
      <h3 class="section-title">Recent Form</h3>
      <div class="form-grid">
        <div class="form-card">
          <p class="form-team">{away_abbr}</p>
          <div class="form-stats">
            <div class="form-stat">
              <span class="form-label">L5</span>
              <span class="form-val">{rf.get("away_last_5", "—")}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L10</span>
              <span class="form-val">{rf.get("away_last_10", "—")}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L5 Net</span>
              <span class="form-val">{sign(rf.get("away_l5_net", 0))}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L10 Net</span>
              <span class="form-val">{sign(rf.get("away_l10_net", 0))}</span>
            </div>
          </div>
          <p class="form-trend">{rf.get("away_trending", "")}</p>
        </div>
        <div class="form-card">
          <p class="form-team">{home_abbr}</p>
          <div class="form-stats">
            <div class="form-stat">
              <span class="form-label">L5</span>
              <span class="form-val">{rf.get("home_last_5", "—")}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L10</span>
              <span class="form-val">{rf.get("home_last_10", "—")}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L5 Net</span>
              <span class="form-val">{sign(rf.get("home_l5_net", 0))}</span>
            </div>
            <div class="form-stat">
              <span class="form-label">L10 Net</span>
              <span class="form-val">{sign(rf.get("home_l10_net", 0))}</span>
            </div>
          </div>
          <p class="form-trend">{rf.get("home_trending", "")}</p>
        </div>
      </div>
    </div>
    """


def build_elo_chart(elo_ratings):
    """Build the Elo Power Rankings bar chart section using Chart.js."""
    if not elo_ratings:
        return ""

    # Sort teams by Elo descending
    sorted_teams = sorted(elo_ratings.items(), key=lambda x: x[1], reverse=True)
    labels = [t[0] for t in sorted_teams]
    values = [t[1] for t in sorted_teams]

    # Color: top 5 teal, bottom 5 coral, rest amber
    colors = []
    for i in range(len(sorted_teams)):
        if i < 5:
            colors.append("#2A7D6F")
        elif i >= len(sorted_teams) - 5:
            colors.append("#D4603A")
        else:
            colors.append("#C8831A")

    labels_json = json.dumps(labels)
    values_json = json.dumps(values)
    colors_json = json.dumps(colors)

    return f"""
    <section class="elo-section">
      <div class="container">
        <p class="section-eyebrow">POWER RANKINGS</p>
        <h2 class="section-heading">Elo Ratings</h2>
        <div class="elo-chart-wrap">
          <canvas id="eloChart"></canvas>
        </div>
      </div>
    </section>

    <script>
    (function() {{
      const ctx = document.getElementById('eloChart').getContext('2d');
      new Chart(ctx, {{
        type: 'bar',
        data: {{
          labels: {labels_json},
          datasets: [{{
            label: 'Elo Rating',
            data: {values_json},
            backgroundColor: {colors_json},
            borderColor: 'transparent',
            borderRadius: 4,
            barThickness: 20
          }}]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              backgroundColor: '#0F0F0F',
              titleFont: {{ family: 'DM Sans', size: 13 }},
              bodyFont: {{ family: 'DM Mono', size: 12 }},
              padding: 12,
              cornerRadius: 6
            }}
          }},
          scales: {{
            x: {{
              min: 1100,
              max: 1850,
              grid: {{ color: '#E2DDD5', lineWidth: 0.5 }},
              ticks: {{
                font: {{ family: 'DM Mono', size: 11 }},
                color: '#7A7570'
              }}
            }},
            y: {{
              grid: {{ display: false }},
              ticks: {{
                font: {{ family: 'DM Mono', size: 11, weight: 500 }},
                color: '#1A1A1A'
              }}
            }}
          }}
        }}
      }});
    }})();
    </script>
    """


def build_footer(analysis):
    """Build the dark footer."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    model_info = analysis.get("model_info", {})
    layers = model_info.get("layers", [])

    layers_html = ""
    for layer in layers[:5]:
        layers_html += f"<li>{layer}</li>"

    return f"""
    <footer class="footer">
      <div class="container">
        <div class="footer-grid">
          <div class="footer-col">
            <p class="footer-heading">NBA EDGE</p>
            <p class="footer-text">Quantitative NBA analysis. Not financial advice.
            All model outputs are probabilistic estimates.</p>
          </div>
          <div class="footer-col">
            <p class="footer-heading">Sources</p>
            <ul class="footer-list">
              <li>NBA.com / nba_api</li>
              <li>Stake.com (odds)</li>
              <li>Custom Elo model</li>
              <li>Logistic regression + Monte Carlo</li>
            </ul>
          </div>
          <div class="footer-col">
            <p class="footer-heading">Model Layers</p>
            <ul class="footer-list">{layers_html}</ul>
          </div>
        </div>
        <div class="footer-bottom">
          <p>Generated {now} &middot; {model_info.get("dimensions_per_game", "40+")} dimensions per game</p>
          <p class="footer-disclaimer">For informational purposes only. Past performance does not guarantee future results.</p>
        </div>
      </div>
    </footer>
    """


# ── CSS ────────────────────────────────────────────────────────────────

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'DM Sans', -apple-system, sans-serif;
  background: #FAF7F2;
  color: #1A1A1A;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.container { max-width: 1100px; margin: 0 auto; padding: 0 24px; }

/* ── Hero ── */
.hero {
  background: #0F0F0F;
  color: #FAF7F2;
  padding: 80px 24px 60px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.hero-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  pointer-events: none;
}
.blob-1 { width: 400px; height: 400px; background: #D4603A; top: -100px; left: -100px; }
.blob-2 { width: 300px; height: 300px; background: #2A7D6F; bottom: -80px; right: -80px; }
.blob-3 { width: 200px; height: 200px; background: #C8831A; top: 50%; left: 60%; }
.hero-content { position: relative; z-index: 1; }
.eyebrow {
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #D4603A;
  margin-bottom: 12px;
}
.hero h1 {
  font-family: 'Playfair Display', serif;
  font-size: 56px;
  font-weight: 700;
  margin-bottom: 8px;
  line-height: 1.1;
}
.hero h1 em {
  color: #E8825F;
  font-style: italic;
}
.hero-date {
  font-family: 'DM Mono', monospace;
  font-size: 15px;
  color: #7A7570;
  margin-bottom: 36px;
}
.hero-stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  flex-wrap: wrap;
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.hero-stat-num {
  font-family: 'DM Mono', monospace;
  font-size: 32px;
  font-weight: 500;
  color: #FAF7F2;
}
.hero-stat-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #7A7570;
  margin-top: 4px;
}

/* ── Game Sections ── */
.game-section {
  margin: 40px auto;
  max-width: 1100px;
  padding: 0 24px;
}
.game-header {
  background: #0F0F0F;
  color: #FAF7F2;
  padding: 24px 32px;
  border-radius: 12px 12px 0 0;
}
.game-header-teams {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-family: 'Playfair Display', serif;
  font-size: 28px;
  font-weight: 700;
}
.game-at {
  font-family: 'DM Mono', monospace;
  font-size: 16px;
  color: #7A7570;
}
.game-header-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  color: #7A7570;
}
.meta-sep { opacity: 0.4; }

.game-body {
  background: #fff;
  border: 1px solid #E2DDD5;
  border-top: none;
  border-radius: 0 0 12px 12px;
  padding: 32px;
}

/* ── Section Blocks ── */
.section-block {
  margin-bottom: 32px;
  padding-bottom: 32px;
  border-bottom: 1px solid #E2DDD5;
}
.section-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.section-title {
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 16px;
  color: #1A1A1A;
}
.section-badge {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 1.5px;
  background: #D4603A;
  color: #fff;
  padding: 3px 8px;
  border-radius: 4px;
  vertical-align: middle;
  margin-left: 8px;
}
.section-eyebrow {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #D4603A;
  margin-bottom: 8px;
}
.section-heading {
  font-family: 'Playfair Display', serif;
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 24px;
}

/* ── Probability bars ── */
.prob-grid { display: flex; flex-direction: column; gap: 16px; }
.prob-card {
  background: #FAF7F2;
  border: 1px solid #E2DDD5;
  border-radius: 8px;
  padding: 16px;
}
.prob-label {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #7A7570;
  margin-bottom: 8px;
}
.prob-bar-container {
  display: flex;
  height: 36px;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 8px;
}
.prob-bar-away {
  background: #D4603A;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  transition: width 0.5s ease;
}
.prob-bar-home {
  background: #2A7D6F;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  transition: width 0.5s ease;
}
.prob-bar-away span, .prob-bar-home span {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #fff;
  font-weight: 500;
  white-space: nowrap;
}
.prob-detail {
  font-size: 13px;
  color: #7A7570;
}
.mc-details {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  font-family: 'DM Mono', monospace;
  color: #7A7570;
}
.score-proj {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  font-family: 'DM Mono', monospace;
  font-size: 24px;
  color: #1A1A1A;
  padding: 8px 0;
}
.score-sep { color: #7A7570; font-size: 18px; }
.score-team strong { font-size: 28px; }

/* Bayesian */
.bayes-row { display: flex; gap: 16px; margin-top: 16px; }
.bayes-card {
  flex: 1;
  background: #FAF7F2;
  border: 1px solid #E2DDD5;
  border-radius: 8px;
  padding: 16px;
}
.bayes-mean {
  font-family: 'DM Mono', monospace;
  font-size: 28px;
  font-weight: 500;
  color: #1A1A1A;
  margin: 4px 0;
}
.bayes-std {
  font-size: 16px;
  color: #7A7570;
}

/* ── Comparison Table ── */
.comp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.comp-table th {
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #7A7570;
  padding: 8px 12px;
  border-bottom: 2px solid #E2DDD5;
}
.comp-th-team { width: 40%; }
.comp-th-stat { width: 20%; text-align: center; }
.comp-table td { padding: 10px 12px; border-bottom: 1px solid #E2DDD5; }
.comp-label {
  text-align: center;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #7A7570;
}
.comp-val {
  font-family: 'DM Mono', monospace;
  font-size: 14px;
}
.comp-val:first-child { text-align: right; }
.comp-val:last-child { text-align: left; }
.rank-tag {
  font-size: 10px;
  color: #7A7570;
  margin-left: 4px;
}
.rank-top { background: rgba(42, 125, 111, 0.1); }
.rank-bot { background: rgba(212, 96, 58, 0.1); }

/* ── Odds Tables ── */
.odds-grid { display: flex; flex-direction: column; gap: 20px; }
.odds-subtitle {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #7A7570;
  margin-bottom: 8px;
}
.odds-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.odds-table th {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #7A7570;
  padding: 6px 10px;
  border-bottom: 2px solid #E2DDD5;
  text-align: left;
}
.odds-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #E2DDD5;
}
.mono { font-family: 'DM Mono', monospace; }
.edge-pos { background: rgba(42, 125, 111, 0.12); }
.edge-neg { background: rgba(212, 96, 58, 0.08); }
.edge-cell { font-weight: 600; }
.no-data { color: #7A7570; font-style: italic; padding: 16px 0; }

/* ── Four Factors ── */
.ff-summary {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  font-size: 14px;
  color: #7A7570;
}
.ff-grade { font-size: 16px; color: #1A1A1A; }
.ff-tables { display: flex; gap: 20px; flex-wrap: wrap; }
.ff-table-wrap { flex: 1; min-width: 280px; }

/* ── Flags ── */
.flags-container { display: flex; flex-direction: column; gap: 10px; }
.flag-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #FAF7F2;
  border-left: 4px solid;
  border-radius: 0 8px 8px 0;
}
.flag-icon { font-size: 18px; flex-shrink: 0; }
.flag-text { flex: 1; font-size: 14px; }
.flag-type {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 1px;
  flex-shrink: 0;
}

/* ── Player Props ── */
.props-section { overflow-x: auto; }
.props-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.props-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 900px;
}
.props-table th {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #7A7570;
  padding: 6px 8px;
  border-bottom: 2px solid #E2DDD5;
  text-align: center;
}
.props-table .sub-header th {
  border-bottom: 1px solid #E2DDD5;
  font-size: 10px;
}
.group-header {
  border-bottom: 2px solid #1A1A1A !important;
  font-size: 12px !important;
  color: #1A1A1A !important;
}
.props-table td {
  padding: 8px 8px;
  border-bottom: 1px solid #E2DDD5;
  text-align: center;
}
.prop-name {
  text-align: left !important;
  white-space: nowrap;
}
.prop-team {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #7A7570;
  margin-left: 6px;
}
.prop-actionable { background: rgba(42, 125, 111, 0.05); }
.dir-over { color: #2A7D6F; font-weight: 600; }
.dir-under { color: #D4603A; font-weight: 600; }
.dir-neutral { color: #7A7570; }

/* ── Recent Form ── */
.form-grid { display: flex; gap: 16px; }
.form-card {
  flex: 1;
  background: #FAF7F2;
  border: 1px solid #E2DDD5;
  border-radius: 8px;
  padding: 16px;
}
.form-team {
  font-family: 'DM Mono', monospace;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  letter-spacing: 1px;
}
.form-stats { display: flex; gap: 16px; flex-wrap: wrap; }
.form-stat { display: flex; flex-direction: column; }
.form-label {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #7A7570;
}
.form-val {
  font-family: 'DM Mono', monospace;
  font-size: 18px;
  font-weight: 500;
}
.form-trend {
  font-size: 13px;
  color: #7A7570;
  margin-top: 8px;
  font-style: italic;
}

/* ── Elo Chart ── */
.elo-section {
  background: #fff;
  border-top: 1px solid #E2DDD5;
  border-bottom: 1px solid #E2DDD5;
  padding: 48px 24px;
  margin: 40px 0;
}
.elo-chart-wrap {
  height: 750px;
  position: relative;
}

/* ── Footer ── */
.footer {
  background: #0F0F0F;
  color: #FAF7F2;
  padding: 48px 24px 32px;
}
.footer-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
  margin-bottom: 32px;
}
.footer-heading {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #D4603A;
  margin-bottom: 12px;
}
.footer-text { font-size: 13px; color: #7A7570; line-height: 1.6; }
.footer-list { list-style: none; }
.footer-list li {
  font-size: 13px;
  color: #7A7570;
  padding: 2px 0;
}
.footer-bottom {
  border-top: 1px solid rgba(255,255,255,0.1);
  padding-top: 20px;
  text-align: center;
}
.footer-bottom p {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #7A7570;
}
.footer-disclaimer { margin-top: 8px; font-style: italic; }

/* ── Responsive ── */
@media (max-width: 768px) {
  .hero h1 { font-size: 36px; }
  .hero-stats { gap: 20px; }
  .game-header-teams { font-size: 20px; }
  .bayes-row { flex-direction: column; }
  .form-grid { flex-direction: column; }
  .ff-tables { flex-direction: column; }
  .footer-grid { grid-template-columns: 1fr; }
  .comp-table { font-size: 12px; }
}
"""


# ── Main Generator ─────────────────────────────────────────────────────

def generate_dashboard():
    """
    Read analysis.json, odds_stake.json, and elo_ratings.json,
    then generate a self-contained HTML dashboard.
    Returns the filepath to the generated HTML file.
    """
    # Load data
    analysis = load_nightly("analysis.json")
    if not analysis:
        print("  ERROR: No analysis.json found for today.")
        return None

    odds_stake = load_nightly("odds_stake.json")
    stake_games = odds_stake.get("games", []) if odds_stake else []

    elo_ratings = load_cached("elo_ratings")
    if not elo_ratings:
        elo_ratings = {}

    date = analysis.get("date", datetime.now().strftime("%Y-%m-%d"))
    games = analysis.get("games", [])

    # Count Stake lines
    stake_line_count = 0
    for sg in stake_games:
        for mkt_key, mkt_val in sg.get("markets", {}).items():
            if isinstance(mkt_val, list):
                stake_line_count += len(mkt_val)
            elif isinstance(mkt_val, dict):
                stake_line_count += 1

    # ── Build HTML sections ──

    hero_html = build_hero(analysis)

    games_html = ""
    for game in games:
        # Match this game to Stake odds
        stake_game = match_stake_game(game, stake_games)

        games_html += f"""
        <div class="game-section">
          {build_game_header(game)}
          <div class="game-body">
            {build_win_probability(game)}
            {build_stake_odds(game, stake_game)}
            {build_team_comparison(game)}
            {build_four_factors(game)}
            {build_flags(game)}
            {build_player_props(game)}
            {build_recent_form(game)}
          </div>
        </div>
        """

    elo_html = build_elo_chart(elo_ratings)
    footer_html = build_footer(analysis)

    # ── Assemble full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NBA Edge - {date}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>{CSS}</style>
</head>
<body>
  {hero_html}
  {games_html}
  {elo_html}
  {footer_html}
</body>
</html>"""

    # ── Write file ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{date}.html")
    with open(filepath, "w") as f:
        f.write(html)

    print(f"  Dashboard generated: {filepath}")
    return filepath


if __name__ == "__main__":
    path = generate_dashboard()
    if path:
        print(f"\n  Open: file://{os.path.abspath(path)}")
