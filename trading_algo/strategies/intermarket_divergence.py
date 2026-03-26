"""
Strategy 10: Intermarket Divergence Analysis
Book reference: Lessons 26, 27

Logic:
  1. Compare two historically correlated stocks/ETFs (e.g., SPY vs. QQQ).
  2. Mark confirmed 3-bar highs and lows for BOTH stocks.
  3. NEGATIVE DIVERGENCE (bearish):
     - Stock A makes a new confirmed high ABOVE its prior high.
     - Stock B fails to make a new confirmed high ABOVE its prior high
       (only reaches a 2-bar reversal, or stops below).
     - BOTH stocks then break DOWN through their respective lows on the same day.
     → SHORT signal.
  4. POSITIVE DIVERGENCE (bullish):
     - Stock A makes a new confirmed low BELOW its prior low.
     - Stock B fails to make a new confirmed low BELOW its prior low
       (higher low = divergence).
     - BOTH stocks then break UP through their respective highs on the same day.
     → LONG signal.
  5. Entry: when BOTH break in the same direction on the same day.
  6. Stop: most recent opposite extreme for the position.
  7. Key rule: during congestion periods, a 2-bar reversal from one stock
     can substitute for a 3-bar reversal for confirmation.

Cyclical analysis should always be considered alongside this divergence analysis
(the book recommends combining with Solar/Lunar indicators).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional, Dict, Tuple
import pandas as pd

from ..utils.bar_analysis import (
    find_all_confirmed_pivots, BarReversal,
    is_n_bar_high, is_n_bar_low
)


@dataclass
class DivergenceEvent:
    """A detected intermarket divergence between two stocks."""
    type: str           # 'positive' or 'negative'
    start_date: date
    end_date: date      # date of confirmation break
    symbol_a: str
    symbol_b: str
    # Stock A pivots (leading stock)
    a_new_extreme: BarReversal
    a_prior_extreme: BarReversal
    # Stock B divergence (failing to match A)
    b_best_pivot: Optional[BarReversal]   # B's best attempt (may be 2-bar)
    b_prior_extreme: Optional[BarReversal]
    is_confirmed: bool = False
    confirmation_date: Optional[date] = None


@dataclass
class DivergenceSignal:
    """Trade signal from the Intermarket Divergence strategy."""
    direction: str           # 'short' (negative divergence) or 'long' (positive)
    signal_date: date
    entry_price_a: float     # entry for symbol A
    entry_price_b: float     # entry for symbol B
    stop_price_a: float
    stop_price_b: float
    divergence: DivergenceEvent
    signal_type: str = "intermarket_divergence"


class IntermarketDivergenceStrategy:
    """
    Implements Intermarket Divergence Analysis (Lessons 26-27).
    Tracks two correlated symbols and identifies divergence breaks.
    """

    LOOKBACK_PIVOTS = 10  # Number of prior pivots to check for divergence

    def __init__(self, symbol_a: str, symbol_b: str):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b

    def detect_divergences(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[DivergenceEvent]:
        """
        Detect all positive and negative divergences between the two stocks.
        """
        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        pivots_a = find_all_confirmed_pivots(df_a, n=3, use_intraday=True)
        pivots_b = find_all_confirmed_pivots(df_b, n=3, use_intraday=True)

        # Also track 2-bar reversals for Stock B (used in congestion)
        pivots_b_2bar = find_all_confirmed_pivots(df_b, n=2, use_intraday=True)

        # Build date-indexed pivot lookup for B (both 3-bar and 2-bar)
        b_pivot_by_date_3 = {get_date(p.date): p for p in pivots_b}
        b_pivot_by_date_2 = {get_date(p.date): p for p in pivots_b_2bar}

        divergences = []

        for k in range(1, len(pivots_a)):
            pa_curr = pivots_a[k]
            pa_prev = pivots_a[k - 1]

            if pa_curr.direction != pa_prev.direction:
                continue  # Need same direction to compare new vs prior

            pa_curr_date = get_date(pa_curr.date)
            if not (start_date <= pa_curr_date <= end_date):
                continue

            # Find Stock B's pivot near the same time window
            window_start = get_date(pa_prev.date)
            window_end   = pa_curr_date

            # Look for B pivot in same window
            pb_in_window = [
                p for p in pivots_b
                if window_start <= get_date(p.date) <= window_end
                and p.direction == pa_curr.direction
            ]
            # Also check 2-bar reversals for B
            pb_2bar_in_window = [
                p for p in pivots_b_2bar
                if window_start <= get_date(p.date) <= window_end
                and p.direction == pa_curr.direction
            ]

            if not pb_in_window and not pb_2bar_in_window:
                continue

            # Best B pivot in window
            all_b_pivots_window = pb_in_window or pb_2bar_in_window
            if pa_curr.direction == "high":
                pb_best = max(all_b_pivots_window, key=lambda p: p.price)
            else:
                pb_best = min(all_b_pivots_window, key=lambda p: p.price)

            # Find Stock B's prior equivalent pivot (before the window)
            pb_prior_in_window = [
                p for p in pivots_b
                if get_date(p.date) < window_start
                and p.direction == pa_curr.direction
            ]
            pb_prior = pb_prior_in_window[-1] if pb_prior_in_window else None

            if pa_curr.direction == "high":
                # NEGATIVE divergence check:
                # A makes a higher high; B fails to make a higher high
                a_higher = pa_curr.price > pa_prev.price
                b_lower  = (pb_best.price <= (pb_prior.price if pb_prior else pb_best.price))

                if a_higher and b_lower:
                    div = DivergenceEvent(
                        type="negative",
                        start_date=window_start,
                        end_date=pa_curr_date,
                        symbol_a=self.symbol_a,
                        symbol_b=self.symbol_b,
                        a_new_extreme=pa_curr,
                        a_prior_extreme=pa_prev,
                        b_best_pivot=pb_best,
                        b_prior_extreme=pb_prior,
                    )
                    divergences.append(div)

            else:  # "low"
                # POSITIVE divergence check:
                # A makes a lower low; B fails to make a lower low (higher low)
                a_lower = pa_curr.price < pa_prev.price
                b_higher = (pb_best.price >= (pb_prior.price if pb_prior else pb_best.price))

                if a_lower and b_higher:
                    div = DivergenceEvent(
                        type="positive",
                        start_date=window_start,
                        end_date=pa_curr_date,
                        symbol_a=self.symbol_a,
                        symbol_b=self.symbol_b,
                        a_new_extreme=pa_curr,
                        a_prior_extreme=pa_prev,
                        b_best_pivot=pb_best,
                        b_prior_extreme=pb_prior,
                    )
                    divergences.append(div)

        return divergences

    def confirm_divergences(
        self,
        divergences: List[DivergenceEvent],
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
    ) -> List[DivergenceEvent]:
        """
        Confirm divergences: both stocks must break in the same direction
        on the SAME DAY within a few days of detection.
        (Lesson 27: confirmation comes when both break prior days' lows/highs together.)
        """
        def get_date(idx):
            return idx.date() if hasattr(idx, "date") else idx

        confirmed = []
        for div in divergences:
            # Look for simultaneous break within 3 days of divergence end date
            check_start = pd.Timestamp(div.end_date)
            check_end   = pd.Timestamp(div.end_date + timedelta(days=5))

            df_a_check = df_a[(df_a.index >= check_start) & (df_a.index <= check_end)]
            df_b_check = df_b[(df_b.index >= check_start) & (df_b.index <= check_end)]

            if df_a_check.empty or df_b_check.empty:
                continue

            for i in range(1, min(len(df_a_check), len(df_b_check))):
                d_a = get_date(df_a_check.index[i])
                d_b = get_date(df_b_check.index[i])

                if d_a != d_b:
                    continue

                row_a = df_a_check.iloc[i]
                row_b = df_b_check.iloc[i]
                prev_a = df_a_check.iloc[i - 1]
                prev_b = df_b_check.iloc[i - 1]

                if div.type == "negative":
                    # Both break prior day's lows
                    if (row_a["low"] < prev_a["low"] and
                            row_b["low"] < prev_b["low"]):
                        div.is_confirmed = True
                        div.confirmation_date = d_a
                        confirmed.append(div)
                        break

                else:  # positive
                    # Both break prior day's highs
                    if (row_a["high"] > prev_a["high"] and
                            row_b["high"] > prev_b["high"]):
                        div.is_confirmed = True
                        div.confirmation_date = d_a
                        confirmed.append(div)
                        break

        return confirmed

    def generate_signals(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> List[DivergenceSignal]:
        """
        Detect divergences, confirm them, and generate trade signals.
        """
        divergences  = self.detect_divergences(df_a, df_b, start_date, end_date)
        confirmed    = self.confirm_divergences(divergences, df_a, df_b)

        signals = []
        for div in confirmed:
            d = div.confirmation_date
            if not d:
                continue

            # Get prices at confirmation date
            ts = pd.Timestamp(d)
            row_a = df_a[df_a.index.date == d].iloc[-1] if hasattr(df_a.index, 'date') else (
                df_a[df_a.index == ts].iloc[-1] if ts in df_a.index else None
            )
            row_b = df_b[df_b.index.date == d].iloc[-1] if hasattr(df_b.index, 'date') else (
                df_b[df_b.index == ts].iloc[-1] if ts in df_b.index else None
            )

            if row_a is None or row_b is None:
                continue

            if div.type == "negative":
                entry_a = row_a["low"]
                entry_b = row_b["low"]
                stop_a  = div.a_new_extreme.price + 0.01
                stop_b  = div.b_best_pivot.price + 0.01 if div.b_best_pivot else entry_b * 1.02

                sig = DivergenceSignal(
                    direction="short",
                    signal_date=d,
                    entry_price_a=entry_a,
                    entry_price_b=entry_b,
                    stop_price_a=stop_a,
                    stop_price_b=stop_b,
                    divergence=div,
                )

            else:  # positive
                entry_a = row_a["high"]
                entry_b = row_b["high"]
                stop_a  = div.a_new_extreme.price - 0.01
                stop_b  = div.b_best_pivot.price - 0.01 if div.b_best_pivot else entry_b * 0.98

                sig = DivergenceSignal(
                    direction="long",
                    signal_date=d,
                    entry_price_a=entry_a,
                    entry_price_b=entry_b,
                    stop_price_a=stop_a,
                    stop_price_b=stop_b,
                    divergence=div,
                )

            signals.append(sig)

        return signals
