"""London Strategic Edge -- the Terminal's ``/vault`` data calls.

Keys issued for the LSE Terminal / older Databank (``lse_live_...``) are not
known to the LSE Data 3.0 service, but the API reference states that the
Terminal keeps its data calls at ``api.londonstrategicedge.com``:
``/vault/catalog``, ``/vault/candles``, ``/vault/usage``, ``/vault/meta``.

Observed contract (probed live, 9 November 2026):

* key in ``X-API-Key``; ``/vault/usage`` reports ``calls_per_minute`` (60 on
  the free plan), ``max_rows_per_request`` (5000), byte caps per week and month;
* ``/vault/catalog`` lists every instrument with ``dataset`` (futures, index,
  commodity, fx, crypto, stocks, etf, ...), ``symbol`` (``NASDAQ100.F``,
  ``GOLD.F``, ``SP500.F``, ``XAU/USD``), tick counts and history bounds;
* ``/vault/candles?symbol=&dataset=&timeframe=&start=&end=&limit=`` answers a
  JSON list of ``{ts, symbol, open, high, low, close[, volume]}``; ``ts`` is
  UTC, ``start``/``end`` take dates or ``YYYY-MM-DD HH:MM:SS`` with ``end``
  exclusive, at most 5000 rows per call -- so a range is paged by moving
  ``start`` past the last row received.

Futures candles carry volume (continuous front-month series); FX and
commodity spot candles do not, and the engine then falls back to its
volume-free paths.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Union

import pandas as pd

from .http import HttpClient, Response
from .lse import ENV_KEYS, LSEError, _fmt_date

VAULT_BASE = "https://api.londonstrategicedge.com/vault"
VAULT_TIMEFRAMES = ("1s", "5s", "15s", "30s", "1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1mo")
_TF_SECONDS = {"1s": 1, "5s": 5, "15s": 15, "30s": 30, "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 7 * 86400, "1mo": 31 * 86400}

DateLike = Union[str, date, datetime]


class VaultClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        http: Optional[HttpClient] = None,
        base_url: str = VAULT_BASE,
        calls_per_minute: int = 60,
        max_rows: int = 5000,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        key = api_key or next((os.environ[k] for k in ENV_KEYS if os.environ.get(k)), None)
        if not key:
            raise LSEError(401, "key-missing", "set LSE_API_KEY or pass api_key")
        self.api_key = key
        self.http = http or HttpClient()
        self.base_url = base_url.rstrip("/")
        self.max_rows = max_rows
        self.sleep = sleep
        self.clock = clock
        self._min_interval = 60.0 / max(calls_per_minute, 1)
        self._last_call = -1e9

    def _pace(self) -> None:
        wait = self._min_interval - (self.clock() - self._last_call)
        if wait > 0:
            self.sleep(wait)
        self._last_call = self.clock()

    def _get(self, path: str, params: Optional[dict] = None, retries_429: int = 3) -> Response:
        url = HttpClient.build_url(f"{self.base_url}/{path.lstrip('/')}", params)
        for attempt in range(retries_429 + 1):
            self._pace()
            resp = self.http.get(url, headers={"X-API-Key": self.api_key, "Accept": "application/json"})
            if resp.status == 429 and attempt < retries_429:
                self.sleep(resp.retry_after(5.0))
                continue
            if resp.ok:
                return resp
            try:
                body = resp.json()
            except Exception:
                body = {}
            detail = body.get("detail") if isinstance(body, dict) else None
            raise LSEError(resp.status, body.get("code", "vault-error") if isinstance(body, dict) else "vault-error", str(detail or body or resp.text()[:200]), body=body if isinstance(body, dict) else {})
        raise LSEError(resp.status, "calls-exhausted", "rate limit persisted")

    # ------------------------------------------------------------------ calls
    def usage(self) -> dict:
        return self._get("usage").json()

    def meta(self) -> dict:
        return self._get("meta").json()

    def catalog(self, dataset: Optional[str] = None) -> pd.DataFrame:
        rows = self._get("catalog").json()
        df = pd.DataFrame(rows)
        if dataset is not None and not df.empty:
            df = df[df["dataset"] == dataset]
        return df.reset_index(drop=True)

    def candles_page(self, symbol: str, dataset: str, timeframe: str, start: DateLike, end: DateLike, limit: Optional[int] = None) -> List[dict]:
        params = {"symbol": symbol, "dataset": dataset, "timeframe": timeframe, "start": _fmt_date(start), "end": _fmt_date(end), "limit": limit or self.max_rows}
        return self._get("candles", params).json()

    def candles(self, symbol: str, dataset: str, timeframe: str, start: DateLike, end: DateLike, progress: Optional[Callable[[int, str], None]] = None) -> pd.DataFrame:
        """All candles in [start, end), paged past the server's per-call row cap."""

        if timeframe not in VAULT_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {VAULT_TIMEFRAMES}")
        step = timedelta(seconds=_TF_SECONDS[timeframe])
        cursor: DateLike = start
        end_ts = pd.Timestamp(_fmt_date(end))
        frames: List[pd.DataFrame] = []
        total = 0
        while True:
            rows = self.candles_page(symbol, dataset, timeframe, cursor, end, self.max_rows)
            if not rows:
                break
            page = pd.DataFrame(rows)
            frames.append(page)
            total += len(page)
            last = pd.Timestamp(page["ts"].iloc[-1])
            if progress:
                progress(total, str(last))
            if len(rows) < self.max_rows or last + step >= end_ts:
                break
            cursor = (last + step).to_pydatetime()
        if not frames:
            return vault_to_frame(pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]))
        return vault_to_frame(pd.concat(frames, ignore_index=True))


def vault_to_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Map vault candle rows to the engine schema (UTC index, float OHLCV)."""

    if raw.empty:
        idx = pd.DatetimeIndex([], tz="UTC", name="ts")
        return pd.DataFrame({c: pd.Series(dtype=float) for c in ("open", "high", "low", "close", "volume")}, index=idx)
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.drop(columns=[c for c in ("symbol",) if c in df.columns]).set_index("ts").sort_index()
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0).astype(float)
    else:
        df["volume"] = 0.0
    df = df[~df.index.duplicated(keep="last")]
    # the feed occasionally prints a bar whose open/close sit a tick outside [low, high]; widen the range
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df[["open", "high", "low", "close", "volume"]]


# Catalogue symbols for the instruments the engine targets.
VAULT_SYMBOLS: Dict[str, tuple] = {
    "NQ": ("NASDAQ100.F", "futures"),
    "MNQ": ("MICRONASDAQ100.F", "futures"),
    "ES": ("SP500.F", "futures"),
    "MES": ("MICROSP500.F", "futures"),
    "YM": ("DOW.F", "futures"),
    "RTY": ("RUSSELL2000.F", "futures"),
    "GC": ("GOLD.F", "futures"),
    "SI": ("SILVER.F", "futures"),
    "HG": ("COPPER.F", "futures"),
    "PL": ("PLATINUM.F", "futures"),
}
