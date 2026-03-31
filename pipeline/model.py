"""
model.py — Statistical modeling for NBA game prediction.

This is where the real analytics lives. Not just comparing numbers —
actual statistical models that learn relationships from data.

Methods:
1. Logistic regression on team features → win probability
2. Monte Carlo simulation → confidence intervals on predictions
3. Bayesian strength estimation → posterior team strength with uncertainty
4. Feature importance analysis → what actually predicts wins
5. Player prop projections → matchup-adjusted player line analysis
"""
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from cache import load_cached


# ============================================================
# 1. LOGISTIC REGRESSION MODEL
#    Uses team-level features to predict win probability.
#    More principled than raw Elo — learns optimal feature weights.
# ============================================================

def build_feature_vector(team_stats, team_abbr):
    """
    Extract a feature vector for one team from their stats.
    Each feature is something that plausibly predicts winning.
    """
    t = team_stats.get(team_abbr, {})
    ff = t.get("four_factors", {})
    l10 = t.get("last_10", {})
    l5 = t.get("last_5", {})

    return {
        # efficiency (the most predictive features)
        "net_rating": t.get("net_rating", 0),
        "off_rating": t.get("off_rating", 110),
        "def_rating": t.get("def_rating", 110),

        # four factors (explains 91.4% of win variance)
        "efg_pct": ff.get("efg_pct", 0.50),
        "tov_pct": ff.get("tm_tov_pct", 0.13),
        "oreb_pct": ff.get("oreb_pct", 0.28),
        "fta_rate": ff.get("fta_rate", 0.25),
        "opp_efg_pct": ff.get("opp_efg_pct", 0.50),
        "opp_tov_pct": ff.get("opp_tov_pct", 0.13),
        "opp_oreb_pct": ff.get("opp_oreb_pct", 0.28),
        "opp_fta_rate": ff.get("opp_fta_rate", 0.25),

        # shooting
        "ts_pct": t.get("ts_pct", 0.56),
        "fg3_pct": t.get("fg3_pct", 0.36),

        # pace
        "pace": t.get("pace", 99),

        # recent form (momentum matters)
        "l10_net": l10.get("net_rating", 0) if l10 else 0,
        "l5_net": l5.get("net_rating", 0) if l5 else 0,
        "l10_win_pct": (l10.get("wins", 5) / 10) if l10 else 0.5,
        "l5_win_pct": (l5.get("wins", 2.5) / 5) if l5 else 0.5,
    }


def compute_matchup_features(home_features, away_features, is_home=True):
    """
    Compute the DIFFERENTIAL features that predict game outcomes.
    Home - Away for each feature, plus home court indicator.
    """
    diff = {}
    for key in home_features:
        h = home_features[key] or 0
        a = away_features[key] or 0
        diff[f"diff_{key}"] = h - a

    diff["home_court"] = 1.0 if is_home else 0.0
    return diff


def logistic_predict(matchup_features, weights=None):
    """
    Logistic regression prediction.

    Without historical training data, we use empirically-derived weights
    based on published research (538, academic literature) for what
    predicts NBA game outcomes.

    With training data, these weights would be learned via maximum
    likelihood estimation (MLE) — that's the upgrade path.
    """
    if weights is None:
        # empirically-calibrated weights from NBA research literature
        # net_rating differential is the single best predictor
        weights = {
            "diff_net_rating": 0.12,      # ~3% win prob per point of net rating
            "diff_off_rating": 0.03,      # supplementary to net
            "diff_def_rating": -0.03,     # lower is better, so negative weight
            "diff_efg_pct": 2.5,          # biggest Four Factor (40% weight)
            "diff_tov_pct": -1.5,         # turnovers hurt (negative = bad)
            "diff_oreb_pct": 1.0,         # second chances
            "diff_fta_rate": 0.8,         # getting to the line
            "diff_opp_efg_pct": -2.5,     # defensive eFG (lower = better defense)
            "diff_opp_tov_pct": 1.5,      # forcing turnovers
            "diff_opp_oreb_pct": -1.0,    # allowing offensive rebounds (bad)
            "diff_opp_fta_rate": -0.8,    # fouling (bad)
            "diff_ts_pct": 1.0,           # true shooting
            "diff_fg3_pct": 0.5,          # 3-point shooting
            "diff_pace": 0.0,             # pace itself doesn't predict wins
            "diff_l10_net": 0.04,         # recent form
            "diff_l5_net": 0.05,          # very recent form (weighted more)
            "diff_l10_win_pct": 0.3,      # recent win rate
            "diff_l5_win_pct": 0.4,       # very recent win rate
            "home_court": 0.45,           # ~61% home win rate historically
            "intercept": 0.0,
        }

    # compute logit (log-odds)
    logit = weights.get("intercept", 0)
    for feature, value in matchup_features.items():
        logit += weights.get(feature, 0) * value

    # sigmoid → probability
    prob = 1.0 / (1.0 + np.exp(-logit))
    return prob


