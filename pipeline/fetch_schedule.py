"""
Fetch tonight's NBA games from the ESPN hidden API.
Always fetches fresh (no cache) — games/times can change.
"""
import requests
from datetime import datetime
from cache import ensure_dirs, save_nightly

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def fetch_schedule():
    """Pull tonight's NBA games from ESPN."""
    ensure_dirs()
    print("Fetching tonight's schedule from ESPN...")

    resp = requests.get(ESPN_SCOREBOARD)
    resp.raise_for_status()
    raw = resp.json()

    games = []
    for event in raw.get("events", []):
        competition = event["competitions"][0]
        # figure out home vs away
        home = away = None
        for team_entry in competition["competitors"]:
            info = {
                "id": team_entry["team"]["id"],
                "name": team_entry["team"]["displayName"],
                "abbreviation": team_entry["team"]["abbreviation"],
                "record": team_entry.get("records", [{}])[0].get("summary", ""),
                "score": team_entry.get("score", "0"),
            }
            if team_entry["homeAway"] == "home":
                home = info
            else:
                away = info

        game = {
            "game_id": event["id"],
            "date": event["date"],
            "status": event["status"]["type"]["description"],  # "Scheduled", "In Progress", "Final"
            "home": home,
            "away": away,
            "venue": competition.get("venue", {}).get("fullName", ""),
        }
        games.append(game)

    save_nightly("schedule.json", {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "game_count": len(games),
        "games": games,
    })

    if not games:
        print("  No NBA games tonight.")
    else:
        print(f"  Found {len(games)} games tonight:")
        for g in games:
            print(f"    {g['away']['abbreviation']} @ {g['home']['abbreviation']} — {g['status']}")

    return games


if __name__ == "__main__":
    fetch_schedule()
