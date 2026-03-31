"""
crunch.py — The Synthesis Engine

Produces a DEEPLY COMPREHENSIVE analysis per game.
For each matchup: 40+ dimensions of data, league ranks,
Four Factors breakdown, player-level intelligence, pace analysis,
scoring profile comparison, defensive matchups, recent form,
Elo prediction with contextual adjustments, and odds value detection.
"""
import json
from cache import load_cached, load_nightly, save_nightly, normalize_abbr
from elo import load_ratings, predict_game
from four_factors import analyze_matchup, analyze_pace_mismatch
from model import full_model_prediction, compute_feature_importance


def american_to_implied_prob(odds):
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def rank_label(rank, total=30):
    """Convert rank number to readable label."""
    if rank is None:
        return "?"
    if rank <= 3:
        return f"#{rank} (elite)"
    elif rank <= 5:
        return f"#{rank} (top 5)"
    elif rank <= 10:
        return f"#{rank} (top 10)"
    elif rank <= 15:
        return f"#{rank} (above avg)"
    elif rank <= 20:
        return f"#{rank} (below avg)"
    elif rank <= 25:
        return f"#{rank} (bottom 10)"
    elif rank <= 28:
        return f"#{rank} (bottom 5)"
    else:
        return f"#{rank} (bottom 3)"


def get_team_players(player_stats, team_abbr, top_n=8):
    """Get top N players for a team by minutes played."""
    team_players = [p for p in player_stats if p.get("team") == team_abbr]
    team_players.sort(key=lambda p: p.get("min", 0), reverse=True)
    return team_players[:top_n]


def build_team_profile(abbr, team_stats, player_stats, elo_ratings):
    """
    Build a comprehensive profile for one team.
    This is the foundation — everything we know about this team.
    """
    t = team_stats.get(abbr, {})
    if not t:
        return {"abbreviation": abbr, "error": f"No stats for {abbr}"}

    # top players
    players = get_team_players(player_stats, abbr)
    player_profiles = []
    for p in players:
        player_profiles.append({
            "name": p["name"],
            "ppg": p.get("ppg"), "rpg": p.get("rpg"), "apg": p.get("apg"),
            "spg": p.get("spg"), "bpg": p.get("bpg"), "tov": p.get("tov"),
            "min": p.get("min"), "gp": p.get("gp"),
            "fg_pct": p.get("fg_pct"), "fg3_pct": p.get("fg3_pct"),
            "ft_pct": p.get("ft_pct"), "ts_pct": p.get("ts_pct"),
            "usg_pct": p.get("usg_pct"), "net_rating": p.get("net_rating"),
            "plus_minus": p.get("plus_minus"), "pie": p.get("pie"),
            "fg3m": p.get("fg3m"), "fg3a": p.get("fg3a"),
        })

    profile = {
        "abbreviation": abbr,
        "team_name": t.get("team_name"),
        "record": f"{t.get('wins', '?')}-{t.get('losses', '?')}",
        "win_pct": t.get("win_pct"),
        "elo": elo_ratings.get(abbr, 1500),

        # offensive profile
        "offense": {
            "rating": t.get("off_rating"),
            "rank": rank_label(t.get("off_rating_rank")),
            "ppg": t.get("ppg"),
            "ppg_rank": rank_label(t.get("ppg_rank")),
            "fg_pct": t.get("fg_pct"),
            "fg3_pct": t.get("fg3_pct"),
            "ft_pct": t.get("ft_pct"),
            "ts_pct": t.get("ts_pct"),
            "ts_rank": rank_label(t.get("ts_pct_rank")),
            "efg_pct": t.get("efg_pct"),
            "efg_rank": rank_label(t.get("efg_pct_rank")),
            "apg": t.get("apg"),
            "apg_rank": rank_label(t.get("apg_rank")),
            "tov_pg": t.get("tov_pg"),
            "tov_rank": rank_label(t.get("tov_pg_rank")),
            "oreb_pg": t.get("oreb_pg"),
            "oreb_pct": t.get("oreb_pct"),
            "oreb_rank": rank_label(t.get("oreb_pct_rank")),
            "pace": t.get("pace"),
            "pace_rank": rank_label(t.get("pace_rank")),
        },

        # defensive profile
        "defense": {
            "rating": t.get("def_rating"),
            "rank": rank_label(t.get("def_rating_rank")),
            **(t.get("defense", {})),
            "spg": t.get("spg"),
            "spg_rank": rank_label(t.get("spg_rank")),
            "bpg": t.get("bpg"),
            "bpg_rank": rank_label(t.get("bpg_rank")),
            "dreb_pct": t.get("dreb_pct"),
            "dreb_rank": rank_label(t.get("dreb_pct_rank")),
        },

        # overall
        "net_rating": t.get("net_rating"),
        "net_rating_rank": rank_label(t.get("net_rating_rank")),
        "plus_minus": t.get("plus_minus"),
        "plus_minus_rank": rank_label(t.get("plus_minus_rank")),
        "pie": t.get("pie"),

        # four factors
        "four_factors": t.get("four_factors", {}),

        # scoring breakdown
        "scoring_profile": t.get("scoring", {}),

        # recent form
        "last_5": t.get("last_5", {}),
        "last_10": t.get("last_10", {}),

        # key players
        "key_players": player_profiles,
    }

    return profile