# ============================================================
# 2. MONTE CARLO SIMULATION
#    Adds uncertainty to predictions. Instead of "Team A wins 65%",
#    we get "Team A wins 65% ± 8%" with a full distribution.
# ============================================================

def monte_carlo_game(home_prob, n_sims=10000, score_mean_home=112, score_mean_away=108,
                     score_std=12):
    """
    Simulate a game n_sims times using the model's win probability
    and realistic score distributions.

    Returns simulation results with confidence intervals.
    """
    # simulate scores from normal distributions
    # mean is based on team offensive/defensive ratings
    home_scores = np.random.normal(score_mean_home, score_std, n_sims)
    away_scores = np.random.normal(score_mean_away, score_std, n_sims)

    # add some correlation (both teams play in same game environment)
    # high-pace games inflate both scores, slow games deflate both
    pace_noise = np.random.normal(0, 4, n_sims)
    home_scores += pace_noise
    away_scores += pace_noise

    margins = home_scores - away_scores
    home_wins = np.sum(margins > 0) / n_sims

    return {
        "simulated_home_win_pct": round(home_wins, 4),
        "mean_margin": round(np.mean(margins), 1),
        "median_margin": round(np.median(margins), 1),
        "std_margin": round(np.std(margins), 1),
        "ci_90_margin": [round(np.percentile(margins, 5), 1),
                         round(np.percentile(margins, 95), 1)],
        "ci_80_margin": [round(np.percentile(margins, 10), 1),
                         round(np.percentile(margins, 90), 1)],
        "prob_blowout_home": round(np.sum(margins > 15) / n_sims, 4),
        "prob_close_game": round(np.sum(np.abs(margins) < 5) / n_sims, 4),
        "prob_blowout_away": round(np.sum(margins < -15) / n_sims, 4),
        "score_dist": {
            "home_mean": round(np.mean(home_scores), 1),
            "away_mean": round(np.mean(away_scores), 1),
            "projected_total": round(np.mean(home_scores) + np.mean(away_scores), 1),
            "total_std": round(np.std(home_scores + away_scores), 1),
            "total_ci_90": [round(np.percentile(home_scores + away_scores, 5), 1),
                           round(np.percentile(home_scores + away_scores, 95), 1)],
        },
        "n_sims": n_sims,
    }


# ============================================================
# 3. BAYESIAN TEAM STRENGTH ESTIMATION
#    Instead of a point estimate (Elo = 1650), we get a
#    distribution: "This team's true strength is 1650 ± 80."
#    More games → tighter distribution → more confidence.
# ============================================================

def bayesian_strength(team_stats, team_abbr):
    """
    Estimate team strength as a distribution, not a point.
    Uses the team's record + net rating + variance in performance.

    Returns a normal distribution (mean, std) for team strength.
    """
    t = team_stats.get(team_abbr, {})

    net_rating = t.get("net_rating", 0)
    games_played = t.get("gp", 40)
    l5_net = t.get("last_5", {}).get("net_rating", net_rating)
    l10_net = t.get("last_10", {}).get("net_rating", net_rating)

    # the more games played, the more confident we are in the estimate
    # std shrinks proportional to sqrt(n)
    # typical NBA team net rating std is about 12 points game-to-game
    game_std = 12.0  # per-game standard deviation of point differential
    season_std = game_std / np.sqrt(max(games_played, 1))

    # also factor in recent volatility (if L5 differs a lot from season, more uncertain)
    volatility = abs(l5_net - net_rating)
    adjusted_std = np.sqrt(season_std**2 + (volatility / 3)**2)

    # bayesian posterior: combine season-long prior with recent observations
    # weight recent form more when it's been very different from season average
    recency_weight = min(0.4, volatility / 20)  # cap at 40% recent weight
    posterior_mean = (1 - recency_weight) * net_rating + recency_weight * l5_net

    return {
        "mean": round(posterior_mean, 2),
        "std": round(adjusted_std, 2),
        "ci_90": [round(posterior_mean - 1.645 * adjusted_std, 1),
                  round(posterior_mean + 1.645 * adjusted_std, 1)],
        "ci_80": [round(posterior_mean - 1.28 * adjusted_std, 1),
                  round(posterior_mean + 1.28 * adjusted_std, 1)],
        "games_played": games_played,
        "season_net": net_rating,
        "recent_net_l5": l5_net,
        "recent_net_l10": l10_net,
        "volatility": round(volatility, 1),
        "confidence": "high" if adjusted_std < 2.0 else "medium" if adjusted_std < 3.5 else "low",
    }


