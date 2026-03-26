"""
Strategy 4: Lunar Trend Confirmation (LTC) Model
Book reference: Lessons 11, 12

Logic:
  1. Always trade in the same direction as the Solar Trend Indicator.
  2. Find intraday Moon-outer-planet aspects during market hours.
     Each creates a ±2-hour time window around the exact aspect.
  3. Within each window, identify the intraday 3-bar HIGH and 3-bar LOW
     (on 15-minute bars).
  4. AFTER the window closes, if price:
     - BREAKS BELOW the window's 3-bar LOW  → SHORT  (when Solar = bear)
     - BREAKS ABOVE the window's 3-bar HIGH → LONG   (when Solar = bull)
  5. Stop: tick above the window's 3-bar HIGH (for short)
           tick below the window's 3-bar LOW  (for long)
  6. Exit rules:
     - Exit when price breaks the opposite direction of the position
       (i.e., if short, exit when price breaks above the 3-bar high).
     - Each subsequent lunar window can lower the stop (for shorts)
       or raise the stop (for longs) → lock in profit progressively.
  7. Exit also when price breaks the CONFIRMED direction (i.e., when the
     next window produces an opposing 3-bar pivot that price breaks through).

Stop-lowering rule (Lesson 12):
  - For shorts: after each new lunar window that forms a 3-bar HIGH,
    lower the buy-stop to just above that new window high.
  - For longs: after each new lunar window that forms a 3-bar LOW,
    raise the sell-stop to just below that new window low.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd
import pytz

from ..astro.time_windows import compute_lunar_time_windows
from ..utils.bar_analysis import is_n_bar_high, is_n_bar_low


@dataclass
class LunarWindowPivot:
    """Pivot found within a Lunar Time Window."""
    window: Dict
    direction: str       # 'high' or 'low'
    price: float
    datetime: datetime
    bar_index: int


@dataclass
class LunarTrendSignal:
    """Trade signal from the Lunar Trend Confirmation model."""
    direction: str             # 'short' or 'long'
    entry_datetime: datetime
    entry_price: float
    stop_price: float          # initial stop
    window_high: float         # 3-bar high from the lunar window
    window_low: float          # 3-bar low from the lunar window
    solar_trend: str           # 'bear' or 'bull'
    signal_type: str = "lunar_trend_confirmation"


@dataclass
class LunarTrendPosition:
    """Active position managed by the LTC model."""
    signal: LunarTrendSignal
    current_stop: float
    is_open: bool = True
    exit_datetime: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None


class LunarTrendConfirmation:
    """
    Implements the Lunar Trend Confirmation model (Lessons 11-12).
    Requires the Solar Trend Indicator for direction filter.
    Works on 15-minute intraday bars.
    """

    N_BAR = 3  # Standard bar count for pivot detection in windows
    MARKET_TZ = pytz.UTC

    def __init__(self):
        self.lunar_windows: List[Dict] = []

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute all Lunar Time Windows."""
        self.lunar_windows = compute_lunar_time_windows(start_date, end_date)

    def find_window_pivots(
        self,
        df_15m: pd.DataFrame,
        window: Dict,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Find the 3-bar intraday HIGH and LOW within a lunar time window
        on 15-minute bars.

        Returns (window_high, window_low) — the extreme 3-bar highs/lows
        found within the window_start to window_end time.
        """
        ws = window["window_start"]
        we = window["window_end"]

        # Filter bars in the window
        mask = (df_15m.index >= ws) & (df_15m.index <= we)
        window_df = df_15m[mask]

        if len(window_df) < self.N_BAR + 1:
            return None, None

        window_high = None
        window_low  = None

        for i in range(self.N_BAR, len(window_df)):
            if is_n_bar_high(window_df, i, n=self.N_BAR, use_intraday=True):
                h = window_df["high"].iloc[i]
                if window_high is None or h > window_high:
                    window_high = h
            if is_n_bar_low(window_df, i, n=self.N_BAR, use_intraday=True):
                l = window_df["low"].iloc[i]
                if window_low is None or l < window_low:
                    window_low = l

        return window_high, window_low

    def generate_signals(
        self,
        df_15m: pd.DataFrame,
        solar_trend_by_date: Dict[date, str],
        start_date: date,
        end_date: date,
    ) -> List[LunarTrendSignal]:
        """
        Generate LTC signals for all lunar windows in range.

        df_15m: 15-minute OHLCV DataFrame with DatetimeIndex (UTC).
        solar_trend_by_date: dict of date → trend ('bull', 'bear', 'neutral').
        """
        signals = []

        for window in self.lunar_windows:
            d = window["date"]
            if not (start_date <= d <= end_date):
                continue

            solar_trend = solar_trend_by_date.get(d, "neutral")
            if solar_trend == "neutral":
                continue

            window_high, window_low = self.find_window_pivots(df_15m, window)
            if window_high is None or window_low is None:
                continue

            we = window["window_end"]

            # Post-window bars to check for breakout
            post_mask = df_15m.index > we
            post_df = df_15m[post_mask]

            for i, (idx, row) in enumerate(post_df.iterrows()):
                bar_date = idx.date() if hasattr(idx, "date") else idx
                if bar_date != d:
                    break  # Only trade on the same day after window

                if solar_trend == "bear" and row["low"] < window_low:
                    sig = LunarTrendSignal(
                        direction="short",
                        entry_datetime=idx,
                        entry_price=window_low,
                        stop_price=window_high + 0.01,
                        window_high=window_high,
                        window_low=window_low,
                        solar_trend=solar_trend,
                    )
                    signals.append(sig)
                    break

                elif solar_trend == "bull" and row["high"] > window_high:
                    sig = LunarTrendSignal(
                        direction="long",
                        entry_datetime=idx,
                        entry_price=window_high,
                        stop_price=window_low - 0.01,
                        window_high=window_high,
                        window_low=window_low,
                        solar_trend=solar_trend,
                    )
                    signals.append(sig)
                    break

        return signals

    def manage_positions(
        self,
        signals: List[LunarTrendSignal],
        df_15m: pd.DataFrame,
    ) -> List[LunarTrendPosition]:
        """
        Manage open positions: update stops from new lunar windows,
        exit on reversal or stop hit.

        Implements the progressive stop-lowering rule from Lesson 12.
        """
        positions = []

        for sig in signals:
            pos = LunarTrendPosition(signal=sig, current_stop=sig.stop_price)
            positions.append(pos)

            # Walk forward through bars after entry
            after_mask = df_15m.index > sig.entry_datetime
            for idx, row in df_15m[after_mask].iterrows():
                if not pos.is_open:
                    break

                # Check stop hit
                if sig.direction == "short" and row["high"] >= pos.current_stop:
                    pos.is_open      = False
                    pos.exit_datetime = idx
                    pos.exit_price    = pos.current_stop
                    pos.exit_reason   = "stop_hit"
                    break

                if sig.direction == "long" and row["low"] <= pos.current_stop:
                    pos.is_open       = False
                    pos.exit_datetime = idx
                    pos.exit_price    = pos.current_stop
                    pos.exit_reason   = "stop_hit"
                    break

                # Check for new lunar window to update stop
                for window in self.lunar_windows:
                    if window["window_start"] <= idx <= window["window_end"]:
                        wh, wl = self.find_window_pivots(df_15m, window)
                        if wh and wl:
                            if sig.direction == "short":
                                # Lower stop to just above new window high
                                new_stop = wh + 0.01
                                if new_stop < pos.current_stop:
                                    pos.current_stop = new_stop
                            else:
                                # Raise stop to just below new window low
                                new_stop = wl - 0.01
                                if new_stop > pos.current_stop:
                                    pos.current_stop = new_stop

        return positions
