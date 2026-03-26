"""
Ephemeris calculations using the ephem library.

Computes planetary longitudes, aspects between planets, Moon sign transits,
lunar phase angles, and Sun-to-outer-planet aspect dates.

Book references: Lessons 7, 8, 9, 10, 11, 12, 20
"""

import ephem
import math
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional, Dict
import pytz


# ---------------------------------------------------------------------------
# Aspect sets
# ---------------------------------------------------------------------------

# Original 11 aspects (Lesson 5) — degree values
ASPECTS_11 = [30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]

# Additional 5 aspects added for Solar Time Window (Lesson 7)
ASPECTS_5_EXTRA = [0, 45, 135, 225, 315]

# Full 16-aspect set used for Solar Time Window
ASPECTS_16 = sorted(set(ASPECTS_11 + ASPECTS_5_EXTRA))

# Aspect decimal multipliers for "The 8th Way" (Lesson 5)
ASPECT_DECIMALS = {
    1: 30 / 360,    # 0.0833
    2: 60 / 360,    # 0.1667
    3: 90 / 360,    # 0.25
    4: 120 / 360,   # 0.3333
    5: 150 / 360,   # 0.4167
    6: 180 / 360,   # 0.50
    7: 210 / 360,   # 0.5833
    8: 240 / 360,   # 0.6667
    9: 270 / 360,   # 0.75
    10: 300 / 360,  # 0.8333
    11: 330 / 360,  # 0.9167
}

# Outer planets for Solar/Lunar Time Windows (Lesson 7, 11)
OUTER_PLANETS = {
    "Uranus":  ephem.Uranus,
    "Neptune": ephem.Neptune,
    "Pluto":   ephem.Pluto,
}


# ---------------------------------------------------------------------------
# Helper: ephem date conversion
# ---------------------------------------------------------------------------

def _to_ephem_date(d) -> ephem.Date:
    """Convert date/datetime to ephem.Date."""
    if isinstance(d, ephem.Date):
        return d
    if isinstance(d, datetime):
        return ephem.Date(d.strftime("%Y/%m/%d %H:%M:%S"))
    if isinstance(d, date):
        return ephem.Date(d.strftime("%Y/%m/%d"))
    return ephem.Date(str(d))


def _ephem_to_datetime(d: ephem.Date) -> datetime:
    """Convert ephem.Date to Python datetime (UTC)."""
    tup = d.tuple()
    sec_frac = tup[5]
    sec = int(sec_frac)
    microsec = int((sec_frac - sec) * 1_000_000)
    return datetime(tup[0], tup[1], tup[2], tup[3], tup[4], sec, microsec, tzinfo=pytz.UTC)


# ---------------------------------------------------------------------------
# Basic planetary computations
# ---------------------------------------------------------------------------

def planet_longitude(planet_cls, dt) -> float:
    """Return ecliptic longitude (0-360) of a planet at given date/time."""
    body = planet_cls()
    body.compute(_to_ephem_date(dt))
    return math.degrees(body.hlong) % 360


def moon_phase_angle(dt) -> float:
    """
    Return the Moon's angular separation from the Sun (0-360).
    0   = New Moon (conjunction)
    90  = First Quarter
    180 = Full Moon
    270 = Last Quarter
    """
    sun = ephem.Sun()
    moon = ephem.Moon()
    d = _to_ephem_date(dt)
    sun.compute(d)
    moon.compute(d)
    sun_lon = math.degrees(sun.hlong) % 360
    moon_lon = math.degrees(moon.hlong) % 360
    angle = (moon_lon - sun_lon) % 360
    return angle


# ---------------------------------------------------------------------------
# Aspect detection
# ---------------------------------------------------------------------------

def _angular_difference(lon1: float, lon2: float) -> float:
    """Return the smallest absolute angular difference between two longitudes."""
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)


def _find_aspect_exact(
    body1_cls,
    body2_cls,
    start_dt: datetime,
    end_dt: datetime,
    aspect_deg: float,
    orb: float = 1.0,
    step_hours: float = 1.0,
) -> List[datetime]:
    """
    Find datetimes within [start_dt, end_dt] when body1 forms `aspect_deg`
    with body2 within `orb` degrees, searching in `step_hours` increments.
    Returns list of approximate exact times.
    """
    results = []
    current = start_dt
    delta = timedelta(hours=step_hours)
    prev_diff = None

    while current <= end_dt:
        lon1 = planet_longitude(body1_cls, current)
        lon2 = planet_longitude(body2_cls, current)
        raw_diff = (lon1 - lon2) % 360
        # Distance to target aspect
        dist = abs((raw_diff - aspect_deg + 180) % 360 - 180)

        if dist <= orb:
            # Refine with smaller step if we just entered the orb
            if prev_diff is None or prev_diff > orb:
                # Bisect to find exact crossing
                lo, hi = current - delta, current
                for _ in range(20):
                    mid = lo + (hi - lo) / 2
                    l1 = planet_longitude(body1_cls, mid)
                    l2 = planet_longitude(body2_cls, mid)
                    r = (l1 - l2) % 360
                    d = abs((r - aspect_deg + 180) % 360 - 180)
                    if d < 0.05:
                        results.append(mid)
                        break
                    # Determine which half contains the minimum
                    l1b = planet_longitude(body1_cls, lo)
                    l2b = planet_longitude(body2_cls, lo)
                    rb = (l1b - l2b) % 360
                    db = abs((rb - aspect_deg + 180) % 360 - 180)
                    if db < d:
                        hi = mid
                    else:
                        lo = mid
                else:
                    results.append(current)

        prev_diff = dist
        current += delta

    return results


