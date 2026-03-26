"""
Strategy 6: Golden Ratio Turning Points
Book reference: Lessons 17, 18

Logic:
  1. Mark all CONFIRMED 3-bar highs and lows on the daily chart.
  2. For each pair of adjacent extreme points (confirmed high + confirmed low):
     a. Count the number of price bars between them (N).
     b. Compute the midpoint bar.
     c. Multiply N by the Golden Number (1.618) → projected bars from midpoint.
     d. Count that many bars forward from the midpoint → projected turn date(s).
  3. A "Golden Ratio Turning Point" is confirmed when:
     - TWO OR MORE different projections converge on the SAME date (±1 bar).
     - AND a confirmed 3-bar high or low occurs on that date.
  4. Entry:
     - For a high: short on the first 3-bar downside reversal below the Golden High.
     - For a low:  buy on the first 3-bar upside reversal above the Golden Low.
  5. Price objective:
     - Subtract (initial swing range) from the Golden Ratio high (for short).
     - Add (initial swing range) to the Golden Ratio low (for long).
     - The "initial swing" is the first swing that defined the congestion range.

Golden Number = 1.618 (phi).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..utils.bar_analysis import (
    find_all_confirmed_pivots, BarReversal, is_n_bar_high, is_n_bar_low
)

GOLDEN_NUMBER = 1.618033988749895


@dataclass
class GoldenProjection:
    """A single Golden Ratio projection."""
    source_high: BarReversal
    source_low: BarReversal
    midpoint_index: int
    midpoint_date: object
    projected_bars: float       # N * 1.618
    projected_indices: Tuple[int, int]   # (floor, ceil)
    projected_dates: Tuple[object, object]


@dataclass
class GoldenRatioSignal:
    """Trade signal from a Golden Ratio turning point."""
    direction: str            # 'short' or 'long'
    signal_date: date
    entry_price: float
    stop_price: float
    target_price: float
    golden_date: date         # the convergence date
    projection_count: int     # how many projections converged
    initial_swing_range: float
    signal_type: str = "golden_ratio"


class GoldenRatioStrategy:
    """
    Implements the Golden Ratio Turning Points strategy (Lessons 17-18).
    """

    MIN_PROJECTIONS = 2  # Need at least 2 projections converging

    def compute_projections(
        self,
        pivots: List[BarReversal],
        df: pd.DataFrame,
    ) -> List[GoldenProjection]:
        """
        Compute all Golden Ratio projections from adjacent pivot pairs.
        """
        projections = []

        for i in range(len(pivots) - 1):
            p1 = pivots[i]
            p2 = pivots[i + 1]

            if p1.direction == p2.direction:
                continue  # Must alternate

            n_bars = abs(p2.index - p1.index)
            if n_bars < 2:
                continue

            # Round to nearest even for midpoint calculation (Lesson 17)
            n_even = n_bars if n_bars % 2 == 0 else n_bars + 1
            midpoint_idx = min(p1.index, p2.index) + n_even // 2
            midpoint_idx = min(midpoint_idx, len(df) - 1)

            projected_bars = n_bars * GOLDEN_NUMBER
            lo = int(projected_bars)
            hi = lo + 1

            proj_idx_lo = midpoint_idx + lo
            proj_idx_hi = midpoint_idx + hi

            if proj_idx_lo >= len(df):
                continue

            # Get actual dates for projected indices
            proj_date_lo = df.index[proj_idx_lo] if proj_idx_lo < len(df) else None
            proj_date_hi = df.index[proj_idx_hi] if proj_idx_hi < len(df) else None

            # Determine which is high and which is low
            if p1.direction == "high":
                high_p, low_p = p1, p2
            else:
                high_p, low_p = p2, p1

            proj = GoldenProjection(
                source_high=high_p,
                source_low=low_p,
                midpoint_index=midpoint_idx,
                midpoint_date=df.index[midpoint_idx],
                projected_bars=projected_bars,
                projected_indices=(proj_idx_lo, proj_idx_hi),
                projected_dates=(proj_date_lo, proj_date_hi),
            )
            projections.append(proj)

        return projections

    def find_convergences(
        self,
        projections: List[GoldenProjection],
        df: pd.DataFrame,
    ) -> Dict[int, List[GoldenProjection]]:
        """
        Find dates (indices) where 2+ projections converge.
        Returns dict: index → list of projections pointing to that index.
        """
        from collections import defaultdict
        convergence: Dict[int, List] = defaultdict(list)

        for proj in projections:
            lo, hi = proj.projected_indices
            for idx in [lo, hi]:
                if 0 <= idx < len(df):
                    convergence[idx].append(proj)

        # Also check ±1 bar from each projected index
        expanded: Dict[int, List] = defaultdict(list)
        for idx, projs in convergence.items():
            for offset in [-1, 0, 1]:
                target = idx + offset
                if 0 <= target < len(df):
                    expanded[target].extend(projs)

        # Deduplicate
        result = {}
        for idx, projs in expanded.items():
            unique_projs = list({id(p): p for p in projs}.values())
            if len(unique_projs) >= self.MIN_PROJECTIONS:
                result[idx] = unique_projs

        return result

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[GoldenRatioSignal]:
        """
        Scan for Golden Ratio turning point signals.
        """
        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)
        if len(pivots) < 4:
            return []

        projections = self.compute_projections(pivots, df)
        convergences = self.find_convergences(projections, df)

        signals = []
        pivot_by_index = {p.index: p for p in pivots}

        for conv_idx, conv_projs in convergences.items():
            if conv_idx >= len(df):
                continue

            d = get_date(df.index[conv_idx])
            if not (start_date <= d <= end_date):
                continue

            # Check if this convergence date matches a confirmed pivot
            pivot = pivot_by_index.get(conv_idx)
            if pivot is None:
                # Check ±1 bar
                for offset in [-1, 0, 1]:
                    p = pivot_by_index.get(conv_idx + offset)
                    if p is not None:
                        pivot = p
                        break

            if pivot is None:
                continue

            # Determine initial swing range from the first projection's source
            first_proj = conv_projs[0]
            initial_swing = abs(first_proj.source_high.price - first_proj.source_low.price)

            if pivot.direction == "high":
                # SHORT setup: short on first 3-bar downside reversal
                # Look for downside reversal after the convergence date
                for j in range(conv_idx + 1, min(conv_idx + 5, len(df))):
                    if is_n_bar_low(df, j, n=3, use_intraday=True):
                        entry_price = df["low"].iloc[j]
                        stop_price  = pivot.price + 0.01
                        target_price = pivot.price - initial_swing
                        sig = GoldenRatioSignal(
                            direction="short",
                            signal_date=get_date(df.index[j]),
                            entry_price=entry_price,
                            stop_price=stop_price,
                            target_price=target_price,
                            golden_date=d,
                            projection_count=len(conv_projs),
                            initial_swing_range=initial_swing,
                        )
                        signals.append(sig)
                        break

            else:  # low
                # LONG setup
                for j in range(conv_idx + 1, min(conv_idx + 5, len(df))):
                    if is_n_bar_high(df, j, n=3, use_intraday=True):
                        entry_price = df["high"].iloc[j]
                        stop_price  = pivot.price - 0.01
                        target_price = pivot.price + initial_swing
                        sig = GoldenRatioSignal(
                            direction="long",
                            signal_date=get_date(df.index[j]),
                            entry_price=entry_price,
                            stop_price=stop_price,
                            target_price=target_price,
                            golden_date=d,
                            projection_count=len(conv_projs),
                            initial_swing_range=initial_swing,
                        )
                        signals.append(sig)
                        break

        return signals