def compare_dimension(home_val, away_val, stat_name, higher_is_better=True):
    """Compare a single stat dimension between two teams."""
    if home_val is None or away_val is None:
        return None
    diff = home_val - away_val
    if not higher_is_better:
        diff = -diff
    advantage = "home" if diff > 0 else "away" if diff < 0 else "even"
    return {
        "stat": stat_name,
        "home": home_val,
        "away": away_val,
        "diff": round(abs(home_val - away_val), 2),
        "advantage": advantage,
        "significant": abs(diff) > 0.02 if isinstance(home_val, float) and abs(home_val) < 1 else abs(diff) > 2,
    }


def _safe_sub(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 4)


def _efg_narrative(team_a, team_b, a_efg, b_opp_efg):
    if a_efg is None or b_opp_efg is None:
        return ""
    edge = a_efg - b_opp_efg
    if edge > 0.02:
        return f"{team_a} shoots well and {team_b} allows high eFG% — shooting advantage"
    elif edge < -0.02:
        return f"{team_b} defense should limit {team_a}'s shooting"
    return "Neutral shooting matchup"


def _trend_direction(profile):
    season_net = profile.get("net_rating")
    l10_net = profile.get("last_10", {}).get("net_rating")
    l5_net = profile.get("last_5", {}).get("net_rating")
    if l5_net is None or season_net is None:
        return "unknown"
    if l5_net > season_net + 2:
        return "hot (L5 significantly above season average)"
    elif l5_net > season_net:
        return "trending up"
    elif l5_net < season_net - 2:
        return "cold (L5 significantly below season average)"
    elif l5_net < season_net:
        return "trending down"
    return "steady"


