"""
Lunar cycle calculations: phase dates and duad-sign transit dates.

Book references: Lessons 2, 3, 24, 25
"""

import ephem
import math
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz

from .ephemeris import _to_ephem_date, _ephem_to_datetime, planet_longitude
from .zodiac import get_duad, get_quality, get_sign_from_degrees, SIGNS


def next_new_moon(after_date: date) -> datetime:
    """Return datetime of next New Moon after given date."""
    d = ephem.next_new_moon(_to_ephem_date(after_date))
    return _ephem_to_datetime(d)


def next_first_quarter(after_date: date) -> datetime:
    d = ephem.next_first_quarter_moon(_to_ephem_date(after_date))
    return _ephem_to_datetime(d)


def next_full_moon(after_date: date) -> datetime:
    d = ephem.next_full_moon(_to_ephem_date(after_date))
    return _ephem_to_datetime(d)


def next_last_quarter(after_date: date) -> datetime:
    d = ephem.next_last_quarter_moon(_to_ephem_date(after_date))
    return _ephem_to_datetime(d)


def get_lunar_phase_dates(
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    Return all New Moon, First Quarter, Full Moon, Last Quarter dates
    between start_date and end_date, with Sun and Moon duad information.

    Each entry has:
      phase_name, date, datetime, sun_longitude, moon_longitude,
      sun_sign, moon_sign, sun_duad, moon_duad,
      sun_duad_quality, moon_duad_quality
    """
    results = []
    # Start searching a bit before to capture phases right at the start
    search_start = ephem.Date(_to_ephem_date(start_date) - 30)
    search_end = ephem.Date(_to_ephem_date(end_date) + 30)

    d = search_start
    while d < search_end:
        nm_date = ephem.next_new_moon(d)

        for phase_fn, phase_name in [
            (ephem.next_new_moon,             "New Moon"),
            (ephem.next_first_quarter_moon,   "First Quarter"),
            (ephem.next_full_moon,            "Full Moon"),
            (ephem.next_last_quarter_moon,    "Last Quarter"),
        ]:
            phase_date = phase_fn(d)
            dt = _ephem_to_datetime(phase_date)

            if not (start_date <= dt.date() <= end_date):
                continue

            sun = ephem.Sun()
            moon = ephem.Moon()
            sun.compute(phase_date)
            moon.compute(phase_date)
            sun_lon  = math.degrees(sun.hlong) % 360
            moon_lon = math.degrees(moon.hlong) % 360

            sun_duad   = get_duad(sun_lon)
            moon_duad  = get_duad(moon_lon)

            results.append({
                "phase_name":        phase_name,
                "date":              dt.date(),
                "datetime":          dt,
                "sun_longitude":     sun_lon,
                "moon_longitude":    moon_lon,
                "sun_sign":          get_sign_from_degrees(sun_lon),
                "moon_sign":         get_sign_from_degrees(moon_lon),
                "sun_duad":          sun_duad,
                "moon_duad":         moon_duad,
                "sun_duad_quality":  get_quality(sun_duad),
                "moon_duad_quality": get_quality(moon_duad),
            })

        # Advance by one lunation
        d = ephem.Date(nm_date + 29)

    # Deduplicate and sort
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x["datetime"]):
        key = (r["date"], r["phase_name"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def lunar_phase_duad_dates(
    phase: Dict,
    start_date: date,
    end_date: date,
) -> List[Dict]:
    """
    Given a lunar phase dict (from get_lunar_phase_dates), find the dates
    when the transiting Moon passes through the duad sign(s) of that phase
    during market hours.

    For a New Moon (Sun == Moon), there is only ONE duad.
    For other phases, there are TWO duads (sun_duad and moon_duad),
    which may be the same or different signs.

    Returns list of {date, sign, phase_ref}
    """
    from .ephemeris import moon_sign_transits

    # Collect unique duad signs for this phase
    duad_signs = set()
    duad_signs.add(phase["sun_duad"])
    duad_signs.add(phase["moon_duad"])

    # Get Moon sign transits for the search window
    transits = moon_sign_transits(start_date, end_date)

    results = []
    for t in transits:
        if t["sign"] in duad_signs:
            results.append({
                "date":      t["date"],
                "sign":      t["sign"],
                "phase_ref": phase,
            })

    return results


def get_lunar_phase_last_day(
    phase_date: date,
    next_phase_date: date,
) -> date:
    """
    The 'last day' of a lunar phase is the day before the next phase begins.
    """
    return next_phase_date - timedelta(days=1)


def lunar_phase_quality_sequence(
    phases: List[Dict],
) -> List[Dict]:
    """
    For a list of phases, return each phase annotated with whether the
    sun_duad_quality == moon_duad_quality (the key condition from Lessons 2-3).

    Also marks how many consecutive phases share the same quality.
    """
    annotated = []
    for i, p in enumerate(phases):
        same = p["sun_duad_quality"] == p["moon_duad_quality"]
        p = dict(p)
        p["duad_quality_match"] = same
        p["common_quality"] = p["sun_duad_quality"] if same else None
        annotated.append(p)

    # Count consecutive runs of same quality
    for i, p in enumerate(annotated):
        if not p["common_quality"]:
            p["consecutive_quality_count"] = 0
            continue
        count = 1
        q = p["common_quality"]
        j = i - 1
        while j >= 0 and annotated[j]["common_quality"] == q:
            count += 1
            j -= 1
        p["consecutive_quality_count"] = count

    return annotated
