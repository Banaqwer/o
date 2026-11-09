"""London Strategic Edge -- LSE Data 3.0 client for candles.

Written against the published API reference
(https://londonstrategicedge.com/api-documentation):

* one HTTPS service, every call a GET under
  ``https://download.londonstrategicedge.com/v3`` with the key in the
  ``X-API-Key`` header; a free key is issued on the Databank;
* the selection: ``market``, ``symbol`` or ``pair_id``, ``data`` (candles),
  ``timeframe`` (tick, 1s ... 1m ... 1d, 1w, 1mo), ``from``/``to`` as dates
  or UTC timestamps, ``format`` csv|parquet, ``adjusted``;
* candle columns: ``time, open, high, low, close, volume, trades``; times are UTC;
* ``/v3/export`` streams a file up to 100 MB within 10 s, otherwise answers
  202 with a job to poll at ``/v3/jobs/{id}`` and fetch at ``/v3/jobs/{id}/file``;
* limits on the free plan: 60 calls a minute, one download at a time,
  2,500,000 rows an export, 12,500,000 rows a day, 12.5 GiB a week;
* the free ``futures`` market lists contract families (e.g. ``SP500``,
  ``CRUDEOIL``); CME Globex contracts (``ESZ6``, ``NQZ6``) need a CME plan.

Only the calls the engine needs are implemented. The official Python client
(``pip install lse-data``) covers the whole surface; this module exists so
the engine has no dependency beyond the standard library and pandas and so
its behaviour under refusals is tested here.
"""

from __future__ import annotations

import hashlib
import io
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Union

import pandas as pd

from .http import HttpClient, Response

BASE_URL = "https://download.londonstrategicedge.com/v3"
ENV_KEYS = ("LSE_API_KEY", "LSE_KEY")
TIMEFRAMES = ("tick", "1s", "5s", "15s", "30s", "1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1mo")
FREE_ROWS_PER_EXPORT = 2_500_000

DateLike = Union[str, date, datetime]


class LSEError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, required_plan: Optional[dict] = None, body: Optional[dict] = None):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.required_plan = required_plan
        self.body = body or {}


@dataclass(frozen=True)
class Job:
    job_id: str
    status: str
    filename: str
    bytes: int
    checksum: Optional[str]
    status_url: str
    download_url: str
    error: Optional[str] = None


def _fmt_date(d: DateLike) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


class LSEClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        http: Optional[HttpClient] = None,
        base_url: str = BASE_URL,
        calls_per_minute: int = 60,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        job_poll_seconds: float = 2.0,
        job_timeout_seconds: float = 900.0,
    ):
        key = api_key or next((os.environ[k] for k in ENV_KEYS if os.environ.get(k)), None)
        if not key:
            raise LSEError(401, "key-missing", "set LSE_API_KEY (free key from the Databank) or pass api_key")
        self.api_key = key
        self.http = http or HttpClient()
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep
        self.clock = clock
        self.job_poll_seconds = job_poll_seconds
        self.job_timeout_seconds = job_timeout_seconds
        self._min_interval = 60.0 / max(calls_per_minute, 1)
        self._last_call = -1e9

    # ----------------------------------------------------------------- plumbing
    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key, "Accept": "application/json, text/csv"}

    def _pace(self) -> None:
        wait = self._min_interval - (self.clock() - self._last_call)
        if wait > 0:
            self.sleep(wait)
        self._last_call = self.clock()

    def _url(self, path: str) -> str:
        """Resolve a call path; the server's own job URLs come back as ``/v3/jobs/...``."""
        if path.startswith("http://") or path.startswith("https://"):
            origin = self.base_url.rsplit("/v3", 1)[0]
            if not path.startswith(origin + "/"):
                raise LSEError(400, "url-foreign", f"refusing to follow {path}: not on {origin}")
            return path
        p = path.lstrip("/")
        if p.startswith("v3/"):
            p = p[3:]
        return f"{self.base_url}/{p}"

    def _get(self, path: str, params: Optional[dict] = None, allow: tuple = (200,), retries_429: int = 3) -> Response:
        url = HttpClient.build_url(self._url(path), params)
        for attempt in range(retries_429 + 1):
            self._pace()
            resp = self.http.get(url, headers=self._headers())
            if resp.status == 429 and attempt < retries_429:
                self.sleep(resp.retry_after(5.0))
                continue
            if resp.status in allow:
                return resp
            raise self._error(resp)
        raise self._error(resp)

    @staticmethod
    def _error(resp: Response) -> LSEError:
        try:
            body = resp.json()
        except Exception:
            body = {}
        return LSEError(resp.status, body.get("code", "http-error"), body.get("message", resp.text()[:200]), body.get("required_plan"), body)

    # ------------------------------------------------------------------ service
    def health(self) -> dict:
        return self._get("health").json()

    def usage(self) -> dict:
        return self._get("usage").json()

    def markets(self) -> dict:
        return self._get("markets").json()

    def pairs(self, market: Optional[str] = None, q: Optional[str] = None, symbol: Optional[str] = None, limit: int = 100, offset: int = 0, **filters) -> dict:
        params = {"market": market, "q": q, "symbol": symbol, "limit": limit, "offset": offset, **filters}
        return self._get("pairs", params).json()

    def overview(self, market: str, symbol: str) -> dict:
        return self._get("overview", {"market": market, "symbol": symbol}).json()

    # -------------------------------------------------------------- market data
    def preview(self, market: str, symbol: str, timeframe: str = "1m", start: Optional[DateLike] = None, end: Optional[DateLike] = None) -> pd.DataFrame:
        params = {"market": market, "symbol": symbol, "timeframe": timeframe, "data": "candles"}
        if start is not None and end is not None:
            params["from"], params["to"] = _fmt_date(start), _fmt_date(end)
        body = self._get("preview", params).json()
        return candles_to_frame(pd.DataFrame(body.get("rows") or [], columns=body.get("columns")))

    def estimate(self, market: str, symbol: str, timeframe: str, start: DateLike, end: DateLike, fmt: str = "csv") -> dict:
        params = {"market": market, "symbol": symbol, "timeframe": timeframe, "data": "candles", "from": _fmt_date(start), "to": _fmt_date(end), "format": fmt}
        return self._get("estimate", params).json()

    def export_bytes(self, market: str, symbol: str, timeframe: str, start: DateLike, end: DateLike, adjusted: bool = True) -> bytes:
        """CSV bytes of the selection, following a 202 job when the server prepares one."""

        params = {
            "market": market,
            "symbol": symbol,
            "timeframe": timeframe,
            "data": "candles",
            "from": _fmt_date(start),
            "to": _fmt_date(end),
            "format": "csv",
            "adjusted": 1 if adjusted else 0,
        }
        resp = self._get("export", params, allow=(200, 202))
        if resp.status == 200:
            _verify_checksum(resp)
            return resp.body
        job = _job_from(resp.json())
        return self._wait_for_job(job)

    def _wait_for_job(self, job: Job) -> bytes:
        deadline = self.clock() + self.job_timeout_seconds
        while job.status in ("building", "queued"):
            if self.clock() > deadline:
                raise LSEError(504, "timeout", f"job {job.job_id} still {job.status} after {self.job_timeout_seconds}s")
            self.sleep(self.job_poll_seconds)
            job = _job_from(self._get(job.status_url).json())
        if job.status != "ready":
            raise LSEError(409, "export-failed", job.error or f"job {job.job_id} ended {job.status}")
        resp = self._get(job.download_url, allow=(200,))
        if job.checksum and hashlib.sha256(resp.body).hexdigest() != job.checksum:
            raise LSEError(500, "checksum-mismatch", f"job {job.job_id} file does not match its SHA-256")
        return resp.body

    def candles(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        start: DateLike,
        end: DateLike,
        rows_per_export: int = FREE_ROWS_PER_EXPORT,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Candles as an engine-ready frame, split into exports that respect the plan's row cap."""

        if timeframe not in TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {TIMEFRAMES}")
        windows = self._plan_windows(market, symbol, timeframe, _as_date(start), _as_date(end), rows_per_export)
        parts: List[pd.DataFrame] = []
        for a, b in windows:
            try:
                raw = self.export_bytes(market, symbol, timeframe, a, b, adjusted=adjusted)
            except LSEError as e:
                if e.code == "data-unavailable":
                    continue
                raise
            parts.append(candles_to_frame(pd.read_csv(io.BytesIO(raw))))
        if not parts:
            return candles_to_frame(pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume", "trades"]))
        df = pd.concat(parts)
        return df[~df.index.duplicated(keep="last")].sort_index()

    def _plan_windows(self, market: str, symbol: str, timeframe: str, start: date, end: date, cap: int) -> List[tuple]:
        """Bisect the date range until each window's estimated rows fit one export."""

        out: List[tuple] = []
        stack = [(start, end)]
        while stack:
            a, b = stack.pop()
            est = self.estimate(market, symbol, timeframe, a, b)
            rows = int(est.get("rows") or 0)
            if rows == 0:
                continue  # nothing stored in this window (e.g. a weekend)
            if rows <= cap or a == b:
                out.append((a, b))
                continue
            mid = a + (b - a) / 2
            stack.append((mid + timedelta(days=1), b))
            stack.append((a, mid))
        return sorted(out)


def _as_date(d: DateLike) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


def _job_from(body: dict) -> Job:
    return Job(
        job_id=body["job_id"],
        status=body.get("status", "building"),
        filename=body.get("filename", ""),
        bytes=int(body.get("bytes") or 0),
        checksum=body.get("checksum"),
        status_url=body.get("status_url") or f"jobs/{body['job_id']}",
        download_url=body.get("download_url") or f"jobs/{body['job_id']}/file",
        error=body.get("error"),
    )


def _verify_checksum(resp: Response) -> None:
    expected = resp.headers.get("x-checksum-sha256")
    if expected and hashlib.sha256(resp.body).hexdigest() != expected.strip('"'):
        raise LSEError(500, "checksum-mismatch", "streamed file does not match x-checksum-sha256")


def candles_to_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Map LSE candle rows (time UTC, open, high, low, close, volume, trades) to the engine schema."""

    if raw.empty:
        idx = pd.DatetimeIndex([], tz="UTC", name="ts")
        return pd.DataFrame({c: pd.Series(dtype=float) for c in ("open", "high", "low", "close", "volume", "trades")}, index=idx)
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["time"], utc=True)
    df = df.drop(columns=["time"]).set_index("ts").sort_index()
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    if "trades" in df.columns:
        df["trades"] = pd.to_numeric(df["trades"], errors="coerce")
    df["volume"] = df["volume"].fillna(0.0)
    return df[~df.index.duplicated(keep="last")]


def load_bars(symbol: str, start: DateLike, end: DateLike, market: str = "futures", timeframe: str = "1m", api_key: Optional[str] = None, **kw) -> pd.DataFrame:
    """One-call convenience: engine-ready bars for a symbol."""

    return LSEClient(api_key=api_key, **kw).candles(market, symbol, timeframe, start, end)
