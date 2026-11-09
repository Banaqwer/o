"""Bar schema validation and conversion between pandas frames and Bar objects."""

from __future__ import annotations

from typing import Iterable, Iterator, List

import numpy as np
import pandas as pd

from ..types import Bar

REQUIRED = ("open", "high", "low", "close", "volume")
OPTIONAL = ("buy_volume", "sell_volume")


def validate_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean, tz-aware, time-sorted copy or raise ``ValueError``."""

    if not isinstance(df.index, pd.DatetimeIndex):
        if "ts" in df.columns:
            df = df.set_index("ts")
        elif "timestamp" in df.columns:
            df = df.set_index("timestamp")
        else:
            raise ValueError("frame needs a DatetimeIndex or a 'ts'/'timestamp' column")
        df.index = pd.to_datetime(df.index, utc=True)
    if df.index.tz is None:
        raise ValueError("bar timestamps must be timezone-aware (UTC or exchange tz)")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"frame missing columns {missing}")
    out = df.copy()
    out = out[~out.index.duplicated(keep="last")].sort_index()
    for c in REQUIRED + tuple(c for c in OPTIONAL if c in out.columns):
        out[c] = out[c].astype(float)
    bad = ~((out["low"] <= out[["open", "close"]].min(axis=1)) & (out["high"] >= out[["open", "close"]].max(axis=1)))
    if bad.any():
        raise ValueError(f"{int(bad.sum())} bars with inconsistent OHLC, first at {out.index[bad][0]}")
    if (out["volume"] < 0).any():
        raise ValueError("negative volume")
    if out[list(REQUIRED)].isna().any().any():
        raise ValueError("NaN in required columns")
    return out


def iter_bars(df: pd.DataFrame) -> Iterator[Bar]:
    has_flow = "buy_volume" in df.columns and "sell_volume" in df.columns
    cols = ["open", "high", "low", "close", "volume"] + (["buy_volume", "sell_volume"] if has_flow else [])
    values = df[cols].to_numpy(dtype=float)
    for ts, row in zip(df.index.to_pydatetime(), values):
        if has_flow:
            yield Bar(ts, row[0], row[1], row[2], row[3], row[4], row[5], row[6])
        else:
            yield Bar(ts, row[0], row[1], row[2], row[3], row[4])


def bars_to_frame(bars: Iterable[Bar]) -> pd.DataFrame:
    rows: List[dict] = []
    for b in bars:
        rows.append(
            {
                "ts": b.ts,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "buy_volume": np.nan if b.buy_volume is None else b.buy_volume,
                "sell_volume": np.nan if b.sell_volume is None else b.sell_volume,
            }
        )
    df = pd.DataFrame(rows).set_index("ts")
    if df["buy_volume"].isna().all():
        df = df.drop(columns=["buy_volume", "sell_volume"])
    return df


def load_csv(path: str) -> pd.DataFrame:
    """Load bars from CSV with a ``ts``/``timestamp`` column and OHLCV columns."""

    df = pd.read_csv(path)
    col = "ts" if "ts" in df.columns else "timestamp"
    df[col] = pd.to_datetime(df[col], utc=True)
    return validate_frame(df.set_index(col))
