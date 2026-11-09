import json
from datetime import datetime, timedelta

import pandas as pd
import pytest

from atm_engine.data.sources.http import HttpClient, Response
from atm_engine.data.sources.lse import LSEError
from atm_engine.data.sources.lse_vault import VAULT_SYMBOLS, VaultClient, vault_to_frame


class FakeVault:
    """Scripted /vault server: 1-minute bars from 2026-11-05 00:00 UTC, capped rows per call."""

    def __init__(self, n_bars=12, cap=5):
        self.cap = cap
        self.t0 = datetime(2026, 11, 5, 0, 0)
        self.bars = [self.t0 + timedelta(minutes=i) for i in range(n_bars)]
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        assert headers.get("X-API-Key") == "k-vault"
        from urllib.parse import parse_qs, urlparse

        u = urlparse(url)
        if u.path.endswith("/vault/usage"):
            return Response(200, {}, json.dumps({"calls_per_minute": 60, "max_rows_per_request": 5000}).encode())
        if u.path.endswith("/vault/catalog"):
            return Response(200, {}, json.dumps([
                {"dataset": "futures", "symbol": "NASDAQ100.F", "name": "Nasdaq 100 Futures", "first_tick": "2017-04-02 00:00:00", "last_tick": "2026-11-09 18:54:00"},
                {"dataset": "fx", "symbol": "EUR/USD", "name": "Euro / US Dollar", "first_tick": "2009-09-25", "last_tick": "2026-11-09"},
            ]).encode())
        if u.path.endswith("/vault/candles"):
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if "symbol" not in q:
                return Response(422, {}, json.dumps({"detail": "symbol required"}).encode())
            start = datetime.strptime(q["start"][:19], "%Y-%m-%d %H:%M:%S") if len(q["start"]) > 10 else datetime.strptime(q["start"], "%Y-%m-%d")
            end = datetime.strptime(q["end"][:19], "%Y-%m-%d %H:%M:%S") if len(q["end"]) > 10 else datetime.strptime(q["end"], "%Y-%m-%d")
            limit = min(int(q.get("limit", 5000)), self.cap)
            rows = [
                {"ts": t.strftime("%Y-%m-%d %H:%M:%S.000000"), "symbol": q["symbol"], "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i, "volume": 10 + i}
                for i, t in enumerate(self.bars) if start <= t < end
            ][:limit]
            return Response(200, {}, json.dumps(rows).encode())
        return Response(404, {}, b"{}")


def make(srv, **kw):
    t = {"now": 0.0}
    return VaultClient(api_key="k-vault", http=HttpClient(transport=srv), sleep=lambda s: t.__setitem__("now", t["now"] + s), clock=lambda: t["now"], **kw), t


def test_vault_pages_past_row_cap_without_gaps_or_overlap():
    srv = FakeVault(n_bars=12, cap=5)
    client, _ = make(srv, max_rows=5)
    df = client.candles("NASDAQ100.F", "futures", "1m", "2026-11-05", "2026-11-06")
    assert len(df) == 12
    assert df.index[0] == pd.Timestamp("2026-11-05 00:00", tz="UTC") and df.index[-1] == pd.Timestamp("2026-11-05 00:11", tz="UTC")
    assert (df.index.to_series().diff().dropna() == pd.Timedelta(minutes=1)).all()
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len([c for c in srv.calls if "/vault/candles" in c]) == 3  # 5 + 5 + 2


def test_vault_end_is_exclusive_and_empty_range_returns_empty_frame():
    client, _ = make(FakeVault(), max_rows=5)
    df = client.candles("NASDAQ100.F", "futures", "1m", "2026-11-05 00:00:00", "2026-11-05 00:03:00")
    assert len(df) == 3
    empty = client.candles("NASDAQ100.F", "futures", "1m", "2026-12-01", "2026-12-02")
    assert empty.empty and str(empty.index.tz) == "UTC"


def test_vault_catalog_filter_and_symbol_map():
    client, _ = make(FakeVault())
    cat = client.catalog("futures")
    assert list(cat["symbol"]) == ["NASDAQ100.F"]
    assert VAULT_SYMBOLS["NQ"] == ("NASDAQ100.F", "futures") and VAULT_SYMBOLS["GC"] == ("GOLD.F", "futures")


def test_vault_to_frame_fixes_range_and_missing_volume():
    raw = pd.DataFrame([
        {"ts": "2026-11-05 00:00:00.000000", "symbol": "EUR/USD", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.1},
    ])
    df = vault_to_frame(raw)
    assert df["high"].iloc[0] == 1.1 and df["volume"].iloc[0] == 0.0


def test_vault_requires_key(monkeypatch):
    monkeypatch.delenv("LSE_API_KEY", raising=False)
    monkeypatch.delenv("LSE_KEY", raising=False)
    with pytest.raises(LSEError):
        VaultClient()


def test_vault_surfaces_422_detail():
    client, _ = make(FakeVault())
    with pytest.raises(LSEError) as e:
        client._get("candles", {"dataset": "futures"})
    assert e.value.status == 422 and "symbol" in e.value.message
