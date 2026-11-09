"""Daily market context from FRED and the French library.

The source material says engine behaviour is conditional on market regime:
volatility expansion, liquidity deterioration, correlation breakdown. Those
are visible at the daily frequency in public data, so this module builds a
small daily context frame and offers it in two ways:

* as an **exogenous regime input** -- the standardised log-VIX enters the
  regime component's width multiplier for the session, read from the
  *previous* trading day's close so nothing from the session itself leaks in;
* as **conditioning columns** on the event log, so reaction statistics can
  be cut by VIX regime, term-structure state or recent market factor returns.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ..data.sources.fred import fetch_many
from ..data.sources.french import fetch_factors
from ..data.sources.http import HttpClient

CONTEXT_COLUMNS = (
    "vix",
    "vix_z",
    "vix_pct_1y",
    "term_spread",
    "index_ret_20d",
    "index_vol_20d",
    "index_dd_63d",
    "mkt_ret_20d",
    "mkt_vol_20d",
)


@dataclass(frozen=True)
class ContextSnapshot:
    asof: date
    vix: float
    vix_z: float
    vix_pct_1y: float
    term_spread: float
    index_ret_20d: float
    index_vol_20d: float
    index_dd_63d: float
    mkt_ret_20d: float
    mkt_vol_20d: float

    def as_dict(self) -> Dict[str, float]:
        d = asdict(self)
        d["asof"] = self.asof.isoformat()
        return d


def build_context_frame(fred: pd.DataFrame, factors: Optional[pd.DataFrame] = None, index_id: str = "NASDAQ100") -> pd.DataFrame:
    """Compute context features; every row at date d uses data through d's close."""

    df = pd.DataFrame(index=fred.index.copy())
    vix = fred["VIXCLS"].astype(float).ffill()
    df["vix"] = vix
    lv = np.log(vix)
    roll = lv.rolling(252, min_periods=60)
    df["vix_z"] = (lv - roll.mean()) / roll.std()
    df["vix_pct_1y"] = lv.rolling(252, min_periods=60).apply(lambda w: float((w[:-1] < w[-1]).mean()) if len(w) > 1 else np.nan, raw=True)
    if "T10Y2Y" in fred.columns:
        df["term_spread"] = fred["T10Y2Y"].astype(float).ffill()
    elif {"DGS10", "DGS2"} <= set(fred.columns):
        df["term_spread"] = (fred["DGS10"] - fred["DGS2"]).astype(float).ffill()
    else:
        df["term_spread"] = np.nan
    if index_id in fred.columns:
        px = fred[index_id].astype(float).ffill()
        r = np.log(px).diff()
        df["index_ret_20d"] = np.log(px / px.shift(20))
        df["index_vol_20d"] = r.rolling(20, min_periods=10).std() * np.sqrt(252)
        df["index_dd_63d"] = px / px.rolling(63, min_periods=20).max() - 1.0
    else:
        df["index_ret_20d"] = df["index_vol_20d"] = df["index_dd_63d"] = np.nan
    if factors is not None and "Mkt-RF" in factors.columns:
        mkt = (factors["Mkt-RF"] + factors.get("RF", 0.0)).reindex(df.index)
        df["mkt_ret_20d"] = mkt.rolling(20, min_periods=10).sum()
        df["mkt_vol_20d"] = mkt.rolling(20, min_periods=10).std() * np.sqrt(252)
    else:
        df["mkt_ret_20d"] = df["mkt_vol_20d"] = np.nan
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df[list(CONTEXT_COLUMNS)]


class DailyContext:
    def __init__(self, frame: pd.DataFrame):
        missing = [c for c in CONTEXT_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(f"context frame missing {missing}")
        f = frame.copy()
        f.index = pd.to_datetime(f.index).tz_localize(None).normalize()
        self.frame = f.sort_index()

    @classmethod
    def fetch(cls, start: str = "2010-01-01", index_id: str = "NASDAQ100", http: Optional[HttpClient] = None, with_factors: bool = True) -> "DailyContext":
        http = http or HttpClient()
        ids = ["VIXCLS", "T10Y2Y", index_id]
        fred = fetch_many(ids, start=start, http=http)
        factors = fetch_factors("ff3_daily", http=http) if with_factors else None
        return cls(build_context_frame(fred, factors, index_id))

    @classmethod
    def from_csv(cls, path: str) -> "DailyContext":
        return cls(pd.read_csv(path, index_col=0, parse_dates=True))

    def to_csv(self, path: str) -> None:
        self.frame.to_csv(path)

    def for_session(self, session_date: date) -> Optional[ContextSnapshot]:
        """Context known before the session opens: the last row strictly before ``session_date``."""

        ts = pd.Timestamp(session_date)
        prior = self.frame.loc[self.frame.index < ts]
        if prior.empty:
            return None
        row = prior.iloc[-1]
        if not np.isfinite(row["vix"]):
            return None
        vals = {c: (float(row[c]) if np.isfinite(row[c]) else 0.0) for c in CONTEXT_COLUMNS}
        return ContextSnapshot(asof=prior.index[-1].date(), **vals)

    def join_events(self, events: pd.DataFrame) -> pd.DataFrame:
        """Attach ``ctx_*`` columns to an event frame by its ``session_date``."""

        if events.empty:
            return events
        out = events.copy()
        snaps = {d: self.for_session(pd.Timestamp(d).date()) for d in out["session_date"].unique()}
        for c in CONTEXT_COLUMNS:
            out[f"ctx_{c}"] = out["session_date"].map(lambda d: getattr(snaps[d], c) if snaps[d] else np.nan)
        out["ctx_asof"] = out["session_date"].map(lambda d: snaps[d].asof.isoformat() if snaps[d] else None)
        return out
