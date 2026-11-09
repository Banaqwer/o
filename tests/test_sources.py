import hashlib
import io
import json
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from atm_engine.data.sources import fred, french, lse
from atm_engine.data.sources.http import HttpClient, Response

# ------------------------------------------------------------------ FRED

FRED_TEXT = """observation_date,VIXCLS
2024-01-02,13.20
2024-01-03,14.04
2024-01-04,.
2024-01-05,13.35
"""


def test_parse_fredgraph_csv_handles_missing_dot():
    s = fred.parse_fredgraph_csv(FRED_TEXT, "VIXCLS")
    assert s.name == "VIXCLS" and len(s) == 4
    assert np.isnan(s.loc["2024-01-04"]) and s.loc["2024-01-05"] == 13.35
    assert s.index.name == "date"


def test_fetch_series_builds_url_and_rejects_html():
    seen = {}

    def transport(url, headers, timeout):
        seen["url"] = url
        return Response(200, {}, FRED_TEXT.encode())

    s = fred.fetch_series("VIXCLS", start="2024-01-01", http=HttpClient(transport=transport))
    assert "id=VIXCLS" in seen["url"] and "cosd=2024-01-01" in seen["url"]
    assert len(s) == 4

    def html(url, headers, timeout):
        return Response(200, {}, b"<!DOCTYPE html><html>not a series</html>")

    with pytest.raises(RuntimeError):
        fred.fetch_series("GOLDAMGBD228NLBM", http=HttpClient(transport=html))


# ---------------------------------------------------------------- French

