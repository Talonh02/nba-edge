"""
Fetch NBA odds from Stake.com's internal GraphQL API.
No API key needed — uses cloudscraper to bypass Cloudflare.

Pulls: moneylines, spreads (handicaps), totals, team totals,
       halftime, quarters, and player props when available.

Odds are decimal format (European). Converter included.

Usage:
    python3 fetch_odds_stake.py
"""
import json
import cloudscraper
from datetime import datetime
from cache import ensure_dirs, save_nightly


# --- Constants ---
API_URL = "https://stake.com/_api/graphql"
BASKETBALL_SPORT_ID = "285d2c11-61ff-4d65-97e8-1bad9fdfa2c0"


def get_scraper():
    """Create a cloudscraper session with Stake headers."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "darwin", "desktop": True}
    )
    scraper.headers.update({
        "Origin": "https://stake.com",
        "Referer": "https://stake.com/",
        "x-language": "en",
        "Content-Type": "application/json",
    })
    return scraper


def decimal_to_american(decimal_odds):
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1) * 100)
    else:
        return round(-100 / (decimal_odds - 1))


def decimal_to_implied_prob(decimal_odds):
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 0:
        return 0
    return round(1 / decimal_odds, 4)


def stake_query(scraper, query, variables=None):
    """Run a GraphQL query against Stake's API."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = scraper.post(API_URL, json=payload, timeout=15)
    data = resp.json()
    if "errors" in data:
        print(f"  GraphQL errors: {data['errors']}")
    return data


# --- Fixture list query (upcoming + live) ---

FIXTURE_LIST_QUERY = """
query {
  sport(sportId: "%s") {
    fixtureList(type: upcoming, limit: 50, offset: 0) {
      id
      slug
      status
      marketCount(status: [active, suspended])
      data {
        ... on SportFixtureDataMatch {
          startTime
          competitors { name extId abbreviation __typename }
          __typename
        }
        __typename
      }
      tournament { name slug __typename }
      __typename
    }
    __typename
  }
}
""" % BASKETBALL_SPORT_ID

LIVE_FIXTURE_QUERY = """
query {
  sport(sportId: "%s") {
    tournamentList(type: live, limit: 50) {
      name
      slug
      fixtureList(type: live) {
        id
        slug
        status
        marketCount(status: [active, suspended])
        data {
          ... on SportFixtureDataMatch {
            startTime
            competitors { name extId abbreviation __typename }
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
""" % BASKETBALL_SPORT_ID


def fixture_markets_query(fixture_id):
    """Build query to get ALL markets for a specific fixture."""
    return """
query {
  sportFixture(fixtureId: "%s") {
    id
    slug
    status
    marketCount(status: [active, suspended])
    data {
      ... on SportFixtureDataMatch {
        startTime
        competitors { name extId abbreviation __typename }
        __typename
      }
      __typename
    }
    groups(status: [active, suspended]) {
      name
      translation
      templates {
        markets {
          id
          name
          status
          specifiers
          outcomes {
            id
            name
            odds
            active
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
""" % fixture_id


def parse_markets(fixture_data):
    """
    Parse all markets from a fixture into a clean dict.
    Returns dict with keys: moneyline, spreads, totals,
    team_totals, halftime, quarters, combos, other
    """
    result = {
        "moneyline": None,
        "spreads": [],
        "totals": [],
        "team_totals": [],
        "halftime": [],
        "quarters": [],
        "combos": [],
        "other": [],
    }

    for group in fixture_data.get("groups", []):
        group_name = group.get("name", "")
        for template in group.get("templates", []):
            for market in template.get("markets", []):
                m_name = market.get("name", "")
                specs = market.get("specifiers", "")
                outcomes = []
                for o in market.get("outcomes", []):
                    outcomes.append({
                        "name": o["name"],
                        "odds_decimal": o["odds"],
                        "odds_american": decimal_to_american(o["odds"]),
                        "implied_prob": decimal_to_implied_prob(o["odds"]),
                        "active": o.get("active", True),
                    })

                entry = {
                    "market_name": m_name,
                    "group": group_name,
                    "specifiers": specs,
                    "status": market.get("status", "unknown"),
                    "outcomes": outcomes,
                }

                # Categorize the market
                if m_name == "Winner (Incl. Overtime)" and group_name == "winner":
                    result["moneyline"] = entry
                elif "Handicap" in m_name and group_name == "Handicap":
                    result["spreads"].append(entry)
                elif m_name == "Total (Incl. Overtime)" and group_name == "Total":
                    result["totals"].append(entry)
                elif "Total" in m_name and group_name == "points":
                    result["team_totals"].append(entry)
                elif "Half" in m_name or group_name == "half":
                    result["halftime"].append(entry)
                elif "Quarter" in m_name or group_name == "quarters":
                    result["quarters"].append(entry)
                elif group_name == "combo":
                    result["combos"].append(entry)
                else:
                    # avoid duplicates from 'main' and 'threeway' groups
                    if group_name in ("main", "threeway"):
                        continue
                    result["other"].append(entry)

    return result


