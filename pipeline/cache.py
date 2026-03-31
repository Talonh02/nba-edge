"""
Cache management for NBA Edge.
Stats are cached and only re-fetched when stale (>12h by default).
Odds and schedule are always fetched fresh.
"""
import json
import os
from datetime import datetime, timezone

# ESPN uses different abbreviations than nba_api for some teams
ESPN_TO_NBA = {
    "NY": "NYK",
    "NO": "NOP",
    "GS": "GSW",
    "SA": "SAS",
    "UTAH": "UTA",
    "WSH": "WAS",
    "PHO": "PHX",
}

def normalize_abbr(abbr):
    """Convert any team abbreviation to the nba_api standard."""
    return ESPN_TO_NBA.get(abbr, abbr)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
NIGHTLY_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "nightly")
TIMESTAMPS_FILE = os.path.join(CACHE_DIR, "last_updated.json")


def ensure_dirs():
    """Create cache and nightly directories if they don't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = os.path.join(NIGHTLY_DIR, today)
    os.makedirs(today_dir, exist_ok=True)
    os.makedirs(os.path.join(today_dir, "insights"), exist_ok=True)
    return today_dir


def get_today_dir():
    """Return today's nightly data directory path."""
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(NIGHTLY_DIR, today)


def load_timestamps():
    """Load the last-updated timestamps for each data source."""
    if os.path.exists(TIMESTAMPS_FILE):
        with open(TIMESTAMPS_FILE) as f:
            return json.load(f)
    return {}


def update_timestamp(source_name):
    """Record that a data source was just refreshed."""
    timestamps = load_timestamps()
    timestamps[source_name] = datetime.now(timezone.utc).isoformat()
    with open(TIMESTAMPS_FILE, "w") as f:
        json.dump(timestamps, f, indent=2)


def needs_refresh(source_name, max_age_hours=12):
    """Check if a cached data source is stale and needs re-fetching."""
    timestamps = load_timestamps()
    last = timestamps.get(source_name)
    if not last:
        return True  # never fetched
    last_dt = datetime.fromisoformat(last)
    age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
    return age_hours > max_age_hours


def save_cached(source_name, data):
    """Save data to cache and update the timestamp."""
    ensure_dirs()
    filepath = os.path.join(CACHE_DIR, f"{source_name}.json")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    update_timestamp(source_name)
    print(f"  Cached: {source_name} ({filepath})")


def load_cached(source_name):
    """Load data from cache. Returns None if not cached."""
    filepath = os.path.join(CACHE_DIR, f"{source_name}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return None


def save_nightly(filename, data):
    """Save data to tonight's nightly directory."""
    today_dir = ensure_dirs()
    filepath = os.path.join(today_dir, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: {filepath}")


def load_nightly(filename):
    """Load data from tonight's nightly directory."""
    filepath = os.path.join(get_today_dir(), filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return None
