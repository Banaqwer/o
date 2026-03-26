"""
Price data loader.

Provides daily and intraday OHLCV DataFrames with standardized columns:
  open, high, low, close, volume

Columns are lowercase. Index is DatetimeIndex.
"""

import pandas as pd
import numpy as np
from datetime import date, datetime
from typing import Optional


def load_price_data(
    symbol: str,
    start_date,
    end_date,
    interval: str = "1d",
    source: str = "yfinance",
) -> pd.DataFrame:
    """
    Load OHLCV data for a symbol.

    interval: '1d', '60m', '30m', '15m'
    source: 'yfinance' (default) or 'csv:<filepath>'

    Returns DataFrame with columns: open, high, low, close, volume
    Index: DatetimeIndex (timezone-aware UTC for intraday)
    """
    if source == "yfinance":
        return _load_yfinance(symbol, start_date, end_date, interval)
    elif source.startswith("csv:"):
        filepath = source[4:]
        return _load_csv(filepath)
    else:
        raise ValueError(f"Unknown data source: {source}")


def _load_yfinance(symbol, start_date, end_date, interval):
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance is not installed. Run: pip install yfinance")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=str(start_date), end=str(end_date), interval=interval)

    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index.name = "date"
    return df


def _load_csv(filepath: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV file."""
    df = pd.read_csv(filepath, parse_dates=True, index_col=0)
    df.columns = [c.lower() for c in df.columns]
    if "open" not in df.columns:
        raise ValueError("CSV must have columns: open, high, low, close, volume")
    return df


def resample_to_timeframe(
    df: pd.DataFrame,
    timeframe: str,
) -> pd.DataFrame:
    """
    Resample a higher-frequency DataFrame to a lower frequency.
    timeframe: 'D' (daily), '60T' (60-min), '30T' (30-min), '15T' (15-min)
    """
    resampled = df.resample(timeframe).agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }).dropna()
    return resampled


def get_date(row_index) -> date:
    """Extract a date from a DataFrame index entry (handles both date and datetime)."""
    if isinstance(row_index, datetime):
        return row_index.date()
    if isinstance(row_index, pd.Timestamp):
        return row_index.date()
    return row_index
