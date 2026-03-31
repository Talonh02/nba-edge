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
import requests
import time
from datetime import datetime, timedelta
from cache import load_cached, save_cached, load_timestamps, update_timestamp, normalize_abbr

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


# ============================================================
# ELO AUTO-UPDATE: pull completed games and update ratings
# ============================================================

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# rough season start — don't look further back than this
SEASON_START = "2025-10-20"


def get_completed_games(date_str):
    """
    Pull completed NBA games for a specific date from ESPN.
    date_str: "YYYY-MM-DD"
    Returns list of {home, away, home_score, away_score, winner} dicts.
    """
    espn_date = date_str.replace("-", "")  # ESPN wants YYYYMMDD
    try:
        resp = requests.get(ESPN_SCOREBOARD, params={"dates": espn_date}, timeout=10)
        resp.raise_for_status()
    except Exception:
        return []

    results = []
    for event in resp.json().get("events", []):
        status = event["status"]["type"]["description"]
        if status != "Final":
            continue

        comp = event["competitions"][0]
        home = away = None
        for t in comp["competitors"]:
            info = {
                "abbr": normalize_abbr(t["team"]["abbreviation"]),
                "score": int(t.get("score", 0)),
                "winner": t.get("winner", False),
            }
            if t["homeAway"] == "home":
                home = info
            else:
                away = info

        if home and away and (home["score"] > 0 or away["score"] > 0):
            results.append({
                "date": date_str,
                "home": home["abbr"],
                "away": away["abbr"],
                "home_score": home["score"],
                "away_score": away["score"],
            })

    return results


def update_elo_from_results():
    """
    Check when Elo was last updated, pull all completed games since then,
    and update ratings for each one in chronological order.

    Called automatically at the start of each run.
    """
    ratings = load_ratings()

    # figure out when we last updated
    timestamps = load_timestamps()
    last_elo_update = timestamps.get("elo_game_update")

    if last_elo_update:
        # start from the day after the last update
        last_date = datetime.fromisoformat(last_elo_update).date()
        start_date = last_date + timedelta(days=1)
    else:
        # never updated — but we seeded from net ratings, so we don't need
        # to replay the whole season. start from 3 days ago to catch up.
        start_date = (datetime.now().date() - timedelta(days=3))

    today = datetime.now().date()

    # don't process today — games might still be in progress
    end_date = today - timedelta(days=1)

    if start_date > end_date:
        print("  Elo ratings are up to date.")
        return ratings

    print(f"  Updating Elo from {start_date} to {end_date}...")

    total_games = 0
    current = start_date
    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        games = get_completed_games(date_str)

        for game in games:
            home = game["home"]
            away = game["away"]
            h_score = game["home_score"]
            a_score = game["away_score"]
            margin = abs(h_score - a_score)

            if h_score > a_score:
                update_ratings(ratings, winner=home, loser=away, margin=margin)
            else:
                update_ratings(ratings, winner=away, loser=home, margin=margin)
            total_games += 1

        current += timedelta(days=1)
        time.sleep(0.3)  # be nice to ESPN

    # save updated ratings and record the update date
    save_cached("elo_ratings", ratings)
    # record that we've processed through end_date
    # store as ISO datetime at end of that day
    update_timestamp("elo_game_update")

    print(f"  Processed {total_games} games. Elo ratings updated through {end_date}.")
    return ratings


if __name__ == "__main__":
    print("Updating Elo ratings from game results...")
    ratings = update_elo_from_results()
    print("\nCurrent Elo Ratings:")
    for team, elo in get_all_ratings():
        print(f"  {team}: {elo:.0f}")
