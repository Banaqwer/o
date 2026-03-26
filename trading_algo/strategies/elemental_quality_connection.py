"""
Strategy 5: Elemental & Quality Connection
Book reference: Lessons 15, 16

The "Elemental Connection" (Lesson 15):
  1. Identify a bearish (or bullish) engulfing candlestick pattern.
  2. Note what ELEMENT the Moon is transiting through on that day
     (fire, earth, air, or water).
  3. Look back to the PRIOR period when the Moon was in a sign of the SAME ELEMENT.
  4. If both periods relate to 3-bar highs (or both to lows), AND the current
     high is LOWER than the prior same-element high (for short) → valid signal.
  5. Entry: tick below prior day's body low.
  6. Stop:  tick above signal day's HIGH (intraday).
  7. Target: entry − 2 × risk  (always 2:1 risk-reward).

The "Quality Connection" (Lesson 16):
  - Identical rules, but uses the QUALITY (cardinal, fixed, mutable) instead of element.
  - Fixed signs: Taurus, Leo, Scorpio, Aquarius.
  - Cardinal signs: Aries, Cancer, Libra, Capricorn.
  - Mutable signs: Gemini, Virgo, Sagittarius, Pisces.

Both connections combined: if both elemental AND quality criteria are met → higher
confidence signal.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..astro.zodiac import (
    SIGN_ELEMENT, SIGN_QUALITY, ELEMENT_SIGNS, QUALITY_SIGNS
)
from ..astro.ephemeris import moon_sign_transits
from ..utils.bar_analysis import is_n_bar_high, is_n_bar_low, find_all_confirmed_pivots
from ..utils.candlestick import (
    is_bearish_engulfing, is_bullish_engulfing,
    bearish_engulfing_entry_price, bearish_engulfing_stop_price,
    bullish_engulfing_entry_price, bullish_engulfing_stop_price,
    engulfing_price_target, candlestick_body_high, candlestick_body_low,
)


@dataclass
class ElementalSignal:
    """Trade signal from the Elemental or Quality Connection strategy."""
    direction: str            # 'short' or 'long'
    signal_date: date
    entry_price: float
    stop_price: float
    target_price: float
    risk: float
    moon_sign: str
    moon_element: str
    moon_quality: str
    prior_element_date: date  # date of prior same-element Moon transit with high/low
    prior_quality_date: date  # date of prior same-quality Moon transit with high/low
    connection_type: str      # 'elemental', 'quality', or 'both'
    signal_type: str = "elemental_quality_connection"


class ElementalQualityConnectionStrategy:
    """
    Implements the Elemental & Quality Connection strategies (Lessons 15-16).
    """

    def __init__(self):
        self._moon_transits: List[Dict] = []
        self._moon_transit_by_date: Dict[date, List[str]] = {}

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute Moon sign transits for the date range (+ 60-day lookback)."""
        buffer_start = start_date - timedelta(days=60)
        self._moon_transits = moon_sign_transits(buffer_start, end_date)
        for t in self._moon_transits:
            d = t["date"]
            if d not in self._moon_transit_by_date:
                self._moon_transit_by_date[d] = []
            self._moon_transit_by_date[d].append(t["sign"])

    def _get_moon_signs_on_date(self, d: date) -> List[str]:
        return self._moon_transit_by_date.get(d, [])

    def _prior_same_group_dates(
        self,
        target_date: date,
        group_type: str,      # 'element' or 'quality'
        group_value: str,     # e.g. 'Fire' or 'Fixed'
        lookback_days: int = 60,
    ) -> List[date]:
        """
        Return dates before target_date where Moon transited through
        the same element or quality group.
        """
        group_signs = (
            ELEMENT_SIGNS[group_value] if group_type == "element"
            else QUALITY_SIGNS[group_value]
        )
        result = []
        for t in self._moon_transits:
            d = t["date"]
            if d < target_date and d >= target_date - timedelta(days=lookback_days):
                if t["sign"] in group_signs:
                    result.append(d)
        return sorted(set(result))

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[ElementalSignal]:
        """
        Scan for Elemental and Quality Connection signals.

        df: daily OHLCV DataFrame.
        """
        if not self._moon_transits:
            self.initialize(start_date, end_date)

        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)
        pivot_dates_high = {get_date(p.date): p for p in pivots if p.direction == "high"}
        pivot_dates_low  = {get_date(p.date): p for p in pivots if p.direction == "low"}

        signals = []

        for i in range(1, len(df)):
            d = get_date(df.index[i])
            if not (start_date <= d <= end_date):
                continue

            curr_row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            prev_date = get_date(df.index[i - 1])

            # Get Moon signs transiting today
            moon_signs_today = self._get_moon_signs_on_date(d)
            if not moon_signs_today:
                continue

            # Check for 3-bar high today (required for bearish engulfing context)
            has_3bar_high = is_n_bar_high(df, i, n=3, use_intraday=True)
            has_3bar_low  = is_n_bar_low(df, i, n=3, use_intraday=True)

            for moon_sign in moon_signs_today:
                moon_element = SIGN_ELEMENT[moon_sign]
                moon_quality = SIGN_QUALITY[moon_sign]

                # ---- BEARISH ENGULFING / SHORT ----
                if has_3bar_high and is_bearish_engulfing(prev_row, curr_row):
                    # Check elemental connection
                    prior_element_dates = self._prior_same_group_dates(
                        d, "element", moon_element
                    )
                    # Check quality connection
                    prior_quality_dates = self._prior_same_group_dates(
                        d, "quality", moon_quality
                    )

                    elem_ok = any(pd_ in pivot_dates_high for pd_ in prior_element_dates)
                    qual_ok = any(pd_ in pivot_dates_high for pd_ in prior_quality_dates)

                    # Require prior same-group period also had a 3-bar HIGH
                    # AND current high is LOWER than prior same-group high
                    prior_elem_pivot = None
                    for pd_ in reversed(prior_element_dates):
                        if pd_ in pivot_dates_high:
                            prior_elem_pivot = pivot_dates_high[pd_]
                            break

                    prior_qual_pivot = None
                    for pd_ in reversed(prior_quality_dates):
                        if pd_ in pivot_dates_high:
                            prior_qual_pivot = pivot_dates_high[pd_]
                            break

                    # Current high must be lower than prior same-group high
                    curr_high = curr_row["high"]
                    elem_valid = (prior_elem_pivot is not None and
                                  curr_high < prior_elem_pivot.price)
                    qual_valid = (prior_qual_pivot is not None and
                                  curr_high < prior_qual_pivot.price)

                    if not (elem_valid or qual_valid):
                        continue

                    conn_type = ("both" if elem_valid and qual_valid
                                 else ("elemental" if elem_valid else "quality"))

                    entry_price = bearish_engulfing_entry_price(prev_row)
                    stop_price  = bearish_engulfing_stop_price(curr_row)
                    risk        = abs(stop_price - entry_price)
                    target_price = engulfing_price_target(entry_price, stop_price, "short")

                    sig = ElementalSignal(
                        direction="short",
                        signal_date=d,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        risk=risk,
                        moon_sign=moon_sign,
                        moon_element=moon_element,
                        moon_quality=moon_quality,
                        prior_element_date=prior_elem_pivot.date if prior_elem_pivot else d,
                        prior_quality_date=prior_qual_pivot.date if prior_qual_pivot else d,
                        connection_type=conn_type,
                    )
                    signals.append(sig)

                # ---- BULLISH ENGULFING / LONG ----
                elif has_3bar_low and is_bullish_engulfing(prev_row, curr_row):
                    prior_element_dates = self._prior_same_group_dates(
                        d, "element", moon_element
                    )
                    prior_quality_dates = self._prior_same_group_dates(
                        d, "quality", moon_quality
                    )

                    prior_elem_pivot = None
                    for pd_ in reversed(prior_element_dates):
                        if pd_ in pivot_dates_low:
                            prior_elem_pivot = pivot_dates_low[pd_]
                            break

                    prior_qual_pivot = None
                    for pd_ in reversed(prior_quality_dates):
                        if pd_ in pivot_dates_low:
                            prior_qual_pivot = pivot_dates_low[pd_]
                            break

                    curr_low = curr_row["low"]
                    elem_valid = (prior_elem_pivot is not None and
                                  curr_low > prior_elem_pivot.price)
                    qual_valid = (prior_qual_pivot is not None and
                                  curr_low > prior_qual_pivot.price)

                    if not (elem_valid or qual_valid):
                        continue

                    conn_type = ("both" if elem_valid and qual_valid
                                 else ("elemental" if elem_valid else "quality"))

                    entry_price = bullish_engulfing_entry_price(prev_row)
                    stop_price  = bullish_engulfing_stop_price(curr_row)
                    risk        = abs(entry_price - stop_price)
                    target_price = engulfing_price_target(entry_price, stop_price, "long")

                    sig = ElementalSignal(
                        direction="long",
                        signal_date=d,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        risk=risk,
                        moon_sign=moon_sign,
                        moon_element=moon_element,
                        moon_quality=moon_quality,
                        prior_element_date=prior_elem_pivot.date if prior_elem_pivot else d,
                        prior_quality_date=prior_qual_pivot.date if prior_qual_pivot else d,
                        connection_type=conn_type,
                    )
                    signals.append(sig)

        return signals
