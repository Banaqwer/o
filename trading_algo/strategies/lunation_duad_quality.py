"""
Strategy 1: Lunation Cycle Duad Quality Analysis
Book reference: Lessons 1, 2, 3

Logic:
  1. Track the 4-phase lunar cycle (New Moon, 1st Quarter, Full Moon, Last Quarter).
  2. For each phase, compute the Sun's duad and Moon's duad.
  3. If both duads share the same QUALITY (cardinal, fixed, or mutable) for
     3+ CONSECUTIVE phases, it signals a directional BIAS for that period.
  4. The prior experience of that quality determines the expected bias:
     - If that quality was previously associated with a DOWN market → SELL bias
     - If previously associated with an UP market → BUY bias
  5. Entry rule:
     - In a SELL bias: wait for a 3-day high, then short on a 2-day break of lows.
     - In a BUY bias: wait for a 3-day low, then buy on a 2-day break of highs.
  6. Exit: last day of the quality period (day before next phase of different quality).

Key insight from the book: Fixed mode → bearish; Mutable mode → also bearish
(as observed in the 2000 NDX examples). But the algorithm tracks historical
context to infer the bias.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..astro.lunar_cycle import get_lunar_phase_dates, lunar_phase_quality_sequence
from ..utils.bar_analysis import (
    find_all_confirmed_pivots, is_n_bar_high, is_n_bar_low, BarReversal
)


@dataclass
class LunationQualityPeriod:
    """A run of consecutive lunar phases with the same duad quality."""
    quality: str
    phases: List[Dict]
    start_date: date
    end_date: date     # last day of final phase (day before next phase)
    phase_count: int
    bias: Optional[str] = None   # 'long', 'short', or None (insufficient history)


@dataclass
class LunationQualitySignal:
    """A trade signal from the Lunation Duad Quality strategy."""
    direction: str           # 'short' or 'long'
    entry_date: date
    entry_price: float
    stop_price: float
    exit_date: date          # last day of quality period
    quality: str
    phase_count: int
    signal_type: str = "lunation_duad_quality"


class LunationDuadQualityStrategy:
    """
    Implements the Lunation Cycle Duad Quality strategy (Lessons 1-3).
    """

    MIN_CONSECUTIVE_PHASES = 3  # Minimum phases with same quality to trigger

    def __init__(self, symbol: str = "QQQ"):
        self.symbol = symbol

    def compute_quality_periods(
        self,
        start_date: date,
        end_date: date,
    ) -> List[LunationQualityPeriod]:
        """
        Compute all quality periods (consecutive same-quality phases) in the range.
        """
        # Get phases with a buffer for history
        buffer_start = start_date - timedelta(days=120)
        phases = get_lunar_phase_dates(buffer_start, end_date)
        annotated = lunar_phase_quality_sequence(phases)

        periods = []
        i = 0
        while i < len(annotated):
            p = annotated[i]
            if not p["common_quality"]:
                i += 1
                continue

            # Collect consecutive run of same quality
            quality = p["common_quality"]
            run = [p]
            j = i + 1
            while j < len(annotated) and annotated[j]["common_quality"] == quality:
                run.append(annotated[j])
                j += 1

            if len(run) >= self.MIN_CONSECUTIVE_PHASES:
                # End date = day before the start of next phase after this run
                if j < len(annotated):
                    end_d = annotated[j]["date"] - timedelta(days=1)
                else:
                    end_d = run[-1]["date"] + timedelta(days=30)

                period = LunationQualityPeriod(
                    quality=quality,
                    phases=run,
                    start_date=run[0]["date"],
                    end_date=end_d,
                    phase_count=len(run),
                )
                periods.append(period)

            i = j

        # Assign bias based on previous period of same quality
        quality_history: Dict[str, str] = {}  # quality -> 'up' or 'down'
        for period in periods:
            q = period.quality
            if q in quality_history:
                period.bias = "short" if quality_history[q] == "down" else "long"
            # We'll update history after generating signals (requires price data)

        return periods

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[LunationQualitySignal]:
        """
        Generate trade signals for the strategy.

        df: daily OHLCV DataFrame with DatetimeIndex.
        Returns list of LunationQualitySignal.
        """
        periods = self.compute_quality_periods(start_date, end_date)
        signals = []

        # Build quality→market-direction history from price performance
        quality_perf: Dict[str, List[float]] = {}

        for period in periods:
            if not (period.start_date <= end_date and period.end_date >= start_date):
                continue

            # Compute price performance during this period to update history
            period_df = df[
                (df.index.date >= period.start_date) &
                (df.index.date <= period.end_date)
            ] if hasattr(df.index, 'date') else df[
                (df.index >= pd.Timestamp(period.start_date)) &
                (df.index <= pd.Timestamp(period.end_date))
            ]

            if len(period_df) >= 2:
                perf = period_df["close"].iloc[-1] - period_df["close"].iloc[0]
                q = period.quality
                if q not in quality_perf:
                    quality_perf[q] = []
                quality_perf[q].append(perf)

                # Determine bias for THIS period from the prior occurrences
                if len(quality_perf[q]) >= 2:
                    prior_avg = sum(quality_perf[q][:-1]) / len(quality_perf[q][:-1])
                    period.bias = "short" if prior_avg < 0 else "long"

            if period.bias is None or period.phase_count < self.MIN_CONSECUTIVE_PHASES:
                continue

            # Generate entry signal during this period
            signal = self._find_entry(df, period)
            if signal:
                signals.append(signal)

        return signals

    def _find_entry(
        self,
        df: pd.DataFrame,
        period: LunationQualityPeriod,
    ) -> Optional[LunationQualitySignal]:
        """
        Find entry within the quality period.

        For SELL bias: look for a 3-day high, then short on 2-day break of lows.
        For BUY  bias: look for a 3-day low, then buy on 2-day break of highs.
        """
        # Filter to dates within the quality period
        def get_date(idx):
            return idx.date() if hasattr(idx, 'date') else idx

        mask = pd.Series([
            period.start_date <= get_date(idx) <= period.end_date
            for idx in df.index
        ], index=df.index)
        period_df = df[mask]

        if len(period_df) < 5:
            return None

        direction = period.bias  # 'short' or 'long'

        for i in range(3, len(period_df)):
            if direction == "short":
                # Look for 3-day high
                if is_n_bar_high(period_df, i, n=3, use_intraday=True):
                    # Now look for 2-day break of lows (entry trigger)
                    if i + 2 < len(period_df):
                        entry_bar = period_df.iloc[i + 1]
                        prev2_low = period_df["low"].iloc[i - 1: i + 1].min()
                        if entry_bar["low"] < prev2_low:
                            entry_price = prev2_low
                            stop_price  = period_df["high"].iloc[i] + 0.01
                            exit_date   = period.end_date
                            return LunationQualitySignal(
                                direction="short",
                                entry_date=get_date(period_df.index[i + 1]),
                                entry_price=entry_price,
                                stop_price=stop_price,
                                exit_date=exit_date,
                                quality=period.quality,
                                phase_count=period.phase_count,
                            )

            else:  # long
                if is_n_bar_low(period_df, i, n=3, use_intraday=True):
                    if i + 2 < len(period_df):
                        entry_bar = period_df.iloc[i + 1]
                        prev2_high = period_df["high"].iloc[i - 1: i + 1].max()
                        if entry_bar["high"] > prev2_high:
                            entry_price = prev2_high
                            stop_price  = period_df["low"].iloc[i] - 0.01
                            exit_date   = period.end_date
                            return LunationQualitySignal(
                                direction="long",
                                entry_date=get_date(period_df.index[i + 1]),
                                entry_price=entry_price,
                                stop_price=stop_price,
                                exit_date=exit_date,
                                quality=period.quality,
                                phase_count=period.phase_count,
                            )

        return None
