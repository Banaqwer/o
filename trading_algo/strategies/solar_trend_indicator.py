"""
Strategy 3: Solar Trend Indicator (3-Day Solar Time Window)
Book reference: Lessons 7, 8, 9

Logic:
  1. Compute all 3-day Solar Time Windows (Sun-outer-planet aspects, 16 aspects).
     Window = day before, day of, day after the exact aspect.
  2. During each window, look for CONFIRMED 3-bar intraday highs and lows.
  3. A "confirmed" high or low in a window becomes a MAJOR short-term resistance/support.
  4. Trend is BULLISH when price breaks ABOVE the most recent Solar Window High.
  5. Trend is BEARISH when price breaks BELOW the most recent Solar Window Low.
  6. Once a trend direction is set:
     - Track the current Solar Window High (resistance / buy point for shorts).
     - Track the current Solar Window Low (support / sell point for longs).
  7. Signals:
     - SELL signal: price breaks below the Solar Window Low → bearish mode.
     - BUY signal:  price breaks above the Solar Window High → bullish mode.
  8. Stop management: use 2-bar reversal exits when inside a window during position.

Additional subtlety (Lesson 9):
  - If a 3-bar intraday high (or low) occurs DURING a Solar Window while
    already in a position, watch for a 2-bar reversal off that point as an EXIT.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..astro.time_windows import compute_solar_time_windows, is_in_solar_window
from ..utils.bar_analysis import (
    find_all_confirmed_pivots, BarReversal, is_n_bar_high, is_n_bar_low
)


@dataclass
class SolarTrendState:
    """Tracks the current Solar Trend state."""
    trend: str             # 'bull', 'bear', or 'neutral'
    resistance: float      # Solar Window High (break above = buy / exit short)
    support: float         # Solar Window Low  (break below = sell / exit long)
    resistance_date: date
    support_date: date
    last_signal_date: Optional[date] = None
    last_signal_direction: Optional[str] = None


@dataclass
class SolarTrendSignal:
    """A buy or sell signal from the Solar Trend Indicator."""
    direction: str       # 'long' or 'short'
    signal_date: date
    entry_price: float   # break level (Solar Window High or Low)
    stop_price: float    # prior confirmed Solar Window Low (for long) or High (for short)
    trend: str           # resulting trend after this signal
    signal_type: str = "solar_trend"


class SolarTrendIndicator:
    """
    Implements the Solar Trend Indicator (Lessons 7-9).

    This is the PRIMARY FILTER for other intraday strategies:
    only take long trades when trend is bullish, short trades when bearish.
    """

    def __init__(self):
        self.windows: List[Dict] = []
        self.solar_window_dates = set()

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute Solar Time Windows for the date range."""
        self.windows = compute_solar_time_windows(start_date, end_date)
        for w in self.windows:
            for d in w["window_dates"]:
                self.solar_window_dates.add(d)

    def _get_date(self, idx) -> date:
        return idx.date() if hasattr(idx, "date") else idx

    def find_solar_window_pivots(
        self,
        df: pd.DataFrame,
        n: int = 3,
    ) -> List[BarReversal]:
        """
        Find all confirmed pivots that occurred within Solar Time Windows.
        These are the ONLY pivots that matter for trend analysis.
        """
        all_pivots = find_all_confirmed_pivots(
            df, n=n, use_intraday=True,
            solar_window_dates=self.solar_window_dates
        )
        return [p for p in all_pivots if p.in_solar_window]

    def compute_trend_states(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> Tuple[List[SolarTrendSignal], Dict[date, SolarTrendState]]:
        """
        Compute the Solar Trend direction for each day in the range.

        Returns:
          signals: list of trend change signals
          daily_states: dict mapping date -> SolarTrendState
        """
        window_pivots = self.find_solar_window_pivots(df, n=3)

        # Also find confirmed pivots NOT in windows (for 2-bar reversal exit check)
        all_pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)

        signals = []
        daily_states: Dict[date, SolarTrendState] = {}

        if not window_pivots:
            return signals, daily_states

        # Sort pivots by date
        window_pivots.sort(key=lambda x: x.index)

        # Initial state: neutral, using first pivot's prices
        first_high = next((p for p in window_pivots if p.direction == "high"), None)
        first_low  = next((p for p in window_pivots if p.direction == "low"), None)

        if not first_high or not first_low:
            return signals, daily_states

        current_state = SolarTrendState(
            trend="neutral",
            resistance=first_high.price,
            support=first_low.price,
            resistance_date=self._get_date(first_high.date),
            support_date=self._get_date(first_low.date),
        )

        # Walk through each trading day
        prev_high_pivot: Optional[BarReversal] = first_high
        prev_low_pivot:  Optional[BarReversal] = first_low

        for i, idx in enumerate(df.index):
            d = self._get_date(idx)
            row = df.iloc[i]

            if not (start_date <= d <= end_date):
                continue

            # Update known Solar Window highs/lows as they appear
            for p in window_pivots:
                pd_date = self._get_date(p.date)
                if pd_date <= d:
                    if p.direction == "high":
                        if p.price > current_state.resistance or pd_date > current_state.resistance_date:
                            pass  # We'll track latest, not maximum
                        prev_high_pivot = p
                        # Latest solar window high is resistance
                        current_state.resistance = p.price
                        current_state.resistance_date = pd_date
                    else:
                        prev_low_pivot = p
                        current_state.support = p.price
                        current_state.support_date = pd_date

            # Check for trend change signals
            if current_state.trend != "bear" and row["low"] < current_state.support:
                # SELL signal: break below Solar Window Low
                new_state = SolarTrendState(
                    trend="bear",
                    resistance=current_state.resistance,
                    support=current_state.support,
                    resistance_date=current_state.resistance_date,
                    support_date=current_state.support_date,
                    last_signal_date=d,
                    last_signal_direction="short",
                )
                sig = SolarTrendSignal(
                    direction="short",
                    signal_date=d,
                    entry_price=current_state.support,
                    stop_price=current_state.resistance,
                    trend="bear",
                )
                signals.append(sig)
                current_state = new_state

            elif current_state.trend != "bull" and row["high"] > current_state.resistance:
                # BUY signal: break above Solar Window High
                new_state = SolarTrendState(
                    trend="bull",
                    resistance=current_state.resistance,
                    support=current_state.support,
                    resistance_date=current_state.resistance_date,
                    support_date=current_state.support_date,
                    last_signal_date=d,
                    last_signal_direction="long",
                )
                sig = SolarTrendSignal(
                    direction="long",
                    signal_date=d,
                    entry_price=current_state.resistance,
                    stop_price=current_state.support,
                    trend="bull",
                )
                signals.append(sig)
                current_state = new_state

            daily_states[d] = SolarTrendState(
                trend=current_state.trend,
                resistance=current_state.resistance,
                support=current_state.support,
                resistance_date=current_state.resistance_date,
                support_date=current_state.support_date,
            )

        return signals, daily_states

    def get_trend_on_date(
        self,
        daily_states: Dict[date, SolarTrendState],
        check_date: date,
    ) -> str:
        """Return trend direction on a specific date ('bull', 'bear', 'neutral')."""
        # Find the most recent state on or before check_date
        relevant = [d for d in daily_states if d <= check_date]
        if not relevant:
            return "neutral"
        return daily_states[max(relevant)].trend
