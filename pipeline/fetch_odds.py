"""
Fetch current NBA odds from The Odds API.
Always fetches fresh — odds are real-time.
Free tier: 500 requests/month.
"""
import os
import requests
from dotenv import load_dotenv
from cache import ensure_dirs, save_nightly

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"


def american_to_implied_prob(odds):
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def fetch_odds():
    """Pull NBA odds from The Odds API across all available books."""
    ensure_dirs()

    if not ODDS_API_KEY:
        print("  WARNING: No ODDS_API_KEY in .env — skipping odds fetch.")
        print("  Sign up free at the-odds-api.com and add your key to .env")
        # save empty odds so downstream scripts don't break
        save_nightly("odds.json", {"games": [], "note": "No API key configured"})
        return []

    print("Fetching odds from The Odds API...")

    # fetch all three market types
    all_odds = {}

    for market in ["h2h", "spreads", "totals"]:
        resp = requests.get(ODDS_URL, params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": market,
            "oddsFormat": "american",
        })
        resp.raise_for_status()

        # check remaining API credits (in response headers)
        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")

        games_data = resp.json()

        for game in games_data:
            game_key = game["id"]
            if game_key not in all_odds:
                all_odds[game_key] = {
                    "id": game["id"],
                    "home_team": game["home_team"],
                    "away_team": game["away_team"],
                    "commence_time": game["commence_time"],
                    "markets": {},
                }

            # parse bookmaker odds for this market
            market_data = []
            for bookmaker in game.get("bookmakers", []):
                book_name = bookmaker["title"]
                for mkt in bookmaker.get("markets", []):
                    for outcome in mkt.get("outcomes", []):
                        entry = {
                            "book": book_name,
                            "name": outcome["name"],  # team name or "Over"/"Under"
                            "price": outcome["price"],  # American odds
                            "implied_prob": round(american_to_implied_prob(outcome["price"]), 4),
                        }
                        # spreads and totals have a "point" field
                        if "point" in outcome:
                            entry["point"] = outcome["point"]
                        market_data.append(entry)

            all_odds[game_key]["markets"][market] = market_data

    odds_list = list(all_odds.values())
    save_nightly("odds.json", {"games": odds_list})

    print(f"  Fetched odds for {len(odds_list)} games across {len(all_odds)} matchups.")
    print(f"  API credits remaining: {remaining} (used: {used})")
    return odds_list


if __name__ == "__main__":
    fetch_odds()
