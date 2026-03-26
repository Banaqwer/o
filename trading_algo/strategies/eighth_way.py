"""
Strategy 2: "The 8th Way" — Aspect Flow Price Targets
Book reference: Lessons 4, 5, 6

Logic:
  1. Use the 3-bar reversal technique to identify cyclical highs and lows.
  2. Compute the price range of the prior swing (high-to-low or low-to-high).
  3. Multiply that range by the 11 aspect decimal multipliers to get support/
     resistance "aspect levels."
  4. Assess the strength of any retracement by checking which aspect level it reaches.
  5. KEY RULE — "The 8th Way":
     - If the retracement only reaches Aspect #7 (58%) → entry on a 2-bar reversal.
       Use a tick above the cycle high as stop.
       Price target = entry − risk (from entry to cycle high/low).
     - If the retracement reaches Aspect #8 (67%) or higher → wait for a 3-bar reversal.
     - If retracement fails to reach even Aspect #6 (50%) → strong trend continuation.
  6. The trade is taken in the DIRECTION of the prior swing (continuation).
     e.g., if prior swing was DOWN and retracement fails to reach Aspect #8 → SHORT.

Aspect decimal table (Lesson 5):
  #1: 30/360 = 0.0833  |  #7: 210/360 = 0.5833
  #2: 60/360 = 0.1667  |  #8: 240/360 = 0.6667
  #3: 90/360 = 0.2500  |  #9: 270/360 = 0.75
  #4: 120/360 = 0.3333 | #10: 300/360 = 0.8333
  #5: 150/360 = 0.4167 | #11: 330/360 = 0.9167
  #6: 180/360 = 0.5000
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict
import pandas as pd

from ..utils.bar_analysis import (
    find_all_confirmed_pivots, BarReversal, get_prior_confirmed_pivot
)
from ..astro.ephemeris import ASPECT_DECIMALS


@dataclass
class AspectLevel:
    """A single aspect-based price level derived from a prior swing."""
    aspect_number: int
    decimal: float
    price: float


@dataclass
class EighthWaySignal:
    """Trade signal from The 8th Way strategy."""
    direction: str           # 'short' or 'long'
    entry_date: date
    entry_price: float
    stop_price: float
    target_price: float
    reversal_bars: int       # 2 or 3 (which reversal triggered entry)
    retracement_aspect: int  # highest aspect reached by retracement (6, 7, or 8+)
    prior_swing_range: float
    prior_high_price: float
    prior_low_price: float
    signal_type: str = "eighth_way"


class EighthWayStrategy:
    """
    Implements "The 8th Way" aspect flow strategy (Lessons 4-6).
    """

    # Aspect thresholds
    ASPECT_6_DECIMAL = ASPECT_DECIMALS[6]   # 0.50  — birth of new trend
    ASPECT_7_DECIMAL = ASPECT_DECIMALS[7]   # 0.5833 — weak retracement
    ASPECT_8_DECIMAL = ASPECT_DECIMALS[8]   # 0.6667 — mature trend

    def compute_aspect_levels(
        self,
        swing_range: float,
        base_price: float,
        direction: str,
    ) -> Dict[int, AspectLevel]:
        """
        Compute all 11 aspect price levels from a swing.

        swing_range: absolute price range of the prior swing.
        base_price: the starting point of the retracement (the low if prior swing was down).
        direction: 'up' (retracement up from a low) or 'down' (retracement down from a high).
        """
        levels = {}
        for num, dec in ASPECT_DECIMALS.items():
            offset = swing_range * dec
            if direction == "up":
                price = base_price + offset
            else:
                price = base_price - offset
            levels[num] = AspectLevel(
                aspect_number=num,
                decimal=dec,
                price=price,
            )
        return levels

    def classify_retracement(
        self,
        retracement_high: float,
        base_price: float,
        swing_range: float,
        direction: str,
    ) -> int:
        """
        Return the highest aspect number reached by the retracement.
        direction: 'up' (retracement up from low) or 'down' (retracement down from high).
        """
        if direction == "up":
            retracement_size = retracement_high - base_price
        else:
            retracement_size = base_price - retracement_high

        if swing_range == 0:
            return 0

        fraction = retracement_size / swing_range
        highest_aspect = 0
        for num, dec in sorted(ASPECT_DECIMALS.items()):
            if fraction >= dec:
                highest_aspect = num
            else:
                break
        return highest_aspect

    def generate_signals(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[EighthWaySignal]:
        """
        Scan the DataFrame for 8th Way signals.

        Algorithm:
        1. Find all confirmed 3-bar pivots (highs and lows).
        2. For each pivot pair (prior high + prior low or vice versa):
           a. Compute swing range.
           b. Check if momentum is increasing on the trend side
              (key technical weakness/strength indicator from Lesson 4).
           c. On the next retracement, compute aspect levels.
           d. If retracement reaches only Aspect #7 → 2-bar reversal entry.
              If retracement fails to reach Aspect #8 → treat as weak; 2-bar entry.
           e. Set stop at tick above/below the retracement extreme.
           f. Target = entry − risk (1:1 risk-reward from entry to stop).
        """
        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        pivots = find_all_confirmed_pivots(df, n=3, use_intraday=True)
        signals = []

        # Need at least 3 pivots (alternating H-L-H or L-H-L) to check momentum
        if len(pivots) < 3:
            return signals

        for k in range(2, len(pivots)):
            pivot = pivots[k]
            pivot_prev = pivots[k - 1]
            pivot_prev2 = pivots[k - 2]

            pdate = get_date(pivot.date)
            if not (start_date <= pdate <= end_date):
                continue

            # Check for alternating pattern (H-L-H or L-H-L)
            if pivot.direction == pivot_prev.direction:
                continue

            # --- SHORT SETUP ---
            # Pattern: H(k-2) > L(k-1) > H(k) — downtrend momentum increasing
            if (pivot_prev2.direction == "high" and
                    pivot_prev.direction == "low" and
                    pivot.direction == "high"):

                prev_down_range = pivot_prev2.price - pivot_prev.price
                curr_up_range   = pivot.price - pivot_prev.price

                # Check: did the DOWN move increase momentum?
                # i.e., is there a prior down swing we can compare to?
                # From the book: momentum increases when downswing > prior downswing
                # Here we look at whether the current retracement (up) is weak
                retracement_dir = "up"
                base_price     = pivot_prev.price  # low price
                swing_range_val = prev_down_range
                retracement_max = pivot.price

                if swing_range_val <= 0:
                    continue

                highest_aspect = self.classify_retracement(
                    retracement_max, base_price, swing_range_val, retracement_dir
                )

                # Signal condition: retracement reached at most Aspect #7
                if highest_aspect <= 7:
                    reversal_n = 2 if highest_aspect <= 7 else 3

                    # Aspect levels from this low
                    levels = self.compute_aspect_levels(swing_range_val, base_price, "up")
                    aspect7_price = levels[7].price
                    aspect8_price = levels[8].price

                    # Stop = tick above the retracement high (cycle high = pivot.price)
                    stop_price  = pivot.price + 0.01
                    risk        = stop_price - base_price  # approximate
                    # Entry = retracement peak (pivot.price) minus a tick (on reversal)
                    entry_price = pivot.price - 0.01
                    # Target = entry − risk
                    target_price = entry_price - risk

                    sig = EighthWaySignal(
                        direction="short",
                        entry_date=pdate,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        reversal_bars=reversal_n,
                        retracement_aspect=highest_aspect,
                        prior_swing_range=swing_range_val,
                        prior_high_price=pivot_prev2.price,
                        prior_low_price=pivot_prev.price,
                    )
                    signals.append(sig)

            # --- LONG SETUP ---
            # Pattern: L(k-2) < H(k-1) < L(k) — uptrend momentum
            elif (pivot_prev2.direction == "low" and
                    pivot_prev.direction == "high" and
                    pivot.direction == "low"):

                prev_up_range   = pivot_prev.price - pivot_prev2.price
                curr_down_range = pivot_prev.price - pivot.price

                retracement_dir = "down"
                base_price      = pivot_prev.price  # high price
                swing_range_val = prev_up_range
                retracement_min = pivot.price

                if swing_range_val <= 0:
                    continue

                highest_aspect = self.classify_retracement(
                    retracement_min, base_price, swing_range_val, retracement_dir
                )

                if highest_aspect <= 7:
                    reversal_n = 2 if highest_aspect <= 7 else 3

                    stop_price  = pivot.price - 0.01
                    risk        = base_price - stop_price
                    entry_price = pivot.price + 0.01
                    target_price = entry_price + risk

                    sig = EighthWaySignal(
                        direction="long",
                        entry_date=pdate,
                        entry_price=entry_price,
                        stop_price=stop_price,
                        target_price=target_price,
                        reversal_bars=reversal_n,
                        retracement_aspect=highest_aspect,
                        prior_swing_range=swing_range_val,
                        prior_high_price=pivot_prev.price,
                        prior_low_price=pivot_prev2.price,
                    )
                    signals.append(sig)

        return signals