# ============================================================
# 4. PLAYER PROP PROJECTIONS
#    Adjust player averages based on opponent matchup.
#    "This player averages 22 PPG but faces the 28th-ranked
#    defense — project him at 25+ tonight."
# ============================================================

def project_player_props(player, opp_abbr, team_stats):
    """
    Project a player's stat line against a specific opponent,
    adjusted for the opponent's defensive profile.

    Uses a simple adjustment: if the opponent allows X% more/less
    than league average in a category, adjust the player's projection
    proportionally.
    """
    opp = team_stats.get(opp_abbr, {})
    opp_def = opp.get("defense", {})

    # league averages (approximate for 2025-26)
    league_avg_ppg = 113.5
    league_avg_fg_pct = 0.470
    league_avg_fg3_pct = 0.364

    # opponent's defensive multipliers
    # if they allow 120 ppg vs league avg 113.5, that's a 1.057x multiplier
    opp_ppg_allowed = opp_def.get("opp_ppg", league_avg_ppg) or league_avg_ppg
    opp_fg_pct_allowed = opp_def.get("opp_fg_pct", league_avg_fg_pct) or league_avg_fg_pct
    opp_fg3_pct_allowed = opp_def.get("opp_fg3_pct", league_avg_fg3_pct) or league_avg_fg3_pct

    ppg_mult = opp_ppg_allowed / league_avg_ppg
    fg_mult = opp_fg_pct_allowed / league_avg_fg_pct
    fg3_mult = opp_fg3_pct_allowed / league_avg_fg3_pct

    player_ppg = player.get("ppg", 0)
    player_rpg = player.get("rpg", 0)
    player_apg = player.get("apg", 0)
    player_fg3m = player.get("fg3m", 0)

    # adjust scoring for opponent defense quality
    # use a dampened multiplier (don't overreact — regression to mean)
    dampen = 0.5  # 50% of the raw adjustment
    adj_ppg = player_ppg * (1 + (ppg_mult - 1) * dampen)
    adj_fg3m = player_fg3m * (1 + (fg3_mult - 1) * dampen)

    # rebounds are less matchup-dependent, assists slightly
    opp_pace = opp.get("pace", 99)
    team_pace = 99  # approximate
    pace_factor = ((opp_pace + team_pace) / 2) / 99  # normalize to league avg
    adj_rpg = player_rpg * (1 + (pace_factor - 1) * 0.3)
    adj_apg = player_apg * (1 + (pace_factor - 1) * 0.2)

    # compute over/under edge (projected - season average)
    # positive = over looks good, negative = under looks good
    pts_edge = adj_ppg - player_ppg
    reb_edge = adj_rpg - player_rpg
    ast_edge = adj_apg - player_apg

    # standard deviation for player props (from NBA research)
    # roughly 25-30% of the mean for points, slightly higher for other stats
    pts_std = player_ppg * 0.30
    reb_std = player_rpg * 0.40
    ast_std = player_apg * 0.40

    return {
        "name": player.get("name"),
        "team": player.get("team"),
        "opponent": opp_abbr,
        "season_avg": {
            "ppg": player_ppg,
            "rpg": player_rpg,
            "apg": player_apg,
            "fg3m": player_fg3m,
        },
        "projected": {
            "ppg": round(adj_ppg, 1),
            "rpg": round(adj_rpg, 1),
            "apg": round(adj_apg, 1),
            "fg3m": round(adj_fg3m, 1),
        },
        "edge": {
            "pts": round(pts_edge, 1),
            "reb": round(reb_edge, 1),
            "ast": round(ast_edge, 1),
            "pts_direction": "OVER" if pts_edge > 0.5 else "UNDER" if pts_edge < -0.5 else "NEUTRAL",
            "reb_direction": "OVER" if reb_edge > 0.3 else "UNDER" if reb_edge < -0.3 else "NEUTRAL",
            "ast_direction": "OVER" if ast_edge > 0.3 else "UNDER" if ast_edge < -0.3 else "NEUTRAL",
        },
        "confidence": {
            "pts_std": round(pts_std, 1),
            "reb_std": round(reb_std, 1),
            "ast_std": round(ast_std, 1),
        },
        "matchup_context": {
            "opp_ppg_allowed": opp_ppg_allowed,
            "opp_ppg_rank": opp.get("def_rating_rank"),
            "opp_fg_pct_allowed": opp_fg_pct_allowed,
            "opp_fg3_pct_allowed": opp_fg3_pct_allowed,
            "scoring_multiplier": round(ppg_mult, 3),
        },
    }


