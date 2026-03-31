"""
Elo rating system for NBA teams.
- K=20, margin-of-victory multiplier (MOVDA approach)
- Home court: +70 Elo points
- Back-to-back: -46 Elo points
- Rest advantage: +25 per extra day (up to 3)
- Ratings persist in cache and update as game results come in

Elo is mathematically equivalent to logistic regression (nicidob proof).
Hits ~67% accuracy — robust regardless of parameter tuning.
"""
import math
from cache import load_cached, save_cached

# constants from 538's published research
K = 20
HOME_ADVANTAGE = 70      # ~3.5 points
B2B_PENALTY = -46         # back-to-back fatigue
REST_BONUS_PER_DAY = 25   # per extra day of rest, up to 3
DENVER_HOME_BONUS = 15    # altitude
STARTING_ELO = 1500

# all 30 NBA teams
NBA_TEAMS = [
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
]


def load_ratings():
    """Load Elo ratings from cache, or seed from team stats if available."""
    cached = load_cached("elo_ratings")
    if cached:
        # check if they're all 1500 (unseeded) and we now have team stats
        all_default = all(v == STARTING_ELO for v in cached.values())
        if not all_default:
            return cached
        # try to seed from team stats
        team_stats = load_cached("team_stats")
        if team_stats:
            return seed_from_stats(team_stats)
        return cached

    # no cache at all — try to seed from stats
    team_stats = load_cached("team_stats")
    if team_stats:
        return seed_from_stats(team_stats)

    # no stats either — initialize flat
    ratings = {team: STARTING_ELO for team in NBA_TEAMS}
    save_cached("elo_ratings", ratings)
    print("  Initialized Elo ratings at 1500 for all teams.")
    return ratings


def seed_from_stats(team_stats):
    """
    Seed Elo ratings from current season net ratings.
    Each point of net rating ≈ 25 Elo points.
    This gives a much better starting point than flat 1500.
    """
    ratings = {}
    for abbr, stats in team_stats.items():
        net_rating = stats.get("net_rating")
        if net_rating is not None:
            # net_rating * 25 converts to Elo scale
            ratings[abbr] = round(STARTING_ELO + (net_rating * 25), 1)
        else:
            ratings[abbr] = STARTING_ELO

    # make sure all 30 teams are present
    for team in NBA_TEAMS:
        if team not in ratings:
            ratings[team] = STARTING_ELO

    save_cached("elo_ratings", ratings)
    print(f"  Seeded Elo ratings from net ratings for {len(ratings)} teams.")
    return ratings


def expected_score(rating_a, rating_b):
    """Expected win probability for team A against team B."""
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))


def mov_multiplier(margin, elo_diff):
    """
    Margin-of-victory multiplier (from MOVDA / 538).
    Adjusts K so blowouts move ratings more than close games,
    but with diminishing returns to avoid overreaction.
    """
    return math.log(abs(margin) + 1) * (2.2 / ((elo_diff * 0.001) + 2.2))


def update_ratings(ratings, winner, loser, margin, home_team=None):
    """
    Update Elo ratings after a game result.
    margin = winner's score - loser's score (always positive)
    """
    # apply home court to the prediction, not the update
    winner_elo = ratings.get(winner, STARTING_ELO)
    loser_elo = ratings.get(loser, STARTING_ELO)

    # expected score (without home court — we want raw skill update)
    exp_w = expected_score(winner_elo, loser_elo)

    # MOV multiplier
    elo_diff = abs(winner_elo - loser_elo)
    mov_mult = mov_multiplier(margin, elo_diff)

    # update
    shift = K * mov_mult * (1 - exp_w)
    ratings[winner] = winner_elo + shift
    ratings[loser] = loser_elo - shift

    return ratings


def predict_game(ratings, home_abbr, away_abbr, home_b2b=False, away_b2b=False,
                 home_rest_days=1, away_rest_days=1):
    """
    Predict a game using Elo ratings + contextual adjustments.
    Returns dict with win probabilities and projected spread.
    """
    home_elo = ratings.get(home_abbr, STARTING_ELO)
    away_elo = ratings.get(away_abbr, STARTING_ELO)

    # contextual adjustments
    home_adj = HOME_ADVANTAGE
    away_adj = 0

    # denver altitude bonus
    if home_abbr == "DEN":
        home_adj += DENVER_HOME_BONUS

    # back-to-back penalty
    if home_b2b:
        home_adj += B2B_PENALTY
    if away_b2b:
        away_adj += B2B_PENALTY

    # rest advantage (capped at 3 extra days)
    home_extra_rest = min(home_rest_days - 1, 3)
    away_extra_rest = min(away_rest_days - 1, 3)
    home_adj += home_extra_rest * REST_BONUS_PER_DAY
    away_adj += away_extra_rest * REST_BONUS_PER_DAY

    # adjusted Elo
    adj_home = home_elo + home_adj
    adj_away = away_elo + away_adj

    # win probability
    home_win_prob = expected_score(adj_home, adj_away)
    away_win_prob = 1 - home_win_prob

    # projected spread (rough: each 25 Elo points ≈ 1 point of spread)
    elo_diff = adj_home - adj_away
    projected_spread = -(elo_diff / 25)  # negative = home favored

    return {
        "home_team": home_abbr,
        "away_team": away_abbr,
        "home_elo": round(home_elo, 1),
        "away_elo": round(away_elo, 1),
        "home_elo_adjusted": round(adj_home, 1),
        "away_elo_adjusted": round(adj_away, 1),
        "home_win_prob": round(home_win_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "projected_spread": round(projected_spread, 1),  # from home perspective
        "adjustments": {
            "home_court": HOME_ADVANTAGE,
            "home_b2b": B2B_PENALTY if home_b2b else 0,
            "away_b2b": B2B_PENALTY if away_b2b else 0,
            "home_rest_bonus": home_extra_rest * REST_BONUS_PER_DAY,
            "away_rest_bonus": away_extra_rest * REST_BONUS_PER_DAY,
            "altitude": DENVER_HOME_BONUS if home_abbr == "DEN" else 0,
        },
    }


def get_all_ratings():
    """Return current Elo ratings sorted by rating (best to worst)."""
    ratings = load_ratings()
    sorted_teams = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    return sorted_teams


if __name__ == "__main__":
    ratings = load_ratings()
    print("\nCurrent Elo Ratings:")
    for team, elo in get_all_ratings():
        print(f"  {team}: {elo:.0f}")
