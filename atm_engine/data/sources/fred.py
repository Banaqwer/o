"""FRED (Federal Reserve Bank of St. Louis) daily series.

Uses the public ``fredgraph.csv`` endpoint, which needs no API key. Missing
observations are published as ``.`` and become NaN. One request per series:
the multi-series form of the endpoint answers a zip archive instead of CSV.
"""

from __future__ import annotations

import io
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from .http import HttpClient

FRED_GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Series relevant to an index / metals futures reversal engine.
DEFAULT_SERIES: Dict[str, str] = {
    "SP500": "S&P 500 index, daily close",
    "NASDAQ100": "Nasdaq-100 index, daily close",
    "DJIA": "Dow Jones Industrial Average, daily close",
    "VIXCLS": "CBOE Volatility Index (VIX), daily close",
    "DGS2": "2-year Treasury constant maturity yield",
    "DGS10": "10-year Treasury constant maturity yield",
    "T10Y2Y": "10-year minus 2-year Treasury spread",
    "DFF": "Effective federal funds rate",
    "DTWEXBGS": "Trade-weighted US dollar index, broad",
    "BAMLH0A0HYM2": "ICE BofA US high-yield option-adjusted spread",
}


def parse_fredgraph_csv(text: str, series_id: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    if series_id not in df.columns:
        raise ValueError(f"series {series_id!r} not in columns {list(df.columns)}")
    s = pd.Series(df[series_id].astype(float).to_numpy(), index=pd.to_datetime(df[date_col]), name=series_id)
    s.index.name = "date"
    return s


def fetch_series(
    series_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    http: Optional[HttpClient] = None,
) -> pd.Series:
    http = http or HttpClient()
    url = HttpClient.build_url(FRED_GRAPH, {"id": series_id, "cosd": start, "coed": end})
    resp = http.get(url, use_cache=http.cache_dir is not None)
    if not resp.ok:
        raise RuntimeError(f"FRED {series_id}: HTTP {resp.status}")
    text = resp.text()
    if not text.lstrip().startswith("observation_date"):
        raise RuntimeError(f"FRED {series_id}: unexpected payload (series id unknown or discontinued?)")
    return parse_fredgraph_csv(text, series_id)


def fetch_many(
    series_ids: Iterable[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    http: Optional[HttpClient] = None,
) -> pd.DataFrame:
    http = http or HttpClient()
    cols = [fetch_series(s, start, end, http) for s in series_ids]
    df = pd.concat(cols, axis=1).sort_index()
    df.index.name = "date"
    return df