def fetch_odds_stake():
    """
    Main function: fetch all NBA odds from Stake.com.
    Returns list of game dicts with full market data.
    """
    ensure_dirs()
    scraper = get_scraper()

    print("Fetching NBA odds from Stake.com...")

    # --- Step 1: Get upcoming NBA fixtures ---
    upcoming_data = stake_query(scraper, FIXTURE_LIST_QUERY)
    upcoming_fixtures = (
        upcoming_data.get("data", {}).get("sport", {}).get("fixtureList", [])
    )

    # Filter for NBA only
    nba_upcoming = [
        f for f in upcoming_fixtures
        if f.get("tournament", {}).get("slug") == "nba"
    ]

    # --- Step 2: Get live NBA fixtures ---
    live_data = stake_query(scraper, LIVE_FIXTURE_QUERY)
    live_tournaments = (
        live_data.get("data", {}).get("sport", {}).get("tournamentList", [])
    )
    nba_live = []
    for t in live_tournaments:
        if t.get("slug") == "nba":
            for f in t.get("fixtureList", []):
                f["_live"] = True
                nba_live.append(f)

    all_nba = nba_live + nba_upcoming
    print(f"  Found {len(nba_live)} live + {len(nba_upcoming)} upcoming NBA games")

    if not all_nba:
        print("  No NBA games found.")
        save_nightly("odds_stake.json", {"games": [], "source": "stake.com"})
        return []

    # --- Step 3: For each NBA game, pull all markets ---
    games = []
    for fixture in all_nba:
        comps = fixture.get("data", {}).get("competitors", [])
        if len(comps) < 2:
            continue

        home_team = comps[0]["name"]
        away_team = comps[1]["name"]
        fid = fixture["id"]
        is_live = fixture.get("_live", False)

        # Pull full market data for this fixture
        market_data = stake_query(scraper, fixture_markets_query(fid))
        fx = market_data.get("data", {}).get("sportFixture")

        if not fx:
            print(f"  Could not load markets for {home_team} vs {away_team}")
            continue

        markets = parse_markets(fx)
        market_count = fx.get("marketCount", 0)

        game_obj = {
            "fixture_id": fid,
            "home_team": home_team,
            "away_team": away_team,
            "start_time": fixture.get("data", {}).get("startTime", ""),
            "is_live": is_live,
            "market_count": market_count,
            "source": "stake.com",
            "markets": markets,
        }

        # Print summary
        ml = markets.get("moneyline")
        if ml:
            outcomes = ml["outcomes"]
            if len(outcomes) >= 2:
                h_odds = outcomes[0]["odds_american"]
                a_odds = outcomes[1]["odds_american"]
                h_sign = "+" if h_odds > 0 else ""
                a_sign = "+" if a_odds > 0 else ""
                live_tag = " [LIVE]" if is_live else ""
                print(
                    f"  {home_team} ({h_sign}{h_odds}) vs "
                    f"{away_team} ({a_sign}{a_odds}) "
                    f"— {market_count} markets{live_tag}"
                )

        games.append(game_obj)

    # --- Step 4: Save ---
    output = {
        "games": games,
        "source": "stake.com",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "game_count": len(games),
    }
    save_nightly("odds_stake.json", output)
    print(f"  Saved odds for {len(games)} NBA games to odds_stake.json")

    return games


if __name__ == "__main__":
    fetch_odds_stake()
