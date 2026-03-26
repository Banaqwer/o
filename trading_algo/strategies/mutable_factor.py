"""
Strategy 8: The Mutable Factor (with Engulfing Candlestick entry)
Book reference: Lessons 21, 22, 23

Logic:
  1. Track dates when the Moon transits through MUTABLE signs
     (Gemini, Virgo, Sagittarius, Pisces) during market hours.
  2. During these mutable periods, monitor for 3-bar highs (or lows)
     on the DAILY chart.
  3. If a 3-bar high (or low) is made during a mutable Moon period AND
     is immediately confirmed by a 3-bar reversal → this is a "mutable trend change."
  4. Look BACK in time for the prior confirmed 3-bar high/low.
  5. Entry rule — via candlestick body (Lessons 22, 23):
     - For SHORT:
       a. Find the body HIGH of the confirmed 3-bar LOW (prior + sign).
       b. Buy stop for exit short → tick above that body high.
       c. Entry = tick below the BODY LOW of the mutable cycle low.
       d. Stop  = tick below the body low of the actual cycle low.
       OR via bearish engulfing pattern (Lesson 23):
       a. Mutable period contains a 3-bar high.
       b. Price forms a BEARISH ENGULFING candlestick during/after that high.
       c. Entry = tick below prior day's body low.
       d. Stop  = tick above signal day's intraday high.
       e. Target 1 (half position): entry − risk (1× risk).
       f. Target 2 (remaining half): entry − 2× risk.
  6. 5-Day Rule (Lesson 22):
     If the price target is NOT hit within 5 trading days → close at EOD day 5.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Set
import pandas as pd

from ..astro.zodiac import QUALITY_SIGNS
from ..astro.ephemeris import moon_sign_transits
from ..utils.bar_analysis import (
    find_all_confirmed_pivots, is_n_bar_high, is_n_bar_low, BarReversal
)
from ..utils.candlestick import (
    is_bearish_engulfing, is_bullish_engulfing,
    bearish_engulfing_entry_price, bearish_engulfing_stop_price,
    bullish_engulfing_entry_price, bullish_engulfing_stop_price,
    candlestick_body_high, candlestick_body_low,
    engulfing_price_target,
)

MUTABLE_SIGNS: Set[str] = set(QUALITY_SIGNS["Mutable"])
MAX_HOLDING_DAYS = 5


@dataclass
class MutableSignal:
    """Trade signal from the Mutable Factor strategy."""
    direction: str           # 'short' or 'long'
    signal_date: date
    entry_price: float
    stop_price: float
    target_price_half: float   # 1× risk — exit half position here
    target_price_full: float   # 2× risk — exit remaining half here
    risk: float
    max_exit_date: date        # 5-trading-day deadline
    moon_sign: str             # Mutable sign Moon is in
    prior_pivot_date: date
    prior_pivot_price: float
    entry_type: str            # 'body' or 'engulfing'
    signal_type: str = "mutable_factor"


class MutableFactorStrategy:
    """
    Implements the Mutable Factor strategy (Lessons 21-23).
    """

    def __init__(self):
        self._mutable_dates: Dict[date, List[str]] = {}

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute Moon mutable sign transit dates."""
        buffer_start = start_date - timedelta(days=30)
        transits = moon_sign_transits(buffer_start, end_date)
        for t in transits:
            if t["sign"] in MUTABLE_SIGNS:
                d = t["date"]
                if d not in self._mutable_dates:
                    self._mutable_dates[d] = []
                self._mutable_dates[d].append(t["sign"])

    def _is_mutable_date(self, d: date) -> Optional[str]:
        """Return mutable sign name if Moon is in a mutable sign that day, else None."""
        signs = self._mutable_dates.get(d, [])
        return signs[0] if signs else None

    def _add_trading_days(self, d: date, n: int) -> date:
        """Add n trading days (Mon-Fri) to a date."""
        count = 0
        current = d
        while count < n:
            current += timedelta(days=1)
            if current.weekday() < 5:
                count += 1
        return current

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[MutableSignal]:
        """
        Scan for Mutable Factor signals.

        Two entry approaches:
        A. Body-based (Lesson 22): using candlestick body highs/lows.
        B. Engulfing (Lesson 23): bearish/bullish engulfing during mutable period.
        """
        if not self._mutable_dates:
            self.initialize(start_date, end_date)

        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)
        pivot_by_date = {get_date(p.date): p for p in pivots}

        signals = []

        for i in range(1, len(df)):
            d = get_date(df.index[i])
            if not (start_date <= d <= end_date):
                continue

            moon_sign = self._is_mutable_date(d)
            if not moon_sign:
                continue

            curr_row = df.iloc[i]
            prev_row = df.iloc[i - 1]

            # ── Approach A: Body-based entry (Lesson 22) ──
            # Check if today has a confirmed 3-bar HIGH or LOW
            pivot = pivot_by_date.get(d)

            if pivot and pivot.direction == "low":
                # Find prior confirmed 3-bar HIGH
                prior_high = None
                for p in reversed(pivots):
                    if get_date(p.date) < d and p.direction == "high":
                        prior_high = p
                        break

                if prior_high:
                    # Entry = tick above body HIGH of prior high's close/open
                    prior_high_row = df.iloc[prior_high.index] if prior_high.index < len(df) else None
                    if prior_high_row is not None:
                        body_high = candlestick_body_high(prior_high_row)
                        entry_price = body_high + 0.01
                        # Stop = tick below BODY LOW of the cycle low
                        body_low_cycle = candlestick_body_low(curr_row)
                        stop_price = body_low_cycle - 0.01
                        risk = abs(entry_price - stop_price)
                        target_half = entry_price + risk
                        target_full = entry_price + 2 * risk
                        max_exit = self._add_trading_days(d, MAX_HOLDING_DAYS)

                        sig = MutableSignal(
                            direction="long",
                            signal_date=d,
                            entry_price=entry_price,
                            stop_price=stop_price,
                            target_price_half=target_half,
                            target_price_full=target_full,
                            risk=risk,
                            max_exit_date=max_exit,
                            moon_sign=moon_sign,
                            prior_pivot_date=get_date(prior_high.date),
                            prior_pivot_price=prior_high.price,
                            entry_type="body",
                        )
                        signals.append(sig)

            elif pivot and pivot.direction == "high":
                # Find prior confirmed 3-bar LOW
                prior_low = None
                for p in reversed(pivots):
                    if get_date(p.date) < d and p.direction == "low":
                        prior_low = p
                        break

                if prior_low:
                    prior_low_row = df.iloc[prior_low.index] if prior_low.index < len(df) else None
                    if prior_low_row is not None:
                        body_low = candlestick_body_low(prior_low_row)
                        entry_price = body_low - 0.01
                        body_high_cycle = candlestick_body_high(curr_row)
                        stop_price = body_high_cycle + 0.01
                        risk = abs(stop_price - entry_price)
                        target_half = entry_price - risk
                        target_full = entry_price - 2 * risk
                        max_exit = self._add_trading_days(d, MAX_HOLDING_DAYS)

                        sig = MutableSignal(
                            direction="short",
                            signal_date=d,
                            entry_price=entry_price,
                            stop_price=stop_price,
                            target_price_half=target_half,
                            target_price_full=target_full,
                            risk=risk,
                            max_exit_date=max_exit,
                            moon_sign=moon_sign,
                            prior_pivot_date=get_date(prior_low.date),
                            prior_pivot_price=prior_low.price,
                            entry_type="body",
                        )
                        signals.append(sig)

            # ── Approach B: Engulfing entry (Lesson 23) ──
            # Bearish engulfing during a mutable period where 3-bar high exists
            if is_n_bar_high(df, i, n=3, use_intraday=True) and is_bearish_engulfing(prev_row, curr_row):
                entry_price = bearish_engulfing_entry_price(prev_row)
                stop_price  = bearish_engulfing_stop_price(curr_row)
                risk        = abs(stop_price - entry_price)
                target_half = entry_price - risk
                target_full = entry_price - 2 * risk
                max_exit    = self._add_trading_days(d, MAX_HOLDING_DAYS)

                prior_low = next(
                    (p for p in reversed(pivots)
                     if get_date(p.date) < d and p.direction == "low"),
                    None
                )

                sig = MutableSignal(
                    direction="short",
                    signal_date=d,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price_half=target_half,
                    target_price_full=target_full,
                    risk=risk,
                    max_exit_date=max_exit,
                    moon_sign=moon_sign,
                    prior_pivot_date=get_date(prior_low.date) if prior_low else d,
                    prior_pivot_price=prior_low.price if prior_low else 0.0,
                    entry_type="engulfing",
                )
                signals.append(sig)

            elif is_n_bar_low(df, i, n=3, use_intraday=True) and is_bullish_engulfing(prev_row, curr_row):
                entry_price = bullish_engulfing_entry_price(prev_row)
                stop_price  = bullish_engulfing_stop_price(curr_row)
                risk        = abs(entry_price - stop_price)
                target_half = entry_price + risk
                target_full = entry_price + 2 * risk
                max_exit    = self._add_trading_days(d, MAX_HOLDING_DAYS)

                prior_high = next(
                    (p for p in reversed(pivots)
                     if get_date(p.date) < d and p.direction == "high"),
                    None
                )

                sig = MutableSignal(
                    direction="long",
                    signal_date=d,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price_half=target_half,
                    target_price_full=target_full,
                    risk=risk,
                    max_exit_date=max_exit,
                    moon_sign=moon_sign,
                    prior_pivot_date=get_date(prior_high.date) if prior_high else d,
                    prior_pivot_price=prior_high.price if prior_high else 0.0,
                    entry_type="engulfing",
                )
                signals.append(sig)

        return signals