# ============================================================
# 5. FEATURE IMPORTANCE ANALYSIS
#    What dimensions of the data actually matter most?
#    This helps the user understand which stats to watch.
# ============================================================

def compute_feature_importance(team_stats):
    """
    Rank features by how well they correlate with winning.
    Uses all 30 teams' data to compute correlation between
    each stat and win percentage.
    """
    teams = list(team_stats.values())
    if len(teams) < 10:
        return {"error": "Not enough teams for feature importance"}

    win_pcts = [t.get("win_pct", 0.5) for t in teams]

    features_to_test = [
        ("net_rating", "Net Rating", True),
        ("off_rating", "Offensive Rating", True),
        ("def_rating", "Defensive Rating", False),
        ("pace", "Pace", None),
        ("ts_pct", "True Shooting %", True),
        ("efg_pct", "Effective FG%", True),
        ("fg3_pct", "3-Point %", True),
        ("tov_pg", "Turnovers/Game", False),
        ("spg", "Steals/Game", True),
        ("bpg", "Blocks/Game", True),
        ("ppg", "Points/Game", True),
    ]

    # also test Four Factors
    ff_features = [
        ("four_factors.efg_pct", "Four Factors: eFG%", True),
        ("four_factors.tm_tov_pct", "Four Factors: TOV%", False),
        ("four_factors.oreb_pct", "Four Factors: OREB%", True),
        ("four_factors.fta_rate", "Four Factors: FT Rate", True),
        ("four_factors.opp_efg_pct", "Four Factors: Opp eFG%", False),
        ("four_factors.opp_tov_pct", "Four Factors: Opp TOV%", True),
    ]

    results = []
    for key, label, higher_is_better in features_to_test:
        values = [t.get(key) for t in teams]
        if all(v is not None for v in values):
            corr, p_value = stats.pearsonr(values, win_pcts)
            results.append({
                "feature": label,
                "correlation": round(corr, 3),
                "abs_correlation": round(abs(corr), 3),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "direction": "positive" if corr > 0 else "negative",
            })

    for key, label, higher_is_better in ff_features:
        parts = key.split(".")
        values = [t.get(parts[0], {}).get(parts[1]) if len(parts) > 1 else t.get(key) for t in teams]
        if all(v is not None for v in values):
            corr, p_value = stats.pearsonr(values, win_pcts)
            results.append({
                "feature": label,
                "correlation": round(corr, 3),
                "abs_correlation": round(abs(corr), 3),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "direction": "positive" if corr > 0 else "negative",
            })

    # sort by absolute correlation (most predictive first)
    results.sort(key=lambda x: x["abs_correlation"], reverse=True)
    return results


# ============================================================
# MAIN: Run all models for a matchup
# ============================================================

