"""
Strategy 7: Sun-Neptune Long-Term Signal
Book reference: Lesson 20

Logic:
  1. Compute all Sun-Neptune aspects (every ~30 degrees, ~monthly).
  2. Check if BOTH the primary stock AND its sector ETF (e.g., INTC + SMH)
     make CONFIRMED 3-bar highs OR 3-bar lows within ONE trading day of a
     Sun-Neptune aspect date.
  3. If both confirm on highs → SHORT signal.
     If both confirm on lows  → LONG signal.
  4. Entry: on the 3-bar reversal breakout (or gap-open through the reversal level).
  5. Stop: tick above the cycle HIGH (for short) / tick below cycle LOW (for long).
  6. Price target: 3× the risk (long-term influence; risk × 3 = target distance).
  7. Exit: when price hits target, OR when stopped out.

Key detail: the aspect window is "within ONE trading day" of the exact aspect.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..astro.ephemeris import sun_neptune_aspects
from ..utils.bar_analysis import find_all_confirmed_pivots, BarReversal


@dataclass
class SunNeptuneSignal:
    """Trade signal from the Sun-Neptune strategy."""
    direction: str             # 'short' or 'long'
    signal_date: date
    entry_price: float
    stop_price: float
    target_price: float
    risk: float
    aspect_date: date
    aspect_name: str
    primary_symbol: str
    sector_symbol: str
    primary_pivot: BarReversal
    sector_pivot: BarReversal
    signal_type: str = "sun_neptune"


class SunNeptuneStrategy:
    """
    Implements the Sun-Neptune long-term signal strategy (Lesson 20).

    Requires two correlated symbols: primary stock + sector ETF.
    """

    ASPECT_WINDOW_DAYS = 1   # Within 1 trading day of exact aspect
    TARGET_RISK_MULTIPLIER = 3.0  # 3:1 risk-reward

    def __init__(self, primary_symbol: str, sector_symbol: str):
        self.primary_symbol = primary_symbol
        self.sector_symbol  = sector_symbol
        self._aspects: List[Dict] = []

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute Sun-Neptune aspects for the range (with buffer)."""
        buffer_start = start_date - timedelta(days=60)
        self._aspects = sun_neptune_aspects(buffer_start, end_date)

    def generate_signals(
        self,
        df_primary: pd.DataFrame,
        df_sector: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[SunNeptuneSignal]:
        """
        Scan for Sun-Neptune signals in both primary and sector DataFrames.

        df_primary: daily OHLCV for the primary stock.
        df_sector:  daily OHLCV for the sector ETF.
        """
        if not self._aspects:
            self.initialize(start_date, end_date)

        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        primary_pivots = find_all_confirmed_pivots(df_primary, n=3, use_intraday=True)
        sector_pivots  = find_all_confirmed_pivots(df_sector,  n=3, use_intraday=True)

        primary_high_by_date = {}
        primary_low_by_date  = {}
        sector_high_by_date  = {}
        sector_low_by_date   = {}

        for p in primary_pivots:
            d = get_date(p.date)
            if p.direction == "high":
                primary_high_by_date[d] = p
            else:
                primary_low_by_date[d]  = p

        for p in sector_pivots:
            d = get_date(p.date)
            if p.direction == "high":
                sector_high_by_date[d] = p
            else:
                sector_low_by_date[d]  = p

        signals = []

        for asp in self._aspects:
            asp_date = asp["date"]
            if not (start_date <= asp_date <= end_date):
                continue

            # Search within ±1 trading day of aspect date
            search_dates = [asp_date]
            prev_d = asp_date - timedelta(days=1)
            next_d = asp_date + timedelta(days=1)
            # Skip weekends
            if prev_d.weekday() < 5:
                search_dates.append(prev_d)
            if next_d.weekday() < 5:
                search_dates.append(next_d)

            # Check for HIGH confirmations on both
            for d in search_dates:
                primary_high = primary_high_by_date.get(d)
                sector_high  = sector_high_by_date.get(d)

                if primary_high and sector_high:
                    # Both confirmed highs → SHORT signal
                    # Entry: reversal breakout below the lower of the two confirmation prices
                    reversal_price = min(
                        df_primary.loc[df_primary.index >= pd.Timestamp(d), "low"].iloc[0]
                        if any(pd.Timestamp(d) <= idx for idx in df_primary.index) else primary_high.price,
                        df_sector.loc[df_sector.index >= pd.Timestamp(d), "low"].iloc[0]
                        if any(pd.Timestamp(d) <= idx for idx in df_sector.index) else sector_high.price,
                    )

                    stop_price  = primary_high.price + 0.01
                    entry_price = reversal_price
                    risk        = abs(stop_price - entry_price)
                    target_price = entry_price - risk * self.TARGET_RISK_MULTIPLIER

                    sig = SunNeptuneSignal(
                        direction="short",
                        signal_date=d,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        risk=risk,
                        aspect_date=asp_date,
                        aspect_name=asp["aspect_name"],
                        primary_symbol=self.primary_symbol,
                        sector_symbol=self.sector_symbol,
                        primary_pivot=primary_high,
                        sector_pivot=sector_high,
                    )
                    signals.append(sig)
                    break

            # Check for LOW confirmations on both
            for d in search_dates:
                primary_low = primary_low_by_date.get(d)
                sector_low  = sector_low_by_date.get(d)

                if primary_low and sector_low:
                    # Both confirmed lows → LONG signal
                    reversal_price = max(
                        df_primary.loc[df_primary.index >= pd.Timestamp(d), "high"].iloc[0]
                        if any(pd.Timestamp(d) <= idx for idx in df_primary.index) else primary_low.price,
                        df_sector.loc[df_sector.index >= pd.Timestamp(d), "high"].iloc[0]
                        if any(pd.Timestamp(d) <= idx for idx in df_sector.index) else sector_low.price,
                    )

                    stop_price  = primary_low.price - 0.01
                    entry_price = reversal_price
                    risk        = abs(entry_price - stop_price)
                    target_price = entry_price + risk * self.TARGET_RISK_MULTIPLIER

                    sig = SunNeptuneSignal(
                        direction="long",
                        signal_date=d,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        risk=risk,
                        aspect_date=asp_date,
                        aspect_name=asp["aspect_name"],
                        primary_symbol=self.primary_symbol,
                        sector_symbol=self.sector_symbol,
                        primary_pivot=primary_low,
                        sector_pivot=sector_low,
                    )
                    signals.append(sig)
                    break

        return signals
