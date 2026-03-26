"""
Solar and Lunar Time Windows.

Solar Time Window (Lessons 7-9):
  - Based on Sun-outer-planet aspects (16 aspects)
  - 3-day window: day before, day of, day after the exact aspect

Lunar Time Window (Lessons 11-12):
  - Based on Moon-outer-planet aspects during market hours
  - 2-hour window: ±2 hours around exact aspect time
  - Only intraday aspects (during market hours 9:30-16:15 ET) are used
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Set, Optional
import pytz

from .ephemeris import sun_outer_aspects, moon_outer_aspects, ASPECTS_16


# ---------------------------------------------------------------------------
# Solar Time Windows
# ---------------------------------------------------------------------------

def compute_solar_time_windows(
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    Compute all 3-day Solar Time Windows between start_date and end_date.

    Each window entry:
      {window_dates: [day-1, day0, day+1], aspect_date: date,
       planet: str, aspect_deg: float, exact_datetime: datetime}

    Days in the window are only market days (Mon-Fri), but the book
    specifies calendar days offset from exact aspect day.
    """
    # Search ±5 days wider to catch windows that extend into range
    search_start = start_date - timedelta(days=5)
    search_end   = end_date   + timedelta(days=5)

    aspects = sun_outer_aspects(search_start, search_end)

    windows = []
    for asp in aspects:
        d = asp["date"]
        # 3-day window: day before, exact day, day after (market days only)
        day_before = _prev_market_day(d)
        day_after  = _next_market_day(d)

        window_dates = [day_before, d, day_after]
        # Only add if window overlaps requested range
        if any(start_date <= wd <= end_date for wd in window_dates):
            windows.append({
                "window_dates":   window_dates,
                "aspect_date":    d,
                "exact_datetime": asp["exact_datetime"],
                "planet":         asp["planet"],
                "aspect_deg":     asp["aspect_deg"],
            })

    windows.sort(key=lambda x: x["aspect_date"])
    return windows


def solar_window_dates_set(
    start_date: date,
    end_date: date,
) -> Set[date]:
    """Return a flat set of all dates that fall within any Solar Time Window."""
    windows = compute_solar_time_windows(start_date, end_date)
    dates = set()
    for w in windows:
        for d in w["window_dates"]:
            if start_date <= d <= end_date:
                dates.add(d)
    return dates


def is_in_solar_window(
    check_date: date,
    windows: List[Dict],
) -> bool:
    """Check if a date falls within any of the pre-computed solar windows."""
    for w in windows:
        if check_date in w["window_dates"]:
            return True
    return False


# ---------------------------------------------------------------------------
# Lunar Time Windows
# ---------------------------------------------------------------------------

def compute_lunar_time_windows(
    start_date: date,
    end_date: date,
    market_open_hour: int = 9,
    market_open_min: int = 30,
    market_close_hour: int = 16,
    market_close_min: int = 15,
) -> List[Dict]:
    """
    Compute all intraday Lunar Time Windows for trading days in range.

    A window is ±2 hours around the exact Moon-outer-planet aspect.
    Only aspects that occur during market hours are included.

    Each entry:
      {date, planet, aspect_deg, exact_datetime,
       window_start, window_end, market_open, market_close}
    """
    aspects = moon_outer_aspects(
        start_date, end_date,
        market_open_hour=market_open_hour,
        market_open_min=market_open_min,
        market_close_hour=market_close_hour,
        market_close_min=market_close_min,
    )

    windows = []
    for asp in aspects:
        # The 2-hour window must overlap with market hours
        market_open  = asp["exact_datetime"].replace(
            hour=market_open_hour, minute=market_open_min, second=0, microsecond=0)
        market_close = asp["exact_datetime"].replace(
            hour=market_close_hour, minute=market_close_min, second=0, microsecond=0)

        ws = max(asp["window_start"], market_open)
        we = min(asp["window_end"],   market_close)

        if ws < we:
            windows.append({
                "date":           asp["date"],
                "planet":         asp["planet"],
                "aspect_deg":     asp["aspect_deg"],
                "exact_datetime": asp["exact_datetime"],
                "window_start":   ws,
                "window_end":     we,
                "market_open":    market_open,
                "market_close":   market_close,
            })

    windows.sort(key=lambda x: x["exact_datetime"])
    return windows


def is_in_lunar_window(
    check_datetime: datetime,
    windows: List[Dict],
) -> Optional[Dict]:
    """
    Return the lunar window dict if check_datetime falls within any window,
    else return None.
    """
    for w in windows:
        if w["window_start"] <= check_datetime <= w["window_end"]:
            return w
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_market_day(d: date) -> bool:
    """Return True if date is Mon-Fri (simple weekday check, no holidays)."""
    return d.weekday() < 5


def _prev_market_day(d: date) -> date:
    """Return previous market day (Mon-Fri) before d."""
    d -= timedelta(days=1)
    while not _is_market_day(d):
        d -= timedelta(days=1)
    return d


def _next_market_day(d: date) -> date:
    """Return next market day (Mon-Fri) after d."""
    d += timedelta(days=1)
    while not _is_market_day(d):
        d += timedelta(days=1)
    return d