# ---------------------------------------------------------------------------
# Sun-Outer planet aspects (Solar Time Windows, Lesson 7-9)
# ---------------------------------------------------------------------------

def sun_outer_aspects(
    start_date: date,
    end_date: date,
    aspects: List[float] = None,
    orb: float = 0.5,
) -> List[Dict]:
    """
    Compute all Sun-outer-planet (Uranus, Neptune, Pluto) aspect dates
    within the date range.

    Returns list of dicts: {date, planet, aspect_deg, exact_datetime}
    Used to build the 3-day Solar Time Window.
    """
    if aspects is None:
        aspects = ASPECTS_16

    results = []
    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=pytz.UTC)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, tzinfo=pytz.UTC)

    for planet_name, planet_cls in OUTER_PLANETS.items():
        for asp in aspects:
            times = _find_aspect_exact(
                ephem.Sun, planet_cls, start_dt, end_dt,
                asp, orb=orb, step_hours=6.0
            )
            for t in times:
                results.append({
                    "exact_datetime": t,
                    "date": t.date(),
                    "planet": planet_name,
                    "aspect_deg": asp,
                })

    results.sort(key=lambda x: x["exact_datetime"])
    return results


# ---------------------------------------------------------------------------
# Moon-Outer planet aspects (Lunar Time Windows, Lesson 11-12)
# ---------------------------------------------------------------------------

def moon_outer_aspects(
    start_date: date,
    end_date: date,
    market_open_hour: int = 9,
    market_open_min: int = 30,
    market_close_hour: int = 16,
    market_close_min: int = 15,
    aspects: List[float] = None,
    orb: float = 0.5,
) -> List[Dict]:
    """
    Compute all Moon-outer-planet aspect exact times within market hours
    for each day in the date range.

    Returns list of dicts: {date, planet, aspect_deg, exact_datetime,
                             window_start (exact-2h), window_end (exact+2h)}
    Used for the Lunar Trend Confirmation model.
    """
    if aspects is None:
        aspects = ASPECTS_16

    results = []
    start_dt = datetime(start_date.year, start_date.month, start_date.day,
                        market_open_hour, market_open_min, tzinfo=pytz.UTC)
    end_dt = datetime(end_date.year, end_date.month, end_date.day,
                      market_close_hour, market_close_min, tzinfo=pytz.UTC)

    for planet_name, planet_cls in OUTER_PLANETS.items():
        for asp in aspects:
            times = _find_aspect_exact(
                ephem.Moon, planet_cls, start_dt, end_dt,
                asp, orb=orb, step_hours=1.0
            )
            for t in times:
                results.append({
                    "exact_datetime": t,
                    "date": t.date(),
                    "planet": planet_name,
                    "aspect_deg": asp,
                    "window_start": t - timedelta(hours=2),
                    "window_end":   t + timedelta(hours=2),
                })

    results.sort(key=lambda x: x["exact_datetime"])
    return results


# ---------------------------------------------------------------------------
# Moon sign transits (Lessons 15, 16, 21, 23)
# ---------------------------------------------------------------------------

