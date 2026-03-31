"""
Four Factors matchup analysis (Dean Oliver framework).
Explains 91.4% of win variation in the NBA.

The Four Factors (with weights):
  1. eFG% — Effective Field Goal %  (40%)
  2. TOV% — Turnover Rate           (25%)
  3. OREB% — Offensive Rebound Rate  (20%)
  4. FTRate — Free Throw Rate        (15%)

For each matchup, we compare Team A's offensive factors
against Team B's defensive factors (and vice versa).
"""
from cache import load_cached

# Oliver's weights
WEIGHTS = {
    "efg": 0.40,
    "tov": 0.25,
    "oreb": 0.20,
    "ft_rate": 0.15,
}


def get_league_averages(team_stats):
    """Calculate league averages for each Four Factor to use as baselines."""
    factors = ["efg_pct", "tm_tov_pct", "oreb_pct", "fta_rate",
               "opp_efg_pct", "opp_tov_pct", "opp_oreb_pct", "opp_fta_rate"]
    avgs = {}
    teams = list(team_stats.values())
    for f in factors:
        vals = [t["four_factors"][f] for t in teams if t.get("four_factors", {}).get(f) is not None]
        avgs[f] = sum(vals) / len(vals) if vals else 0
    return avgs


def analyze_matchup(team_a_abbr, team_b_abbr, team_stats):
    """
    Analyze the Four Factors matchup between two teams.
    Returns matchup grades and specific advantage flags.

    team_a is the team we're evaluating the offense of (vs team_b's defense),
    and vice versa.
    """
    a = team_stats.get(team_a_abbr, {}).get("four_factors", {})
    b = team_stats.get(team_b_abbr, {}).get("four_factors", {})

    if not a or not b:
        return {"error": "Four Factors data not available for one or both teams"}

    league_avgs = get_league_averages(team_stats)

    # Team A offense vs Team B defense
    # positive = advantage for Team A's offense
    a_off_advantages = {
        "efg": {
            "a_offense": a.get("efg_pct", 0),
            "b_defense": b.get("opp_efg_pct", 0),
            "edge": (a.get("efg_pct", 0) or 0) - (b.get("opp_efg_pct", 0) or 0),
            "weight": WEIGHTS["efg"],
        },
        "tov": {
            "a_offense": a.get("tm_tov_pct", 0),
            "b_defense": b.get("opp_tov_pct", 0),
            # lower TOV% is better for offense, so flip the sign
            "edge": (b.get("opp_tov_pct", 0) or 0) - (a.get("tm_tov_pct", 0) or 0),
            "weight": WEIGHTS["tov"],
        },
        "oreb": {
            "a_offense": a.get("oreb_pct", 0),
            "b_defense": b.get("opp_oreb_pct", 0),
            "edge": (a.get("oreb_pct", 0) or 0) - (b.get("opp_oreb_pct", 0) or 0),
            "weight": WEIGHTS["oreb"],
        },
        "ft_rate": {
            "a_offense": a.get("fta_rate", 0),
            "b_defense": b.get("opp_fta_rate", 0),
            "edge": (a.get("fta_rate", 0) or 0) - (b.get("opp_fta_rate", 0) or 0),
            "weight": WEIGHTS["ft_rate"],
        },
    }

    # Team B offense vs Team A defense (same structure, reversed)
    b_off_advantages = {
        "efg": {
            "b_offense": b.get("efg_pct", 0),
            "a_defense": a.get("opp_efg_pct", 0),
            "edge": (b.get("efg_pct", 0) or 0) - (a.get("opp_efg_pct", 0) or 0),
            "weight": WEIGHTS["efg"],
        },
        "tov": {
            "b_offense": b.get("tm_tov_pct", 0),
            "a_defense": a.get("opp_tov_pct", 0),
            "edge": (a.get("opp_tov_pct", 0) or 0) - (b.get("tm_tov_pct", 0) or 0),
            "weight": WEIGHTS["tov"],
        },
        "oreb": {
            "b_offense": b.get("oreb_pct", 0),
            "a_defense": a.get("opp_oreb_pct", 0),
            "edge": (b.get("oreb_pct", 0) or 0) - (a.get("opp_oreb_pct", 0) or 0),
            "weight": WEIGHTS["oreb"],
        },
        "ft_rate": {
            "b_offense": b.get("fta_rate", 0),
            "a_defense": a.get("opp_fta_rate", 0),
            "edge": (b.get("fta_rate", 0) or 0) - (a.get("opp_fta_rate", 0) or 0),
            "weight": WEIGHTS["ft_rate"],
        },
    }

    # compute weighted matchup scores
    a_score = sum(v["edge"] * v["weight"] for v in a_off_advantages.values())
    b_score = sum(v["edge"] * v["weight"] for v in b_off_advantages.values())

    # net matchup advantage (positive = favors team_a)
    net_advantage = a_score - b_score

    # generate advantage flags (what to call out in the dashboard)
    flags = []
    for factor_name, data in a_off_advantages.items():
        if abs(data["edge"]) > 0.02:  # >2% gap = notable
            side = team_a_abbr if data["edge"] > 0 else team_b_abbr
            factor_label = {"efg": "shooting efficiency", "tov": "ball security",
                           "oreb": "offensive rebounding", "ft_rate": "getting to the line"}[factor_name]
            flags.append(f"{side} has a {abs(data['edge'])*100:.1f}% edge in {factor_label}")

    # letter grade based on net advantage
    if abs(net_advantage) < 0.005:
        grade = "C"  # even
    elif net_advantage > 0.02:
        grade = "A" if net_advantage > 0.04 else "B"
    elif net_advantage < -0.02:
        grade = "A" if net_advantage < -0.04 else "B"  # for team B
    else:
        grade = "C+"

    # which team the grade favors
    grade_favors = team_a_abbr if net_advantage > 0 else team_b_abbr

    return {
        "team_a": team_a_abbr,
        "team_b": team_b_abbr,
        "a_offensive_score": round(a_score, 4),
        "b_offensive_score": round(b_score, 4),
        "net_advantage": round(net_advantage, 4),
        "grade": grade,
        "grade_favors": grade_favors,
        "flags": flags,
        "details": {
            f"{team_a_abbr}_offense_vs_{team_b_abbr}_defense": a_off_advantages,
            f"{team_b_abbr}_offense_vs_{team_a_abbr}_defense": b_off_advantages,
        },
    }


def analyze_pace_mismatch(team_a_abbr, team_b_abbr, team_stats):
    """
    Check for pace mismatches — relevant for over/under analysis.
    Fast team vs slow team = pace compromise, affects total.
    """
    a_pace = team_stats.get(team_a_abbr, {}).get("pace")
    b_pace = team_stats.get(team_b_abbr, {}).get("pace")

    if a_pace is None or b_pace is None:
        return {"note": "Pace data not available"}

    # league average pace is roughly 99-100
    avg_pace = (a_pace + b_pace) / 2
    pace_diff = abs(a_pace - b_pace)

    faster = team_a_abbr if a_pace > b_pace else team_b_abbr
    slower = team_b_abbr if a_pace > b_pace else team_a_abbr

    mismatch = "significant" if pace_diff > 3 else "moderate" if pace_diff > 1.5 else "minimal"

    return {
        "team_a_pace": round(a_pace, 1),
        "team_b_pace": round(b_pace, 1),
        "projected_pace": round(avg_pace, 1),
        "pace_diff": round(pace_diff, 1),
        "faster_team": faster,
        "slower_team": slower,
        "mismatch_level": mismatch,
        "over_under_lean": "over" if avg_pace > 100 else "under" if avg_pace < 97 else "neutral",
    }
