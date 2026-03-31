"""
Fetch team and player stats from nba_api.
Cached — only re-fetches if data is >12 hours stale.
Pulls: general, advanced, Four Factors, last-10 games, scoring breakdown.
"""
import time
from cache import needs_refresh, save_cached, load_cached
from nba_api.stats.endpoints import LeagueDashTeamStats, LeagueDashPlayerStats
from nba_api.stats.static import teams as nba_teams_static


def build_team_id_map():
    """Build TEAM_ID → abbreviation lookup from nba_api static data."""
    return {t["id"]: t["abbreviation"] for t in nba_teams_static.get_teams()}


TEAM_ID_TO_ABBR = build_team_id_map()


def safe_get(endpoint_class, **kwargs):
    """Call an nba_api endpoint with rate limiting."""
    result = endpoint_class(**kwargs)
    time.sleep(0.6)
    return result.get_normalized_dict()


def compute_league_ranks(teams, stats_to_rank):
    """
    Compute league rank (1-30) for specified stats across all teams.
    stats_to_rank: list of (stat_key, higher_is_better) tuples
    Adds "{stat_key}_rank" to each team dict.
    """
    for stat_key, higher_is_better in stats_to_rank:
        # get all teams that have this stat
        vals = []
        for abbr, t in teams.items():
            val = t.get(stat_key)
            if val is not None:
                vals.append((abbr, val))

        # sort: rank 1 = best
        vals.sort(key=lambda x: x[1], reverse=higher_is_better)
        for rank, (abbr, _) in enumerate(vals, 1):
            teams[abbr][f"{stat_key}_rank"] = rank


