#!/usr/bin/env python3
"""
NBA Edge — Run the full pipeline in one command.

Usage:
    python3 run.py           # fetch + analyze + dashboard + open browser
    python3 run.py --refresh  # force re-fetch all stats (ignore cache)
    python3 run.py --no-open  # don't auto-open browser
"""
import sys
import os
import subprocess
import platform

# make sure pipeline/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pipeline"))

from cache import ensure_dirs


def open_in_browser(filepath):
    """Open an HTML file in the default browser."""
    if platform.system() == "Darwin":
        subprocess.run(["open", filepath])
    elif platform.system() == "Linux":
        subprocess.run(["xdg-open", filepath])
    else:
        os.startfile(filepath)  # Windows


def main():
    force_refresh = "--refresh" in sys.argv
    no_open = "--no-open" in sys.argv

    ensure_dirs()

    # if force refresh, clear cache timestamps
    if force_refresh:
        from cache import TIMESTAMPS_FILE
        if os.path.exists(TIMESTAMPS_FILE):
            os.remove(TIMESTAMPS_FILE)
            print("Cache cleared — will re-fetch all stats.\n")

    # 1. schedule (always fresh)
    print("=" * 50)
    print("STEP 1: Fetching tonight's schedule")
    print("=" * 50)
    from fetch_schedule import fetch_schedule
    games = fetch_schedule()
    if not games:
        print("\nNo games tonight. Nothing to analyze.")
        return

    # 2. stats (cache-aware — skips if fresh)
    print("\n" + "=" * 50)
    print("STEP 2: Fetching team & player stats")
    print("=" * 50)
    from fetch_stats import fetch_all_stats
    fetch_all_stats()

    # 2b. update Elo from recent game results
    print("\n" + "=" * 50)
    print("STEP 2b: Updating Elo ratings from game results")
    print("=" * 50)
    from elo import update_elo_from_results
    update_elo_from_results()

    # 3a. The Odds API (if key configured)
    print("\n" + "=" * 50)
    print("STEP 3a: Fetching odds (The Odds API)")
    print("=" * 50)
    from fetch_odds import fetch_odds
    fetch_odds()

    # 3b. Stake.com odds (always free, no key needed)
    print("\n" + "=" * 50)
    print("STEP 3b: Fetching odds (Stake.com)")
    print("=" * 50)
    try:
        from fetch_odds_stake import fetch_odds_stake
        fetch_odds_stake()
    except ImportError:
        print("  Stake fetcher not available (missing cloudscraper?)")
        print("  Install with: python3 -m pip install cloudscraper")
    except Exception as e:
        print(f"  Stake fetch failed: {e}")
        print("  Continuing without Stake odds...")

    # 4. analysis (crunch + statistical model)
    print("\n" + "=" * 50)
    print("STEP 4: Running analysis")
    print("=" * 50)
    from crunch import run_analysis
    run_analysis()

    # 5. generate HTML dashboard
    print("\n" + "=" * 50)
    print("STEP 5: Generating dashboard")
    print("=" * 50)
    from dashboard import generate_dashboard
    html_path = generate_dashboard()

    if html_path:
        print(f"\n  Dashboard: {html_path}")
        if not no_open:
            print("  Opening in browser...")
            open_in_browser(html_path)

    print("\n" + "=" * 50)
    print("DONE.")
    print("=" * 50)


if __name__ == "__main__":
    main()