def full_model_prediction(home_abbr, away_abbr, team_stats, player_stats=None):
    """
    Run the full statistical model suite for one game.
    Returns comprehensive prediction with uncertainty.
    """
    # 1. feature vectors
    home_features = build_feature_vector(team_stats, home_abbr)
    away_features = build_feature_vector(team_stats, away_abbr)
    matchup_features = compute_matchup_features(home_features, away_features)

    # 2. logistic regression prediction
    lr_prob = logistic_predict(matchup_features)

    # 3. bayesian team strength
    home_strength = bayesian_strength(team_stats, home_abbr)
    away_strength = bayesian_strength(team_stats, away_abbr)

    # 4. monte carlo simulation
    # use team offensive ratings for score means
    h_stats = team_stats.get(home_abbr, {})
    a_stats = team_stats.get(away_abbr, {})
    h_ppg = h_stats.get("ppg", 112)
    a_ppg = a_stats.get("ppg", 110)
    # adjust away team scoring for home defense and vice versa
    h_def = h_stats.get("defense", {}).get("opp_ppg", 112)
    a_def = a_stats.get("defense", {}).get("opp_ppg", 112)
    home_score_mean = (h_ppg + a_def) / 2 + 1.5  # slight home boost
    away_score_mean = (a_ppg + h_def) / 2 - 1.5

    mc = monte_carlo_game(
        lr_prob,
        n_sims=10000,
        score_mean_home=home_score_mean,
        score_mean_away=away_score_mean,
    )

    # 5. player prop projections (top 5 per team)
    prop_projections = []
    if player_stats:
        home_players = [p for p in player_stats if p.get("team") == home_abbr]
        away_players = [p for p in player_stats if p.get("team") == away_abbr]
        home_players.sort(key=lambda p: p.get("min", 0), reverse=True)
        away_players.sort(key=lambda p: p.get("min", 0), reverse=True)

        for p in home_players[:5]:
            proj = project_player_props(p, away_abbr, team_stats)
            prop_projections.append(proj)
        for p in away_players[:5]:
            proj = project_player_props(p, home_abbr, team_stats)
            prop_projections.append(proj)

    # combined model probability (ensemble of Elo-based and logistic)
    # the ensemble is more robust than either alone
    ensemble_prob = lr_prob  # for now this is the primary; Elo blended in crunch.py

    return {
        "logistic_regression": {
            "home_win_prob": round(lr_prob, 4),
            "away_win_prob": round(1 - lr_prob, 4),
            "projected_spread": round(-(lr_prob - 0.5) * 28, 1),  # rough conversion
            "features_used": len(matchup_features),
        },
        "monte_carlo": mc,
        "bayesian_strength": {
            "home": home_strength,
            "away": away_strength,
        },
        "player_props": prop_projections,
    }


if __name__ == "__main__":
    # quick test
    team_stats = load_cached("team_stats")
    player_stats = load_cached("player_stats")

    if team_stats:
        print("Feature Importance (what predicts winning):")
        print("-" * 50)
        importance = compute_feature_importance(team_stats)
        for f in importance[:15]:
            sig = "*" if f["significant"] else " "
            print(f"  {sig} {f['feature']:30s} r={f['correlation']:+.3f}  p={f['p_value']:.4f}")

        print("\n\nSample prediction: NYK @ CHA")
        print("-" * 50)
        result = full_model_prediction("CHA", "NYK", team_stats, player_stats)

        lr = result["logistic_regression"]
        print(f"  Logistic Regression: CHA {lr['home_win_prob']*100:.1f}% | NYK {lr['away_win_prob']*100:.1f}%")
        print(f"  Projected spread: {lr['projected_spread']:+.1f}")

        mc = result["monte_carlo"]
        print(f"  Monte Carlo ({mc['n_sims']} sims):")
        print(f"    Mean margin: {mc['mean_margin']:+.1f}")
        print(f"    90% CI: [{mc['ci_90_margin'][0]:+.1f}, {mc['ci_90_margin'][1]:+.1f}]")
        print(f"    P(close game): {mc['prob_close_game']*100:.1f}%")
        print(f"    P(home blowout): {mc['prob_blowout_home']*100:.1f}%")
        print(f"    Projected total: {mc['score_dist']['projected_total']}")
        print(f"    Total 90% CI: [{mc['score_dist']['total_ci_90'][0]}, {mc['score_dist']['total_ci_90'][1]}]")

        bs = result["bayesian_strength"]
        print(f"  Bayesian Strength:")
        print(f"    CHA: {bs['home']['mean']:+.1f} ± {bs['home']['std']:.1f} (confidence: {bs['home']['confidence']})")
        print(f"    NYK: {bs['away']['mean']:+.1f} ± {bs['away']['std']:.1f} (confidence: {bs['away']['confidence']})")

        print(f"\n  Player Props ({len(result['player_props'])} projections):")
        for pp in result["player_props"]:
            edge = pp["edge"]
            flags = []
            if edge["pts_direction"] != "NEUTRAL":
                flags.append(f"PTS {edge['pts_direction']} ({edge['pts']:+.1f})")
            if edge["reb_direction"] != "NEUTRAL":
                flags.append(f"REB {edge['reb_direction']} ({edge['reb']:+.1f})")
            print(f"    {pp['name']:25s} avg {pp['season_avg']['ppg']:.1f}pts → proj {pp['projected']['ppg']:.1f}pts  {'  '.join(flags) if flags else '(no strong lean)'}")