def build_comprehensive_matchup(home_profile, away_profile, team_stats):
    """Build the full matchup analysis across every dimension."""
    h = home_profile
    a = away_profile
    ho = h.get("offense", {})
    ao = a.get("offense", {})
    hd = h.get("defense", {})
    ad = a.get("defense", {})
    matchup = {}

    # 1. Team Strength
    matchup["strength"] = {
        "off_rating": compare_dimension(ho.get("rating"), ao.get("rating"), "Offensive Rating"),
        "def_rating": compare_dimension(hd.get("rating"), ad.get("rating"), "Defensive Rating", False),
        "net_rating": compare_dimension(h.get("net_rating"), a.get("net_rating"), "Net Rating"),
        "win_pct": compare_dimension(h.get("win_pct"), a.get("win_pct"), "Win %"),
        "elo": compare_dimension(h.get("elo"), a.get("elo"), "Elo Rating"),
    }

    # 2. Offensive Comparison
    matchup["offense"] = {
        "ppg": compare_dimension(ho.get("ppg"), ao.get("ppg"), "Points Per Game"),
        "fg_pct": compare_dimension(ho.get("fg_pct"), ao.get("fg_pct"), "FG%"),
        "fg3_pct": compare_dimension(ho.get("fg3_pct"), ao.get("fg3_pct"), "3PT%"),
        "ft_pct": compare_dimension(ho.get("ft_pct"), ao.get("ft_pct"), "FT%"),
        "ts_pct": compare_dimension(ho.get("ts_pct"), ao.get("ts_pct"), "True Shooting %"),
        "efg_pct": compare_dimension(ho.get("efg_pct"), ao.get("efg_pct"), "Effective FG%"),
        "apg": compare_dimension(ho.get("apg"), ao.get("apg"), "Assists Per Game"),
        "tov_pg": compare_dimension(ho.get("tov_pg"), ao.get("tov_pg"), "Turnovers Per Game", False),
        "oreb_pct": compare_dimension(ho.get("oreb_pct"), ao.get("oreb_pct"), "Offensive Rebound %"),
        "pace": compare_dimension(ho.get("pace"), ao.get("pace"), "Pace"),
    }

    # 3. Defensive Comparison
    matchup["defense"] = {
        "def_rating": compare_dimension(hd.get("rating"), ad.get("rating"), "Defensive Rating", False),
        "opp_ppg": compare_dimension(hd.get("opp_ppg"), ad.get("opp_ppg"), "Opp PPG Allowed", False),
        "opp_fg_pct": compare_dimension(hd.get("opp_fg_pct"), ad.get("opp_fg_pct"), "Opp FG% Allowed", False),
        "opp_fg3_pct": compare_dimension(hd.get("opp_fg3_pct"), ad.get("opp_fg3_pct"), "Opp 3PT% Allowed", False),
        "spg": compare_dimension(hd.get("spg"), ad.get("spg"), "Steals Per Game"),
        "bpg": compare_dimension(hd.get("bpg"), ad.get("bpg"), "Blocks Per Game"),
        "dreb_pct": compare_dimension(hd.get("dreb_pct"), ad.get("dreb_pct"), "Defensive Rebound %"),
    }

    # 4. Four Factors
    matchup["four_factors"] = analyze_matchup(a["abbreviation"], h["abbreviation"], team_stats)

    # 5. Pace & Style
    matchup["pace_analysis"] = analyze_pace_mismatch(a["abbreviation"], h["abbreviation"], team_stats)

    # 6. Scoring Profile
    hs = h.get("scoring_profile", {})
    as_ = a.get("scoring_profile", {})
    matchup["scoring_style"] = {
        "home_3pt_rate": hs.get("pct_fga_3pt"),
        "away_3pt_rate": as_.get("pct_fga_3pt"),
        "home_paint_pct": hs.get("pct_pts_paint"),
        "away_paint_pct": as_.get("pct_pts_paint"),
        "home_fb_pct": hs.get("pct_pts_fb"),
        "away_fb_pct": as_.get("pct_pts_fb"),
        "home_ft_pct_pts": hs.get("pct_pts_ft"),
        "away_ft_pct_pts": as_.get("pct_pts_ft"),
        "home_off_tov_pct": hs.get("pct_pts_off_tov"),
        "away_off_tov_pct": as_.get("pct_pts_off_tov"),
    }

    # 7. Cross-Matchups (offense vs defense)
    matchup["cross_matchups"] = {
        "home_shooting_vs_away_defense": {
            "home_efg": h.get("four_factors", {}).get("efg_pct"),
            "away_opp_efg": a.get("four_factors", {}).get("opp_efg_pct"),
            "edge": _safe_sub(h.get("four_factors", {}).get("efg_pct"),
                              a.get("four_factors", {}).get("opp_efg_pct")),
            "narrative": _efg_narrative(h["abbreviation"], a["abbreviation"],
                h.get("four_factors", {}).get("efg_pct"),
                a.get("four_factors", {}).get("opp_efg_pct")),
        },
        "away_shooting_vs_home_defense": {
            "away_efg": a.get("four_factors", {}).get("efg_pct"),
            "home_opp_efg": h.get("four_factors", {}).get("opp_efg_pct"),
            "edge": _safe_sub(a.get("four_factors", {}).get("efg_pct"),
                              h.get("four_factors", {}).get("opp_efg_pct")),
        },
        "home_tov_vs_away_forcing": {
            "home_tov_rate": h.get("four_factors", {}).get("tm_tov_pct"),
            "away_opp_tov_rate": a.get("four_factors", {}).get("opp_tov_pct"),
            "edge": _safe_sub(a.get("four_factors", {}).get("opp_tov_pct"),
                              h.get("four_factors", {}).get("tm_tov_pct")),
        },
        "away_tov_vs_home_forcing": {
            "away_tov_rate": a.get("four_factors", {}).get("tm_tov_pct"),
            "home_opp_tov_rate": h.get("four_factors", {}).get("opp_tov_pct"),
            "edge": _safe_sub(h.get("four_factors", {}).get("opp_tov_pct"),
                              a.get("four_factors", {}).get("tm_tov_pct")),
        },
        "home_3pt_vs_away_3pt_def": {
            "home_fg3_pct": ho.get("fg3_pct"),
            "away_opp_fg3_pct": ad.get("opp_fg3_pct"),
            "edge": _safe_sub(ho.get("fg3_pct"), ad.get("opp_fg3_pct")),
        },
        "away_3pt_vs_home_3pt_def": {
            "away_fg3_pct": ao.get("fg3_pct"),
            "home_opp_fg3_pct": hd.get("opp_fg3_pct"),
            "edge": _safe_sub(ao.get("fg3_pct"), hd.get("opp_fg3_pct")),
        },
        "rebounding": {
            "home_oreb_pct": h.get("four_factors", {}).get("oreb_pct"),
            "away_opp_oreb_pct": a.get("four_factors", {}).get("opp_oreb_pct"),
            "away_oreb_pct": a.get("four_factors", {}).get("oreb_pct"),
            "home_opp_oreb_pct": h.get("four_factors", {}).get("opp_oreb_pct"),
        },
    }

    # 8. Recent Form
    hl10 = h.get("last_10", {})
    al10 = a.get("last_10", {})
    hl5 = h.get("last_5", {})
    al5 = a.get("last_5", {})
    matchup["recent_form"] = {
        "home_last_10": f"{hl10.get('wins', '?')}-{hl10.get('losses', '?')}",
        "away_last_10": f"{al10.get('wins', '?')}-{al10.get('losses', '?')}",
        "home_last_5": f"{hl5.get('wins', '?')}-{hl5.get('losses', '?')}",
        "away_last_5": f"{al5.get('wins', '?')}-{al5.get('losses', '?')}",
        "home_l10_net": hl10.get("net_rating"),
        "away_l10_net": al10.get("net_rating"),
        "home_l5_net": hl5.get("net_rating"),
        "away_l5_net": al5.get("net_rating"),
        "home_l10_ppg": hl10.get("ppg"),
        "away_l10_ppg": al10.get("ppg"),
        "home_trending": _trend_direction(h),
        "away_trending": _trend_direction(a),
    }

    # 9. Key Matchup Flags
    matchup["flags"] = _generate_flags(home_profile, away_profile, matchup)

    return matchup


