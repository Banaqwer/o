"""
Candlestick pattern detection.

Patterns used in the book:
  - Bearish Engulfing (Lessons 15, 16, 21, 22, 23): occurs in an uptrend.
    Day 2's body completely engulfs Day 1's body.
    Day 2 opens ABOVE Day 1's body high and closes BELOW Day 1's body low.
  - Bullish Engulfing (Lesson 16, 22, 23): occurs in a downtrend.
    Day 2's body completely engulfs Day 1's body.
    Day 2 opens BELOW Day 1's body low and closes ABOVE Day 1's body high.

Key rule: only the BODY (open-close range) matters, not the shadows (wicks).
"""

import pandas as pd
from typing import Optional


def candlestick_body_high(row: pd.Series) -> float:
    """Return the higher of open and close (body top)."""
    return max(row["open"], row["close"])


def candlestick_body_low(row: pd.Series) -> float:
    """Return the lower of open and close (body bottom)."""
    return min(row["open"], row["close"])


def is_bearish_engulfing(
    prev_row: pd.Series,
    curr_row: pd.Series,
    require_3bar_high: bool = False,
) -> bool:
    """
    Return True if curr_row is a bearish engulfing candlestick vs prev_row.

    Rules (Lesson 15):
    1. curr_row opens ABOVE prev_row's body high (above prior body)
    2. curr_row closes BELOW prev_row's body low (closes below prior body)
    3. curr_row is a dark/filled body (close < open)
    4. prev_row is a white/empty body (close > open) — optional in book
       but implied (prior bar in uptrend)

    Signals: as soon as price drops a tick below prev_row body_low.
    In code we use: curr_close < prev_body_low as trigger condition.
    """
    prev_body_high = candlestick_body_high(prev_row)
    prev_body_low  = candlestick_body_low(prev_row)

    curr_open  = curr_row["open"]
    curr_close = curr_row["close"]

    # Curr opens above prior body AND closes below prior body
    opened_above = curr_open > prev_body_high
    closed_below = curr_close < prev_body_low

    return opened_above and closed_below


def is_bullish_engulfing(
    prev_row: pd.Series,
    curr_row: pd.Series,
) -> bool:
    """
    Return True if curr_row is a bullish engulfing candlestick vs prev_row.

    1. curr_row opens BELOW prev_row's body low
    2. curr_row closes ABOVE prev_row's body high
    3. curr_row is a white/empty body (close > open)
    """
    prev_body_high = candlestick_body_high(prev_row)
    prev_body_low  = candlestick_body_low(prev_row)

    curr_open  = curr_row["open"]
    curr_close = curr_row["close"]

    opened_below = curr_open  < prev_body_low
    closed_above = curr_close > prev_body_high

    return opened_below and closed_above


def bearish_engulfing_entry_price(
    prev_row: pd.Series,
    tick: float = 0.01,
) -> float:
    """
    Entry price for a bearish engulfing short:
    a tick below the prior day's body low.
    (Lesson 15: 'shorted at a tick below prior day's body')
    """
    return candlestick_body_low(prev_row) - tick


def bearish_engulfing_stop_price(
    signal_row: pd.Series,
    tick: float = 0.01,
) -> float:
    """
    Stop price for a bearish engulfing short:
    a tick above the signal day's HIGH (intraday high, not body).
    (Lesson 16 correction: 'protective buy stop at a tick above signal day's high')
    """
    return signal_row["high"] + tick


def bullish_engulfing_entry_price(
    prev_row: pd.Series,
    tick: float = 0.01,
) -> float:
    """Entry price for a bullish engulfing long: tick above prior body high."""
    return candlestick_body_high(prev_row) + tick


def bullish_engulfing_stop_price(
    signal_row: pd.Series,
    tick: float = 0.01,
) -> float:
    """Stop price for a bullish engulfing long: tick below signal day's LOW."""
    return signal_row["low"] - tick


def engulfing_price_target(
    entry_price: float,
    stop_price: float,
    direction: str,
    risk_multiplier: float = 2.0,
) -> float:
    """
    Price objective = entry ± (risk * multiplier).
    Risk = abs(entry - stop).
    For short: target = entry - risk * multiplier.
    For long:  target = entry + risk * multiplier.
    (Lesson 16: always 2:1 risk-reward ratio)
    """
    risk = abs(entry_price - stop_price)
    if direction == "short":
        return entry_price - risk * risk_multiplier
    else:
        return entry_price + risk * risk_multiplier