def moon_sign_transits(
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    For each day in [start_date, end_date], compute what zodiac sign(s)
    the Moon transits during US market hours (9:30 - 16:15 ET).
    Returns list of dicts: {date, sign, ingress_datetime (or None)}
    """
    from .zodiac import get_sign_from_degrees

    results = []
    current = start_date
    while current <= end_date:
        # Sample at market open and close
        times = [
            datetime(current.year, current.month, current.day, 9, 30, tzinfo=pytz.UTC),
            datetime(current.year, current.month, current.day, 12, 0, tzinfo=pytz.UTC),
            datetime(current.year, current.month, current.day, 16, 15, tzinfo=pytz.UTC),
        ]
        signs_today = set()
        for t in times:
            lon = planet_longitude(ephem.Moon, t)
            signs_today.add(get_sign_from_degrees(lon))

        for sign in signs_today:
            results.append({"date": current, "sign": sign})

        current += timedelta(days=1)

    return results


# ---------------------------------------------------------------------------
# Lunar phases (full date list)
# ---------------------------------------------------------------------------

def get_lunar_phases(
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    Return all 4-phase lunar events (New, 1st Quarter, Full, Last Quarter)
    between start_date and end_date.

    Returns list of dicts: {date, datetime, phase_name, sun_longitude,
                             moon_longitude, sun_duad, moon_duad,
                             sun_quality, moon_quality}
    """
    from .zodiac import get_duad, get_quality, get_sign_from_degrees

    results = []
    d = ephem.Date(_to_ephem_date(start_date))
    end_ephem = ephem.Date(_to_ephem_date(end_date))

    # Start slightly before to capture phases right at start
    d = ephem.Date(d - 30)

    while d < end_ephem + 30:
        nm = ephem.next_new_moon(d)
        fq = ephem.next_first_quarter_moon(d)
        fm = ephem.next_full_moon(d)
        lq = ephem.next_last_quarter_moon(d)

        phases = [
            (nm, "New Moon"),
            (fq, "First Quarter"),
            (fm, "Full Moon"),
            (lq, "Last Quarter"),
        ]

        for phase_date, phase_name in phases:
            dt = _ephem_to_datetime(phase_date)
            if not (start_date <= dt.date() <= end_date):
                # Advance and check next
                pass

            sun = ephem.Sun()
            moon = ephem.Moon()
            sun.compute(phase_date)
            moon.compute(phase_date)

            sun_lon = math.degrees(sun.hlong) % 360
            moon_lon = math.degrees(moon.hlong) % 360

            sun_duad = get_duad(sun_lon)
            moon_duad = get_duad(moon_lon)

            entry = {
                "date": dt.date(),
                "datetime": dt,
                "phase_name": phase_name,
                "sun_longitude": sun_lon,
                "moon_longitude": moon_lon,
                "sun_sign": get_sign_from_degrees(sun_lon),
                "moon_sign": get_sign_from_degrees(moon_lon),
                "sun_duad": sun_duad,
                "moon_duad": moon_duad,
                "sun_duad_quality": get_quality(sun_duad),
                "moon_duad_quality": get_quality(moon_duad),
            }
            results.append(entry)

        # Advance by one lunation (≈29.5 days) to get next set of phases
        d = nm + 29

    # Deduplicate and sort by date
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x["datetime"]):
        key = (r["date"], r["phase_name"])
        if key not in seen and start_date <= r["date"] <= end_date:
            seen.add(key)
            unique.append(r)

    return unique


# ---------------------------------------------------------------------------
# Sun-Neptune aspects specifically (Lesson 20)
# ---------------------------------------------------------------------------

def sun_neptune_aspects(
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    Compute all Sun-Neptune aspects using the 30-degree division (12 aspects).
    These recur approximately every 30 days and drive long-term signals.
    Returns list of dicts: {date, aspect_deg, aspect_name, exact_datetime}
    """
    aspect_names = {
        0:   "conjunction (0°)",
        30:  "semi-sextile (30°)",
        60:  "sextile (60°)",
        90:  "square (90°)",
        120: "trine (120°)",
        150: "quincunx (150°)",
        180: "opposition (180°)",
        210: "quincunx waning (210°)",
        240: "trine waning (240°)",
        270: "square waning (270°)",
        300: "sextile waning (300°)",
        330: "semi-sextile waning (330°)",
    }
    results = []
    aspects_30 = list(range(0, 360, 30))
    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=pytz.UTC)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, tzinfo=pytz.UTC)

    for asp in aspects_30:
        times = _find_aspect_exact(
            ephem.Sun, ephem.Neptune, start_dt, end_dt,
            asp, orb=0.5, step_hours=12.0
        )
        for t in times:
            results.append({
                "exact_datetime": t,
                "date": t.date(),
                "aspect_deg": asp,
                "aspect_name": aspect_names.get(asp, f"{asp}°"),
            })

    results.sort(key=lambda x: x["exact_datetime"])
    return results


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def compute_aspect_exact_time(
    body1_cls,
    body2_cls,
    approx_dt: datetime,
    aspect_deg: float,
    search_hours: float = 24.0,
) -> Optional[datetime]:
    """Narrow down exact aspect time within ±search_hours of approx_dt."""
    start = approx_dt - timedelta(hours=search_hours)
    end = approx_dt + timedelta(hours=search_hours)
    times = _find_aspect_exact(body1_cls, body2_cls, start, end, aspect_deg,
                               orb=0.2, step_hours=0.5)
    return times[0] if times else None