def _generate_flags(home, away, matchup):
    """Generate specific, actionable insight flags from the matchup data."""
    flags = []
    h_abbr = home["abbreviation"]
    a_abbr = away["abbreviation"]

    # Four Factors flags
    for flag in matchup.get("four_factors", {}).get("flags", []):
        flags.append({"type": "four_factors", "text": flag})

    # 3PT mismatch
    cross = matchup.get("cross_matchups", {})
    h3 = cross.get("home_3pt_vs_away_3pt_def", {})
    a3 = cross.get("away_3pt_vs_home_3pt_def", {})
    if h3.get("edge") and h3["edge"] > 0.02:
        flags.append({"type": "shooting", "text":
            f"{h_abbr} shoots {(h3.get('home_fg3_pct') or 0)*100:.1f}% from 3 vs {a_abbr} allowing {(h3.get('away_opp_fg3_pct') or 0)*100:.1f}% — 3PT mismatch"})
    if a3.get("edge") and a3["edge"] > 0.02:
        flags.append({"type": "shooting", "text":
            f"{a_abbr} shoots {(a3.get('away_fg3_pct') or 0)*100:.1f}% from 3 vs {h_abbr} allowing {(a3.get('home_opp_fg3_pct') or 0)*100:.1f}% — 3PT mismatch"})

    # Turnover mismatch
    htov = cross.get("home_tov_vs_away_forcing", {})
    atov = cross.get("away_tov_vs_home_forcing", {})
    if htov.get("edge") and htov["edge"] > 0.02:
        flags.append({"type": "turnovers", "text":
            f"{a_abbr} forces turnovers ({(htov.get('away_opp_tov_rate') or 0)*100:.1f}%) vs {h_abbr}'s offense ({(htov.get('home_tov_rate') or 0)*100:.1f}%)"})
    if atov.get("edge") and atov["edge"] > 0.02:
        flags.append({"type": "turnovers", "text":
            f"{h_abbr} forces turnovers ({(atov.get('home_opp_tov_rate') or 0)*100:.1f}%) vs {a_abbr}'s offense ({(atov.get('away_tov_rate') or 0)*100:.1f}%)"})

    # Pace mismatch
    pace = matchup.get("pace_analysis", {})
    if pace.get("mismatch_level") in ["moderate", "significant"]:
        flags.append({"type": "pace", "text":
            f"Pace mismatch: {pace.get('faster_team')} vs {pace.get('slower_team')} ({pace.get('pace_diff'):.1f} possessions/game gap) — affects total"})

    # Recent form
    form = matchup.get("recent_form", {})
    for side, abbr in [("home", h_abbr), ("away", a_abbr)]:
        trend = form.get(f"{side}_trending", "")
        if "hot" in trend:
            flags.append({"type": "trend", "text": f"{abbr} is HOT — L5 net rating significantly above season average"})
        if "cold" in trend:
            flags.append({"type": "trend", "text": f"{abbr} is COLD — L5 net rating significantly below season average"})

    # Net rating gap
    h_net = home.get("net_rating", 0) or 0
    a_net = away.get("net_rating", 0) or 0
    net_gap = abs(h_net - a_net)
    if net_gap > 8:
        better = h_abbr if h_net > a_net else a_abbr
        worse = a_abbr if h_net > a_net else h_abbr
        flags.append({"type": "mismatch", "text":
            f"Large talent gap: {better} ({max(h_net, a_net):+.1f} net) vs {worse} ({min(h_net, a_net):+.1f} net)"})

    # Offensive/Defensive identity
    ho = home.get("offense", {})
    ao = away.get("offense", {})
    hd = home.get("defense", {})
    ad = away.get("defense", {})
    for abbr, off, deff in [(h_abbr, ho, hd), (a_abbr, ao, ad)]:
        if off.get("rating") and deff.get("rating"):
            if off["rating"] > 115 and deff["rating"] > 115:
                flags.append({"type": "identity", "text":
                    f"{abbr} is offense-first (ORTG {off['rating']:.1f}, DRTG {deff['rating']:.1f}) — high-scoring games likely"})
            if off["rating"] < 110 and deff["rating"] < 110:
                flags.append({"type": "identity", "text":
                    f"{abbr} is defense-first (ORTG {off['rating']:.1f}, DRTG {deff['rating']:.1f}) — grind-it-out"})

    # Shooting efficiency matchup narratives
    h_shoot = cross.get("home_shooting_vs_away_defense", {})
    a_shoot = cross.get("away_shooting_vs_home_defense", {})
    if h_shoot.get("narrative"):
        flags.append({"type": "shooting", "text": h_shoot["narrative"]})

    return flags


