"""
Strategy 9: 4-Phase Lunar Cycle with Duad Turn Dates
Book reference: Lessons 24, 25

Logic:
  1. For each of the 4 lunar phases (New, 1st Quarter, Full, Last Quarter):
     a. The PHASE DATE itself is a potential turn date.
     b. The DUAD DATE(S) — when the Moon next transits through the sign of the
        duad for that phase — are also potential turn dates.
        (New Moon has one duad; other phases have two: Sun duad + Moon duad.)
  2. On each potential turn date, look for a CONFIRMED 3-bar high or low.
  3. If confirmed, that price level becomes a MAJOR short-term resistance/support:
     - Break ABOVE a confirmed high → BUY signal.
     - Break BELOW a confirmed low  → SELL signal.
  4. Progressively update the support/resistance levels:
     - For a bearish mode: each new confirmed high LOWERS the resistance (buy point).
     - For a bullish mode: each new confirmed low RAISES the support (sell point).
  5. The sell/buy signal occurs when the PREVIOUS confirmed level is broken.

This is the most complete strategy in the book (used to generate 60.8% return
in the 2001 QQQ example from Lesson 25).
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Dict, Set, Tuple
import pandas as pd

from ..astro.lunar_cycle import (
    get_lunar_phase_dates, lunar_phase_duad_dates
)
from ..utils.bar_analysis import (
    find_all_confirmed_pivots, BarReversal, is_n_bar_high, is_n_bar_low
)


@dataclass
class LunarPhasePivot:
    """A confirmed pivot that occurred on a lunar phase or duad date."""
    date: date
    price: float
    close_price: float
    direction: str         # 'high' or 'low'
    phase_name: str        # 'New Moon', 'First Quarter', etc., or 'Duad'
    duad_sign: str         # sign of the duad
    is_phase_date: bool    # True if on exact phase date, False if on duad transit date


@dataclass
class LunarPhaseDuadSignal:
    """Trade signal from the Lunar Phase Duad strategy."""
    direction: str          # 'long' or 'short'
    signal_date: date
    entry_price: float      # breakout level
    stop_price: float       # current resistance/support on the other side
    trend: str              # 'bull' or 'bear'
    trigger_pivot: LunarPhasePivot
    signal_type: str = "lunar_phase_duad"


class LunarPhaseDuadStrategy:
    """
    Implements the 4-Phase Lunar Cycle with Duad Turn Dates (Lessons 24-25).
    """

    def __init__(self):
        self._phase_data: List[Dict] = []
        self._turn_dates: Set[date] = set()

    def initialize(self, start_date: date, end_date: date):
        """Pre-compute lunar phases and duad dates."""
        buffer_start = start_date - timedelta(days=60)
        self._phase_data = get_lunar_phase_dates(buffer_start, end_date)
        self._turn_dates = self._compute_turn_dates(buffer_start, end_date)

    def _compute_turn_dates(self, start_date: date, end_date: date) -> Set[date]:
        """
        Compute all potential turn dates: phase dates + duad transit dates.
        """
        turn_dates = set()

        for phase in self._phase_data:
            # Phase date itself
            if start_date <= phase["date"] <= end_date:
                turn_dates.add(phase["date"])

            # Duad transit dates
            duad_transits = lunar_phase_duad_dates(phase, start_date, end_date)
            for t in duad_transits:
                if start_date <= t["date"] <= end_date:
                    turn_dates.add(t["date"])

        return turn_dates

    def find_phase_pivots(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[LunarPhasePivot]:
        """
        Find all confirmed 3-bar pivots that fall on lunar phase or duad dates.
        """
        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        all_pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)
        phase_pivots = []

        # Build phase date → phase info mapping
        phase_date_map = {p["date"]: p for p in self._phase_data}

        # Build duad date → phase info mapping
        duad_date_map: Dict[date, Dict] = {}
        for phase in self._phase_data:
            for t in lunar_phase_duad_dates(phase, start_date - timedelta(days=30), end_date):
                duad_date_map[t["date"]] = phase

        for pivot in all_pivots:
            pd_ = get_date(pivot.date)
            if pd_ not in self._turn_dates:
                continue
            if not (start_date <= pd_ <= end_date):
                continue

            # Determine if it's a phase date or duad date
            if pd_ in phase_date_map:
                p_info = phase_date_map[pd_]
                pp = LunarPhasePivot(
                    date=pd_,
                    price=pivot.price,
                    close_price=pivot.close_price,
                    direction=pivot.direction,
                    phase_name=p_info["phase_name"],
                    duad_sign=p_info["sun_duad"],
                    is_phase_date=True,
                )
            elif pd_ in duad_date_map:
                p_info = duad_date_map[pd_]
                pp = LunarPhasePivot(
                    date=pd_,
                    price=pivot.price,
                    close_price=pivot.close_price,
                    direction=pivot.direction,
                    phase_name=p_info["phase_name"] + " (duad)",
                    duad_sign=p_info["sun_duad"],
                    is_phase_date=False,
                )
            else:
                continue

            phase_pivots.append(pp)

        return sorted(phase_pivots, key=lambda x: x.date)

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[LunarPhaseDuadSignal]:
        """
        Generate buy/sell signals based on breaks of confirmed lunar phase pivots.
        """
        if not self._phase_data:
            self.initialize(start_date, end_date)

        phase_pivots = self.find_phase_pivots(df, start_date, end_date)

        if not phase_pivots:
            return []

        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        signals = []

        # Track the current resistance (buy point) and support (sell point)
        # using the sequence of confirmed phase pivots
        current_resistance: Optional[LunarPhasePivot] = None
        current_support: Optional[LunarPhasePivot] = None
        trend = "neutral"

        # Seed from first two pivots
        for pp in phase_pivots:
            if pp.direction == "high" and current_resistance is None:
                current_resistance = pp
            elif pp.direction == "low" and current_support is None:
                current_support = pp
            if current_resistance and current_support:
                break

        if not current_resistance or not current_support:
            return signals

        for i, idx in enumerate(df.index):
            d = get_date(idx)
            if not (start_date <= d <= end_date):
                continue

            row = df.iloc[i]

            # Update phase pivots as they appear in time
            for pp in phase_pivots:
                if pp.date <= d:
                    if pp.direction == "high":
                        # In a bear trend, progressively LOWER the resistance
                        if trend == "bear" or current_resistance is None:
                            if current_resistance is None or pp.price < current_resistance.price:
                                current_resistance = pp
                        elif trend == "bull":
                            # Update to latest high
                            current_resistance = pp
                    else:
                        # In a bull trend, progressively RAISE the support
                        if trend == "bull" or current_support is None:
                            if current_support is None or pp.price > current_support.price:
                                current_support = pp
                        elif trend == "bear":
                            current_support = pp

            if current_resistance is None or current_support is None:
                continue

            # Check for breakout signals
            # SELL: price breaks below current support → bear trend
            if trend != "bear" and row["low"] < current_support.price:
                sig = LunarPhaseDuadSignal(
                    direction="short",
                    signal_date=d,
                    entry_price=current_support.price,
                    stop_price=current_resistance.price,
                    trend="bear",
                    trigger_pivot=current_support,
                )
                signals.append(sig)
                trend = "bear"

            # BUY: price breaks above current resistance → bull trend
            elif trend != "bull" and row["high"] > current_resistance.price:
                sig = LunarPhaseDuadSignal(
                    direction="long",
                    signal_date=d,
                    entry_price=current_resistance.price,
                    stop_price=current_support.price,
                    trend="bull",
                    trigger_pivot=current_resistance,
                )
                signals.append(sig)
                trend = "bull"

        return signals