def fetch_team_stats():
    """
    Fetch comprehensive league-wide team stats.
    Returns dict keyed by team abbreviation with rich data.
    """
    if not needs_refresh("team_stats"):
        print("  Team stats cached and fresh. Skipping fetch.")
        return load_cached("team_stats")

    teams = {}

    # --- General stats (season totals) ---
    print("  Fetching team stats (general)...")
    gen = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Base",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    for row in gen["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"], "???")
        teams[abbr] = {
            "team_id": row["TEAM_ID"],
            "team_name": row["TEAM_NAME"],
            "abbreviation": abbr,
            "gp": row["GP"], "wins": row["W"], "losses": row["L"], "win_pct": row["W_PCT"],
            "ppg": row["PTS"], "rpg": row["REB"], "apg": row["AST"],
            "spg": row["STL"], "bpg": row["BLK"], "tov_pg": row["TOV"],
            "fg_pct": row["FG_PCT"], "fg3_pct": row["FG3_PCT"], "ft_pct": row["FT_PCT"],
            "oreb_pg": row["OREB"], "dreb_pg": row["DREB"],
            "plus_minus": row["PLUS_MINUS"],
        }

    # --- Advanced stats ---
    print("  Fetching team stats (advanced)...")
    adv = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Advanced",
        season="2025-26", season_type_all_star="Regular Season",
    )
    for row in adv["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr].update({
                "off_rating": row.get("OFF_RATING"),
                "def_rating": row.get("DEF_RATING"),
                "net_rating": row.get("NET_RATING"),
                "pace": row.get("PACE"),
                "ts_pct": row.get("TS_PCT"),
                "ast_pct": row.get("AST_PCT"),
                "ast_to_tov": row.get("AST_TO"),
                "ast_ratio": row.get("AST_RATIO"),
                "oreb_pct": row.get("OREB_PCT"),
                "dreb_pct": row.get("DREB_PCT"),
                "reb_pct": row.get("REB_PCT"),
                "efg_pct": row.get("EFG_PCT"),
                "tov_pct": row.get("TM_TOV_PCT"),
                "pie": row.get("PIE"),
            })

    # --- Four Factors ---
    print("  Fetching team stats (Four Factors)...")
    ff = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Four Factors",
        season="2025-26", season_type_all_star="Regular Season",
    )
    for row in ff["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr]["four_factors"] = {
                "efg_pct": row.get("EFG_PCT"),
                "fta_rate": row.get("FTA_RATE"),
                "tm_tov_pct": row.get("TM_TOV_PCT"),
                "oreb_pct": row.get("OREB_PCT"),
                "opp_efg_pct": row.get("OPP_EFG_PCT"),
                "opp_fta_rate": row.get("OPP_FTA_RATE"),
                "opp_tov_pct": row.get("OPP_TOV_PCT"),
                "opp_oreb_pct": row.get("OPP_OREB_PCT"),
            }

    # --- Scoring breakdown ---
    print("  Fetching team stats (scoring)...")
    scoring = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Scoring",
        season="2025-26", season_type_all_star="Regular Season",
    )
    for row in scoring["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr]["scoring"] = {
                "pct_fga_2pt": row.get("PCT_FGA_2PT"),
                "pct_fga_3pt": row.get("PCT_FGA_3PT"),
                "pct_pts_2pt": row.get("PCT_PTS_2PT"),
                "pct_pts_3pt": row.get("PCT_PTS_3PT"),
                "pct_pts_midrange_2pt": row.get("PCT_PTS_2PT_MR"),
                "pct_pts_fb": row.get("PCT_PTS_FB"),
                "pct_pts_ft": row.get("PCT_PTS_FT"),
                "pct_pts_paint": row.get("PCT_PTS_PAINT"),
                "pct_pts_off_tov": row.get("PCT_PTS_OFF_TOV"),
                "pct_assisted_2pt": row.get("PCT_AST_2PM"),
                "pct_assisted_3pt": row.get("PCT_AST_3PM"),
                "pct_unassisted_2pt": row.get("PCT_UAST_2PM"),
                "pct_unassisted_3pt": row.get("PCT_UAST_3PM"),
            }

    # --- Opponent stats (defensive profile) ---
    print("  Fetching opponent stats...")
    opp = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Opponent",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    for row in opp["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr]["defense"] = {
                "opp_ppg": row.get("OPP_PTS", row.get("PTS")),
                "opp_fg_pct": row.get("OPP_FG_PCT", row.get("FG_PCT")),
                "opp_fg3_pct": row.get("OPP_FG3_PCT", row.get("FG3_PCT")),
                "opp_ft_pct": row.get("OPP_FT_PCT", row.get("FT_PCT")),
                "opp_rpg": row.get("OPP_REB", row.get("REB")),
                "opp_apg": row.get("OPP_AST", row.get("AST")),
                "opp_tov_pg": row.get("OPP_TOV", row.get("TOV")),
                "opp_stl": row.get("OPP_STL", row.get("STL")),
                "opp_blk": row.get("OPP_BLK", row.get("BLK")),
            }

    # --- Last 10 games (general + advanced) ---
    print("  Fetching last 10 games stats...")
    l10_gen = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Base",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame", last_n_games=10,
    )
    l10_adv = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Advanced",
        season="2025-26", season_type_all_star="Regular Season",
        last_n_games=10,
    )
    for row in l10_gen["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr]["last_10"] = {
                "wins": row["W"], "losses": row["L"],
                "ppg": row["PTS"], "rpg": row["REB"], "apg": row["AST"],
                "fg_pct": row["FG_PCT"], "fg3_pct": row["FG3_PCT"],
                "plus_minus": row["PLUS_MINUS"],
            }
    for row in l10_adv["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams and "last_10" in teams[abbr]:
            teams[abbr]["last_10"].update({
                "off_rating": row.get("OFF_RATING"),
                "def_rating": row.get("DEF_RATING"),
                "net_rating": row.get("NET_RATING"),
                "pace": row.get("PACE"),
            })

    # --- Last 5 games ---
    print("  Fetching last 5 games stats...")
    l5_gen = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Base",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame", last_n_games=5,
    )
    l5_adv = safe_get(LeagueDashTeamStats,
        measure_type_detailed_defense="Advanced",
        season="2025-26", season_type_all_star="Regular Season",
        last_n_games=5,
    )
    for row in l5_gen["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams:
            teams[abbr]["last_5"] = {
                "wins": row["W"], "losses": row["L"],
                "ppg": row["PTS"], "rpg": row["REB"], "apg": row["AST"],
                "fg_pct": row["FG_PCT"], "fg3_pct": row["FG3_PCT"],
                "plus_minus": row["PLUS_MINUS"],
            }
    for row in l5_adv["LeagueDashTeamStats"]:
        abbr = TEAM_ID_TO_ABBR.get(row["TEAM_ID"])
        if abbr and abbr in teams and "last_5" in teams[abbr]:
            teams[abbr]["last_5"].update({
                "off_rating": row.get("OFF_RATING"),
                "def_rating": row.get("DEF_RATING"),
                "net_rating": row.get("NET_RATING"),
            })

    # --- Compute league ranks ---
    print("  Computing league ranks...")
    compute_league_ranks(teams, [
        ("off_rating", True), ("def_rating", False), ("net_rating", True),
        ("pace", True), ("ppg", True), ("rpg", True), ("apg", True),
        ("fg_pct", True), ("fg3_pct", True), ("ft_pct", True),
        ("ts_pct", True), ("efg_pct", True), ("tov_pct", False),
        ("oreb_pct", True), ("dreb_pct", True),
        ("spg", True), ("bpg", True), ("tov_pg", False),
        ("win_pct", True), ("plus_minus", True),
    ])

    save_cached("team_stats", teams)
    print(f"  Fetched comprehensive stats for {len(teams)} teams.")
    return teams


def fetch_player_stats():
    """
    Fetch league-wide player stats with base + advanced.
    Returns list of player dicts.
    """
    if not needs_refresh("player_stats"):
        print("  Player stats cached and fresh. Skipping fetch.")
        return load_cached("player_stats")

    print("  Fetching player stats (base per-game)...")
    base = safe_get(LeagueDashPlayerStats,
        measure_type_detailed_defense="Base",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )

    print("  Fetching player stats (advanced)...")
    adv = safe_get(LeagueDashPlayerStats,
        measure_type_detailed_defense="Advanced",
        season="2025-26", season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )

    players = {}
    for row in base["LeagueDashPlayerStats"]:
        pid = str(row["PLAYER_ID"])
        team_abbr = TEAM_ID_TO_ABBR.get(row.get("TEAM_ID"), "???")
        players[pid] = {
            "player_id": row["PLAYER_ID"],
            "name": row.get("PLAYER_NAME", row.get("PLAYER", "Unknown")),
            "team": team_abbr,
            "gp": row["GP"], "min": row["MIN"],
            "ppg": row["PTS"], "rpg": row["REB"], "apg": row["AST"],
            "spg": row["STL"], "bpg": row["BLK"], "tov": row["TOV"],
            "fg_pct": row["FG_PCT"], "fg3_pct": row["FG3_PCT"], "ft_pct": row["FT_PCT"],
            "fgm": row["FGM"], "fga": row["FGA"],
            "fg3m": row["FG3M"], "fg3a": row["FG3A"],
            "plus_minus": row["PLUS_MINUS"],
        }

    for row in adv["LeagueDashPlayerStats"]:
        pid = str(row["PLAYER_ID"])
        if pid in players:
            players[pid].update({
                "ts_pct": row.get("TS_PCT"),
                "usg_pct": row.get("USG_PCT"),
                "off_rating": row.get("OFF_RATING"),
                "def_rating": row.get("DEF_RATING"),
                "net_rating": row.get("NET_RATING"),
                "ast_pct": row.get("AST_PCT"),
                "reb_pct": row.get("REB_PCT"),
                "pie": row.get("PIE"),
            })

    player_list = list(players.values())
    save_cached("player_stats", player_list)
    print(f"  Fetched stats for {len(player_list)} players.")
    return player_list


def fetch_all_stats():
    """Run both team and player stat fetches."""
    print("Fetching NBA stats...")
    teams = fetch_team_stats()
    players = fetch_player_stats()
    return teams, players


if __name__ == "__main__":
    fetch_all_stats()