def analyze_odds(game_odds, elo_pred, home_name, away_name):
    """Full odds analysis if data is available."""
    if not game_odds:
        return {"note": "No odds data — add ODDS_API_KEY to .env"}

    markets = game_odds.get("markets", {})
    analysis = {}

    h2h = markets.get("h2h", [])
    if h2h:
        for side_key, team_key, prob_key in [
            ("moneyline_home", "home_team", "home_win_prob"),
            ("moneyline_away", "away_team", "away_win_prob"),
        ]:
            entries = [e for e in h2h if e["name"] == game_odds.get(team_key)]
            if entries:
                best = max(entries, key=lambda x: x["price"])
                worst = min(entries, key=lambda x: x["price"])
                edge = round((elo_pred[prob_key] - best["implied_prob"]) * 100, 2)
                analysis[side_key] = {
                    "best_odds": best["price"], "best_book": best["book"],
                    "worst_odds": worst["price"], "worst_book": worst["book"],
                    "implied_prob": round(best["implied_prob"] * 100, 1),
                    "model_prob": round(elo_pred[prob_key] * 100, 1),
                    "edge_pct": edge, "is_value": edge > 3,
                }

    spreads = markets.get("spreads", [])
    if spreads:
        home_spreads = [e for e in spreads if e["name"] == game_odds.get("home_team")]
        if home_spreads:
            best = max(home_spreads, key=lambda x: x.get("point", 0))
            worst = min(home_spreads, key=lambda x: x.get("point", 0))
            analysis["spread"] = {
                "best_line": best.get("point"), "best_book": best["book"],
                "best_odds": best["price"],
                "worst_line": worst.get("point"), "worst_book": worst["book"],
                "model_spread": elo_pred.get("projected_spread"),
                "diff": round((best.get("point", 0) or 0) - (elo_pred.get("projected_spread", 0) or 0), 1),
            }

    totals = markets.get("totals", [])
    if totals:
        over_entries = [e for e in totals if e["name"] == "Over"]
        under_entries = [e for e in totals if e["name"] == "Under"]
        if over_entries:
            best_over = max(over_entries, key=lambda x: x["price"])
            analysis["total"] = {
                "line": over_entries[0].get("point"),
                "best_over_odds": best_over["price"], "best_over_book": best_over["book"],
            }
            if under_entries:
                best_under = max(under_entries, key=lambda x: x["price"])
                analysis["total"]["best_under_odds"] = best_under["price"]
                analysis["total"]["best_under_book"] = best_under["book"]

    return analysis


