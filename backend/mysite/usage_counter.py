"""
Daily API Usage Counter (database-backed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Uses the DailyAPICounter Django model so the counter survives
redeployments and works correctly with multi-process servers.
"""

from __future__ import annotations

from django.utils import timezone

DAILY_LIMIT = 15  # Production limit


def _today():
    return timezone.now().date()


def get_usage() -> dict:
    """Return current usage info: { date, count, limit, limit_reached }."""
    from .models import DailyAPICounter
    today = _today()
    obj, _ = DailyAPICounter.objects.get_or_create(date=today, defaults={"count": 0})
    return {
        "date": str(today),
        "count": obj.count,
        "limit": DAILY_LIMIT,
        "limit_reached": obj.count >= DAILY_LIMIT,
    }


def increment() -> dict:
    """Increment the counter by 1 and return updated usage info."""
    from .models import DailyAPICounter
    today = _today()
    obj, _ = DailyAPICounter.objects.get_or_create(date=today, defaults={"count": 0})
    obj.count += 1
    obj.save()
    return {
        "date": str(today),
        "count": obj.count,
        "limit": DAILY_LIMIT,
        "limit_reached": obj.count >= DAILY_LIMIT,
    }


def is_limit_reached() -> bool:
    """Check if the daily limit has been reached (without incrementing)."""
    from .models import DailyAPICounter
    today = _today()
    obj, _ = DailyAPICounter.objects.get_or_create(date=today, defaults={"count": 0})
    return obj.count >= DAILY_LIMIT
