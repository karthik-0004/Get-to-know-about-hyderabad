"""
Daily API Usage Counter
~~~~~~~~~~~~~~~~~~~~~~~~
Persists a simple JSON file: { "date": "YYYY-MM-DD", "count": N }
Auto-resets when the date changes (midnight rollover).

Thread-safe via a threading.Lock — fine for Django's dev server
and even moderate production use with gunicorn workers (file-level
locking would be needed for true multi-process safety, but SQLite
or a simple JSON works perfectly here).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date

# Store the counter file next to manage.py (backend/ directory)
_COUNTER_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "api_usage_counter.json"
)

_lock = threading.Lock()

DAILY_LIMIT = 15  # Production limit


def _today_str() -> str:
    return date.today().isoformat()


def _read() -> dict:
    """Read current counter state from disk."""
    try:
        with open(_COUNTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}

    # Auto-reset if the date has changed
    if data.get("date") != _today_str():
        data = {"date": _today_str(), "count": 0}
        _write(data)

    return data


def _write(data: dict) -> None:
    """Write counter state to disk."""
    with open(_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_usage() -> dict:
    """Return current usage info: { date, count, limit, limit_reached }."""
    with _lock:
        data = _read()
    return {
        "date": data["date"],
        "count": data["count"],
        "limit": DAILY_LIMIT,
        "limit_reached": data["count"] >= DAILY_LIMIT,
    }


def increment() -> dict:
    """Increment the counter by 1 and return updated usage info."""
    with _lock:
        data = _read()
        data["count"] += 1
        _write(data)
    return {
        "date": data["date"],
        "count": data["count"],
        "limit": DAILY_LIMIT,
        "limit_reached": data["count"] >= DAILY_LIMIT,
    }


def is_limit_reached() -> bool:
    """Check if the daily limit has been reached (without incrementing)."""
    with _lock:
        data = _read()
    return data["count"] >= DAILY_LIMIT
