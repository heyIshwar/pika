"""Configurable relative date presets for agent dependencies."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DATE_PRESETS = frozenset({
    "yesterday",
    "today",
    "this_week",
    "this_month",
    "last_7_days",
    "last_30_days",
})

_PRESET_ALIASES = {
    "thisweek": "this_week",
    "thismonth": "this_month",
    "last7days": "last_7_days",
    "last30days": "last_30_days",
    "last_week": "last_7_days",
    "last_month": "last_30_days",
}


def _timezone(tz_name: str | None = None) -> ZoneInfo:
    name = tz_name or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def day_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime(day.year, day.month, day.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def month_bounds_utc(year: int, month: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def week_bounds_utc(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    monday = day - timedelta(days=day.weekday())
    start_local = datetime(monday.year, monday.month, monday.day, tzinfo=tz)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def created_at_range_filter(start_utc: datetime, end_utc: datetime, field: str = "createdAt") -> dict:
    """Mongo-style range filter for a timestamp field."""
    return {field: {"$gte": _iso_utc(start_utc), "$lt": _iso_utc(end_utc)}}


def sql_between_filter(start_utc: datetime, end_utc: datetime, column: str = "created_at") -> dict:
    return {"column": column, "gte": _iso_utc(start_utc), "lt": _iso_utc(end_utc)}


def _normalize_preset(preset: str) -> str:
    key = re.sub(r"[\s-]+", "_", (preset or "").strip().lower())
    return _PRESET_ALIASES.get(key, key)


def resolve_date_preset(
    preset: str,
    *,
    tz_name: str | None = None,
    now: datetime | None = None,
) -> tuple[dict, str]:
    """Return (filter dict, human label) for a relative date preset."""
    tz = _timezone(tz_name)
    key = _normalize_preset(preset)
    if key not in DATE_PRESETS:
        valid = ", ".join(sorted(DATE_PRESETS))
        raise ValueError(f"unknown date_preset {preset!r}; use one of: {valid}")

    now_local = (now or datetime.now(tz)).astimezone(tz)
    today = now_local.date()

    if key == "yesterday":
        d = today - timedelta(days=1)
        start, end = day_bounds_utc(d, tz)
        return created_at_range_filter(start, end), f"{d.isoformat()} (yesterday)"

    if key == "today":
        start, end = day_bounds_utc(today, tz)
        return created_at_range_filter(start, end), f"{today.isoformat()} (today)"

    if key == "this_week":
        start, end = week_bounds_utc(today, tz)
        monday = today - timedelta(days=today.weekday())
        return created_at_range_filter(start, end), f"week of {monday.isoformat()} (this week)"

    if key == "this_month":
        start, end = month_bounds_utc(today.year, today.month, tz)
        return created_at_range_filter(start, end), now_local.strftime("%B %Y (this month)")

    if key == "last_7_days":
        end = now_local.astimezone(timezone.utc)
        start = end - timedelta(days=7)
        return created_at_range_filter(start, end), "the last 7 days"

    if key == "last_30_days":
        end = now_local.astimezone(timezone.utc)
        start = end - timedelta(days=30)
        return created_at_range_filter(start, end), "the last 30 days"

    raise ValueError(f"unhandled date_preset {key!r}")


def build_relative_date_context(tz_name: str | None = None, now: datetime | None = None) -> dict[str, str]:
    tz = _timezone(tz_name)
    now_local = (now or datetime.now(tz)).astimezone(tz)
    today = now_local.date()
    return {
        "current_datetime": now_local.strftime("%Y-%m-%d %H:%M %Z"),
        "today_date": today.isoformat(),
        "yesterday_date": (today - timedelta(days=1)).isoformat(),
        "this_month_label": now_local.strftime("%B %Y"),
        "date_presets": ", ".join(sorted(DATE_PRESETS)),
    }