def generate_picks(games_analysis):
    """Generate picks from the comprehensive analysis."""
    picks = []
    for game in games_analysis:
        home = game["home_profile"]["abbreviation"]
        away = game["away_profile"]["abbreviation"]
        odds = game.get("odds_analysis", {})
        flags = game.get("matchup", {}).get("flags", [])

        for side, label in [("moneyline_home", home), ("moneyline_away", away)]:
            ml = odds.get(side, {})
            edge = ml.get("edge_pct", 0)
            if edge > 2:
                picks.append({
                    "type": "Moneyline", "team": label,
                    "matchup": f"{away} @ {home}",
                    "bet": f"{label} ML ({ml.get('best_odds', '?')})",
                    "book": ml.get("best_book", "?"),
                    "edge_pct": edge,
                    "model_prob": ml.get("model_prob"),
                    "market_prob": ml.get("implied_prob"),
                    "confidence": "Strong" if edge > 5 else "Lean",
                    "rationale": f"Model: {ml.get('model_prob')}% vs Market: {ml.get('implied_prob')}%. {edge:.1f}% edge.",
                    "supporting_flags": [f["text"] for f in flags[:3]],
                })

        spread = odds.get("spread", {})
        diff = abs(spread.get("diff", 0))
        if diff > 1.5:
            picks.append({
                "type": "Spread",
                "team": home if spread.get("diff", 0) > 0 else away,
                "matchup": f"{away} @ {home}",
                "bet": f"{spread.get('best_line')} ({spread.get('best_odds', '?')})",
                "book": spread.get("best_book", "?"),
                "edge_pct": diff,
                "confidence": "Strong" if diff > 3 else "Lean",
                "rationale": f"Model: {spread.get('model_spread')}, Market: {spread.get('best_line')}. {diff:.1f}pt gap.",
            })

    picks.sort(key=lambda x: x.get("edge_pct", 0), reverse=True)
    return picks


