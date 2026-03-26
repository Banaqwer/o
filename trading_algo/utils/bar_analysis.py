"""
3-Bar Reversal Engine.

Core price-action tools used by every strategy in the book.

Definitions (Lesson 4, 5, 6, 7, 8, 9):
  - N-bar high  : current bar's high > prior N bars' highs
  - N-bar low   : current bar's low  < prior N bars' lows
  - Confirmed N-bar high : an N-bar high immediately followed by an N-bar downside reversal
  - Confirmed N-bar low  : an N-bar low  immediately followed by an N-bar upside reversal
  - N-bar downside reversal: bar's low < prior N bars' lows (after a prior N-bar high)
  - N-bar upside reversal  : bar's high > prior N bars' highs (after a prior N-bar low)

The default N = 3.  N = 2 is also used in specific circumstances.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class BarReversal:
    """Represents a confirmed pivot high or low."""
    index: int                   # pandas index position
    date: object                 # date or datetime of the pivot
    price: float                 # intraday extreme (high or low)
    close_price: float           # closing price
    direction: str               # 'high' or 'low'
    n_bars: int                  # N used for the reversal (2 or 3)
    is_confirmed: bool = False   # True once immediately followed by reversal
    confirmation_index: int = -1 # index of the bar that confirmed it
    confirmation_date: object = None
    in_solar_window: bool = False  # True if pivot occurred in Solar Time Window


def is_n_bar_high(
    df: pd.DataFrame,
    i: int,
    n: int = 3,
    use_intraday: bool = True,
) -> bool:
    """
    Return True if bar at index i has a higher high than the prior n bars.

    df must have columns: 'high', 'close'.
    If use_intraday=True, compare intraday highs.
    If use_intraday=False, compare closing highs only.
    """
    if i < n:
        return False
    col = "high" if use_intraday else "close"
    current = df[col].iloc[i]
    prior = df[col].iloc[i - n: i]
    return bool(current > prior.max())


def is_n_bar_low(
    df: pd.DataFrame,
    i: int,
    n: int = 3,
    use_intraday: bool = True,
) -> bool:
    """
    Return True if bar at index i has a lower low than the prior n bars.
    """
    if i < n:
        return False
    col = "low" if use_intraday else "close"
    current = df[col].iloc[i]
    prior = df[col].iloc[i - n: i]
    return bool(current < prior.min())


def find_confirmed_highs(
    df: pd.DataFrame,
    n: int = 3,
    use_intraday: bool = True,
    solar_window_dates: Optional[set] = None,
) -> List[BarReversal]:
    """
    Scan a price DataFrame and return all CONFIRMED N-bar highs.

    A confirmed N-bar high requires:
    1. Bar i is an N-bar high
    2. A subsequent bar j (j > i, no confirmed low between them) is an N-bar low
       (i.e., goes below prior N bars' lows), which confirms bar i as a pivot high.

    solar_window_dates: optional set of dates; if provided, marks pivots that
    occur within a Solar Time Window.
    """
    highs = []
    col_high = "high" if use_intraday else "close"
    col_low  = "low"  if use_intraday else "close"
    dates = df.index.tolist()

    # Identify all N-bar highs and lows first
    bar_highs = [i for i in range(n, len(df)) if is_n_bar_high(df, i, n, use_intraday)]
    bar_lows  = [i for i in range(n, len(df)) if is_n_bar_low(df, i, n, use_intraday)]

    confirmed = []
    i = 0
    n_bars = len(df)

    while i < n_bars:
        if is_n_bar_high(df, i, n, use_intraday):
            pivot_price = df[col_high].iloc[i]
            pivot_close = df["close"].iloc[i]
            pivot_date  = dates[i]

            # Look for immediate N-bar low confirmation
            for j in range(i + 1, min(i + n + 5, n_bars)):
                if is_n_bar_low(df, j, n, use_intraday):
                    d = dates[i]
                    in_window = (solar_window_dates is not None) and (
                        d.date() if hasattr(d, "date") else d) in solar_window_dates
                    rev = BarReversal(
                        index=i,
                        date=pivot_date,
                        price=pivot_price,
                        close_price=pivot_close,
                        direction="high",
                        n_bars=n,
                        is_confirmed=True,
                        confirmation_index=j,
                        confirmation_date=dates[j],
                        in_solar_window=in_window,
                    )
                    confirmed.append(rev)
                    break

        i += 1

    return confirmed


def find_confirmed_lows(
    df: pd.DataFrame,
    n: int = 3,
    use_intraday: bool = True,
    solar_window_dates: Optional[set] = None,
) -> List[BarReversal]:
    """
    Scan a price DataFrame and return all CONFIRMED N-bar lows.
    """
    col_low  = "low"  if use_intraday else "close"
    col_high = "high" if use_intraday else "close"
    dates = df.index.tolist()

    confirmed = []
    n_bars = len(df)
    i = 0

    while i < n_bars:
        if is_n_bar_low(df, i, n, use_intraday):
            pivot_price = df[col_low].iloc[i]
            pivot_close = df["close"].iloc[i]
            pivot_date  = dates[i]

            for j in range(i + 1, min(i + n + 5, n_bars)):
                if is_n_bar_high(df, j, n, use_intraday):
                    d = dates[i]
                    in_window = (solar_window_dates is not None) and (
                        d.date() if hasattr(d, "date") else d) in solar_window_dates
                    rev = BarReversal(
                        index=i,
                        date=pivot_date,
                        price=pivot_price,
                        close_price=pivot_close,
                        direction="low",
                        n_bars=n,
                        is_confirmed=True,
                        confirmation_index=j,
                        confirmation_date=dates[j],
                        in_solar_window=in_window,
                    )
                    confirmed.append(rev)
                    break

        i += 1

    return confirmed


def find_all_confirmed_pivots(
    df: pd.DataFrame,
    n: int = 3,
    use_intraday: bool = True,
    solar_window_dates: Optional[set] = None,
) -> List[BarReversal]:
    """
    Return all confirmed highs and lows, sorted by index.
    Filters out overlapping pivots (keeps only those that are
    confirmed by an IMMEDIATE reversal — first reversal after the pivot).
    """
    highs = find_confirmed_highs(df, n, use_intraday, solar_window_dates)
    lows  = find_confirmed_lows(df, n, use_intraday, solar_window_dates)

    all_pivots = sorted(highs + lows, key=lambda x: x.index)
    return all_pivots


def get_prior_confirmed_pivot(
    pivots: List[BarReversal],
    current_index: int,
    direction: str,
) -> Optional[BarReversal]:
    """
    Return the most recent confirmed pivot of given direction ('high' or 'low')
    before current_index.
    """
    for p in reversed(pivots):
        if p.index < current_index and p.direction == direction:
            return p
    return None


def swing_range(high_pivot: BarReversal, low_pivot: BarReversal) -> float:
    """Return the absolute price difference between a high and low pivot."""
    return abs(high_pivot.price - low_pivot.price)
