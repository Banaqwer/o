from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from atm_engine.config import SessionConfig
from atm_engine.data.schema import bars_to_frame, iter_bars, validate_frame
from atm_engine.data.sessions import SessionClock, minutes_since_open
from atm_engine.data.synthetic import SyntheticSpec, generate


def test_synthetic_is_deterministic_and_labelled():
    a = generate(SyntheticSpec(sessions=2, seed=5))
    b = generate(SyntheticSpec(sessions=2, seed=5))
    pd.testing.assert_frame_equal(a, b)
    assert a.attrs["synthetic"] is True
    assert (a["buy_volume"] + a["sell_volume"] - a["volume"]).abs().max() <= 1.0


def test_synthetic_ohlc_consistent(bars):
    v = validate_frame(bars)
    assert len(v) == len(bars)
    assert (v["high"] >= v[["open", "close"]].max(axis=1)).all()


def test_validate_frame_rejects_bad_ohlc(bars):
    bad = bars.copy()
    bad.iloc[0, bad.columns.get_loc("high")] = bad.iloc[0]["low"] - 1
    with pytest.raises(ValueError):
        validate_frame(bad)


def test_validate_frame_requires_tz():
    idx = pd.date_range("2024-01-02 09:30", periods=3, freq="1min")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    with pytest.raises(ValueError):
        validate_frame(df)


def test_roundtrip_bars(bars):
    bs = list(iter_bars(validate_frame(bars.head(5))))
    assert len(bs) == 5 and bs[0].buy_volume is not None
    back = bars_to_frame(bs)
    assert list(back.columns) == ["open", "high", "low", "close", "volume", "buy_volume", "sell_volume"]


def test_session_clock_labels_rth_and_open_bar():
    cfg = SessionConfig()
    clock = SessionClock(cfg)
    tz = ZoneInfo(cfg.tz)
    pre = datetime(2024, 1, 3, 9, 29, tzinfo=tz)
    open_ = datetime(2024, 1, 3, 9, 30, tzinfo=tz)
    later = datetime(2024, 1, 3, 9, 31, tzinfo=tz)
    post = datetime(2024, 1, 3, 16, 5, tzinfo=tz)
    s0 = clock.stamp(pre)
    assert not s0.in_rth and not s0.is_open_bar and s0.session_date.isoformat() == "2024-01-03"
    s1 = clock.stamp(open_)
    assert s1.in_rth and s1.is_open_bar
    s2 = clock.stamp(later)
    assert s2.in_rth and not s2.is_open_bar
    s3 = clock.stamp(post)
    assert not s3.in_rth and s3.session_date.isoformat() == "2024-01-04"  # rolls to next session
    # Friday after close rolls to Monday
    fri = datetime(2024, 1, 5, 18, 0, tzinfo=tz)
    assert clock.stamp(fri).session_date.isoformat() == "2024-01-08"
    assert minutes_since_open(later, cfg) == 1.0


def test_session_clock_handles_utc_input():
    cfg = SessionConfig()
    clock = SessionClock(cfg)
    ts = datetime(2024, 7, 10, 13, 30, tzinfo=ZoneInfo("UTC"))  # 09:30 EDT
    s = clock.stamp(ts)
    assert s.in_rth and s.is_open_bar