def run_analysis():
    """Main pipeline: load data, analyze every game comprehensively."""
    print("\n=== CRUNCH: Running comprehensive analysis ===\n")

    schedule = load_nightly("schedule.json")
    odds_raw = load_nightly("odds.json")
    stake_raw = load_nightly("odds_stake.json")
    team_stats = load_cached("team_stats")
    player_stats = load_cached("player_stats") or []
    elo_ratings = load_ratings()

    if not schedule:
        print("  ERROR: No schedule data. Run fetch_schedule.py first.")
        return

    games = schedule.get("games", [])
    odds_games = odds_raw.get("games", []) if odds_raw else []
    stake_games = stake_raw.get("games", []) if stake_raw else []

    print(f"  Analyzing {len(games)} games across 40+ dimensions per matchup...\n")

    games_analysis = []
    for game in games:
        if game["status"] == "Final":
            continue

        home_abbr = normalize_abbr(game["home"]["abbreviation"])
        away_abbr = normalize_abbr(game["away"]["abbreviation"])
        print(f"  {away_abbr} @ {home_abbr}...")

        home_profile = build_team_profile(home_abbr, team_stats, player_stats, elo_ratings)
        away_profile = build_team_profile(away_abbr, team_stats, player_stats, elo_ratings)
        elo_pred = predict_game(elo_ratings, home_abbr, away_abbr)
        matchup = build_comprehensive_matchup(home_profile, away_profile, team_stats)

        game_odds = None
        for od in odds_games:
            if (game["home"]["name"] in od.get("home_team", "") or
                game["away"]["name"] in od.get("away_team", "")):
                game_odds = od
                break

        odds_result = analyze_odds(game_odds, elo_pred, home_abbr, away_abbr)

        # match Stake.com odds to this game
        stake_game = None
        home_name = game["home"]["name"]
        away_name = game["away"]["name"]
        for sg in stake_games:
            # fuzzy match: check if team name appears in Stake's team name
            sh = sg.get("home_team", "")
            sa = sg.get("away_team", "")
            if (any(word in sh for word in home_name.split()[-1:]) and
                any(word in sa for word in away_name.split()[-1:])):
                stake_game = sg
                break

        # statistical model predictions (logistic regression, Monte Carlo, Bayesian, player props)
        model_pred = full_model_prediction(home_abbr, away_abbr, team_stats, player_stats)

        analysis = {
            "game_id": game["game_id"],
            "status": game["status"],
            "venue": game["venue"],
            "tipoff": game["date"],
            "home_profile": home_profile,
            "away_profile": away_profile,
            "elo": elo_pred,
            "statistical_model": model_pred,
            "matchup": matchup,
            "odds_analysis": odds_result,
            "stake_odds": stake_game,
        }
        games_analysis.append(analysis)

        # print summary
        lr = model_pred["logistic_regression"]
        mc = model_pred["monte_carlo"]
        bs = model_pred["bayesian_strength"]
        n_flags = len(matchup.get("flags", []))
        print(f"    Elo:        {home_abbr} {elo_pred['home_win_prob']*100:.1f}% | {away_abbr} {elo_pred['away_win_prob']*100:.1f}%")
        print(f"    Logistic:   {home_abbr} {lr['home_win_prob']*100:.1f}% | {away_abbr} {lr['away_win_prob']*100:.1f}%")
        print(f"    MC spread:  {mc['mean_margin']:+.1f} (90% CI: [{mc['ci_90_margin'][0]:+.1f}, {mc['ci_90_margin'][1]:+.1f}])")
        print(f"    Projected total: {mc['score_dist']['projected_total']}")
        print(f"    Bayesian:   {home_abbr} {bs['home']['mean']:+.1f}±{bs['home']['std']:.1f} | {away_abbr} {bs['away']['mean']:+.1f}±{bs['away']['std']:.1f}")
        print(f"    Flags ({n_flags}):")
        for f in matchup.get("flags", []):
            print(f"      - [{f['type']}] {f['text']}")
        # player prop highlights
        props = model_pred.get("player_props", [])
        notable_props = [p for p in props if abs(p["edge"]["pts"]) > 0.3]
        if notable_props:
            print(f"    Notable props:")
            for pp in notable_props[:4]:
                e = pp["edge"]
                print(f"      {pp['name']}: avg {pp['season_avg']['ppg']:.1f}pts → proj {pp['projected']['ppg']:.1f}pts ({e['pts_direction']})")
        print()

    picks = generate_picks(games_analysis)

    output = {
        "date": schedule["date"],
        "game_count": len(games_analysis),
        "pick_count": len(picks),
        "picks": picks,
        "games": games_analysis,
        "model_info": {
            "dimensions_per_game": "40+",
            "layers": [
                "Elo power ratings (K=20, MOV multiplier, seeded from net rating)",
                "Four Factors: eFG% (40%), TOV% (25%), OREB% (20%), FTRate (15%) — offense vs defense",
                "Cross-matchups: shooting eFG% vs opponent eFG%, 3PT% vs opp 3PT%, turnovers, rebounding",
                "Scoring profile: 3PT shot rate, paint scoring %, fast break %, FT %, off-turnover %",
                "Defensive profile: opp PPG, opp FG%, opp 3PT%, steals, blocks, forced turnovers, DREB%",
                "Recent form: L5 and L10 records + net ratings + trend direction vs season average",
                "Contextual: home court (+70 Elo), B2B (-46), rest (+25/day), altitude",
                "Key players: top 8 per team — PPG, RPG, APG, TS%, USG%, +/-, PIE",
                "League rankings: every stat ranked 1-30 with tier labels",
                "Market comparison: model prob vs implied prob across 40+ books",
            ],
        },
    }

    save_nightly("analysis.json", output)

    print(f"\n=== COMPLETE: {len(games_analysis)} games, {sum(len(g['matchup'].get('flags', [])) for g in games_analysis)} insight flags ===")
    if picks:
        for p in picks:
            print(f"  [{p['confidence']}] {p['bet']} @ {p['book']} — {p['edge_pct']:.1f}%")
    else:
        print("  No picks (need odds data — add ODDS_API_KEY to .env)")

    return output


if __name__ == "__main__":
    run_analysis()