FRENCH_TEXT = """This file was created by using the 202609 CRSP database.
The Tbill return is the simple daily rate.

,Mkt-RF,SMB,HML,RF
19260701,    0.09,   -0.23,   -0.28,    0.01
19260702,    0.45,   -0.34,   -0.03,    0.01
19260706,  -99.99,    0.29,   -0.38,    0.01

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""


def test_parse_french_csv_percent_to_decimal_and_missing():
    df = french.parse_french_csv(FRENCH_TEXT)
    assert list(df.columns) == ["Mkt-RF", "SMB", "HML", "RF"]
    assert df.index[0] == pd.Timestamp("1926-07-01")
    assert abs(df["Mkt-RF"].iloc[0] - 0.0009) < 1e-12
    assert np.isnan(df["Mkt-RF"].iloc[2])
    assert len(df) == 3


def test_fetch_factors_reads_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("F-F_Research_Data_Factors_daily.csv", FRENCH_TEXT)

    def transport(url, headers, timeout):
        assert url.endswith("F-F_Research_Data_Factors_daily_CSV.zip")
        return Response(200, {}, buf.getvalue())

    df = french.fetch_factors("ff3_daily", http=HttpClient(transport=transport))
    assert len(df) == 3
    with pytest.raises(KeyError):
        french.fetch_factors("nope")


# ------------------------------------------------------------------ HTTP


def test_http_client_retries_503_then_succeeds():
    calls = []
    sleeps = []

    def transport(url, headers, timeout):
        calls.append(url)
        if len(calls) == 1:
            return Response(503, {"retry-after": "7"}, b"busy")
        return Response(200, {}, b"ok")

    c = HttpClient(transport=transport, sleep=sleeps.append)
    r = c.get("https://x/y")
    assert r.ok and len(calls) == 2 and sleeps == [7.0]


def test_http_client_disk_cache(tmp_path):
    n = {"calls": 0}

    def transport(url, headers, timeout):
        n["calls"] += 1
        return Response(200, {}, b"payload")

    c = HttpClient(transport=transport, cache_dir=tmp_path)
    assert c.get("https://x/a", use_cache=True).body == b"payload"
    assert c.get("https://x/a", use_cache=True).headers.get("x-cache") == "hit"
    assert n["calls"] == 1


# ------------------------------------------------------------------- LSE

CANDLES_CSV = (
    '"time","open","high","low","close","volume","trades"\n'
    '"2026-10-08 13:30:00",6700.25,6702.0,6699.5,6701.0,1520,310\n'
    '"2026-10-08 13:31:00",6701.0,6703.25,6700.75,6702.5,1210,255\n'
)


class FakeLSE:
    """Scripted LSE Data 3.0 server."""

    def __init__(self):
        self.calls = []
        self.job_polls = 0
        self.rows_for_window = 100

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers)))
        assert headers.get("X-API-Key") == "k-test"
        path = url.split("/v3/", 1)[1]
        if path.startswith("usage"):
            return self._json({"plan": "free", "calls_per_minute": 60})
        if path.startswith("estimate"):
            return self._json({"rows": self.rows_for_window, "estimated_bytes": 1000, "mode": "stream"})
        if path.startswith("preview"):
            return self._json({"columns": ["time", "open", "high", "low", "close", "volume", "trades"], "rows": [
                {"time": "2026-10-08 13:30:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10, "trades": 2}]})
        if path.startswith("export") and "symbol=PAID" in path:
            return Response(403, {}, json.dumps({"code": "plan-required", "message": "This feed requires a subscription",
                                                 "required_plan": {"market": "cme", "tier": "lite"}}).encode())
        if path.startswith("export") and "symbol=EMPTY" in path:
            return Response(404, {}, json.dumps({"code": "data-unavailable", "message": "none"}).encode())
        if path.startswith("export") and "symbol=JOB" in path:
            return Response(202, {}, json.dumps({"job_id": "j1", "status": "building", "filename": "f.csv", "bytes": 0,
                                                 "checksum": None, "status_url": "/v3/jobs/j1", "download_url": "/v3/jobs/j1/file"}).encode())
        if path.startswith("export") and "symbol=LIMIT" in path:
            if not hasattr(self, "_hit"):
                self._hit = True
                return Response(429, {"retry-after": "3"}, json.dumps({"code": "calls-exhausted", "message": "wait"}).encode())
            return self._csv(CANDLES_CSV)
        if path.startswith("export"):
            return self._csv(CANDLES_CSV)
        if path == "jobs/j1":
            self.job_polls += 1
            if self.job_polls < 2:
                return self._json({"job_id": "j1", "status": "building", "status_url": "/v3/jobs/j1", "download_url": "/v3/jobs/j1/file"})
            return self._json({"job_id": "j1", "status": "ready", "bytes": len(CANDLES_CSV),
                               "checksum": hashlib.sha256(CANDLES_CSV.encode()).hexdigest(),
                               "status_url": "/v3/jobs/j1", "download_url": "/v3/jobs/j1/file"})
        if path == "jobs/j1/file":
            return self._csv(CANDLES_CSV)
        return Response(404, {}, json.dumps({"code": "unknown", "message": path}).encode())

    @staticmethod
    def _json(obj):
        return Response(200, {"content-type": "application/json"}, json.dumps(obj).encode())

    @staticmethod
    def _csv(text):
        return Response(200, {"content-type": "text/csv", "x-checksum-sha256": hashlib.sha256(text.encode()).hexdigest()}, text.encode())


def make_client(server, **kw):
    t = {"now": 0.0}

    def clock():
        return t["now"]

    def sleep(s):
        t["now"] += s

    return lse.LSEClient(api_key="k-test", http=HttpClient(transport=server), sleep=sleep, clock=clock, job_poll_seconds=1.0, **kw), t


def test_lse_requires_key(monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.delenv("LSE_KEY", raising=False)
    with pytest.raises(lse.LSEError) as e:
        lse.LSEClient()
    assert e.value.code == "key-missing"


def test_lse_candles_streamed_and_mapped_to_engine_schema():
    srv = FakeLSE()
    client, _ = make_client(srv)
    df = client.candles("futures", "SP500", "1m", "2026-10-08", "2026-10-08")
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "trades"]
    assert str(df.index.tz) == "UTC" and df.index.name == "ts"
    assert df.index[0] == pd.Timestamp("2026-10-08 13:30:00", tz="UTC")
    assert df["volume"].dtype == float and df.loc[df.index[1], "close"] == 6702.5
    # key travelled in the header, and the selection in the query string
    url, headers = [c for c in srv.calls if "/v3/export" in c[0]][0]
    assert headers["X-API-Key"] == "k-test"
    assert "market=futures" in url and "symbol=SP500" in url and "timeframe=1m" in url and "format=csv" in url


def test_lse_follows_202_job_and_verifies_checksum():
    srv = FakeLSE()
    client, t = make_client(srv)
    raw = client.export_bytes("futures", "JOB", "1m", "2026-10-08", "2026-10-08")
    assert raw.decode() == CANDLES_CSV and srv.job_polls == 2


def test_lse_waits_on_429_then_retries():
    srv = FakeLSE()
    client, t = make_client(srv)
    raw = client.export_bytes("futures", "LIMIT", "1m", "2026-10-08", "2026-10-08")
    assert raw.decode() == CANDLES_CSV
    assert t["now"] >= 3.0  # honoured Retry-After


def test_lse_paid_market_refusal_surfaces_required_plan():
    srv = FakeLSE()
    client, _ = make_client(srv)
    with pytest.raises(lse.LSEError) as e:
        client.export_bytes("cme", "PAID", "1m", "2026-10-08", "2026-10-08")
    assert e.value.status == 403 and e.value.code == "plan-required" and e.value.required_plan["tier"] == "lite"


def test_lse_candles_skips_windows_without_data():
    srv = FakeLSE()
    client, _ = make_client(srv)
    df = client.candles("futures", "EMPTY", "1m", "2026-10-08", "2026-10-08")
    assert df.empty and str(df.index.tz) == "UTC"


def test_lse_splits_range_to_respect_row_cap():
    srv = FakeLSE()
    srv.rows_for_window = 1_000
    client, _ = make_client(srv)
    windows = client._plan_windows("futures", "SP500", "1m", date(2026, 1, 1), date(2026, 1, 31), cap=600)
    assert len(windows) >= 2
    assert windows[0][0] == date(2026, 1, 1) and windows[-1][1] == date(2026, 1, 31)
    for (a, b), (c, d) in zip(windows, windows[1:]):
        assert b < c  # non-overlapping, ordered


def test_lse_paces_calls_per_minute():
    srv = FakeLSE()
    client, t = make_client(srv, calls_per_minute=60)
    client.usage()
    client.usage()
    assert t["now"] >= 1.0  # second call waited for the 1 s interval
