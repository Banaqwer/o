from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from atm_engine.config import config_for
from atm_engine.features.ote import OTEConfig, OTEState, _Aggregator, _SwingDetector, Leg
from atm_engine.research.execution import ExecutionSpec, simulate
from atm_engine.research.ote_strategy import run_ote
from atm_engine.types import Bar, Direction

TZ = ZoneInfo("America/New_York")


def mk(i, o, h, l, c, start=datetime(2024, 1, 3, 9, 30, tzinfo=TZ)):
    return Bar(start + timedelta(minutes=i), o, h, l, c, 100.0)


def test_aggregator_closes_on_clock_boundaries():
    agg = _Aggregator(5, "America/New_York")
    bars = [mk(i, 100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(11)]
    done = [agg.update(b) for b in bars]
    closed = [d for d in done if d is not None]
    assert len(closed) == 2  # 09:30-09:34 and 09:35-09:39 closed; 09:40 still open
    first = closed[0]
    assert first.open == 100 and first.high == 105 and first.low == 99 and first.close == 104.5
    assert first.ts == bars[0].ts


def test_swing_detector_confirms_with_lag():
    det = _SwingDetector(2)
    highs = [100, 101, 105, 101, 100, 99, 98]
    out = []
    for i, h in enumerate(highs):
        out.append(det.update(mk(i, h - 1, h, h - 2, h - 1)))
    # the swing high at index 2 is only confirmed once bar index 4 (2 bars later) has arrived
    assert out[4] and out[4][0].is_high and out[4][0].price == 105 and out[4][0].index == 3
    assert not any(out[:4])


def test_leg_levels_and_retrace_fraction():
    leg = Leg(Direction.BUYING, origin=100.0, extreme=110.0, origin_ts=None, extreme_ts=None, confirmed_at=0, displacement_sigma=5, chop=0.1)
    assert leg.level(0.0) == 110.0 and leg.level(1.0) == 100.0 and abs(leg.level(0.705) - 102.95) < 1e-9
    assert abs(leg.retrace_fraction(103.8) - 0.62) < 1e-9
    short = Leg(Direction.SELLING, origin=110.0, extreme=100.0, origin_ts=None, extreme_ts=None, confirmed_at=0, displacement_sigma=5, chop=0.1)
    assert abs(short.level(0.705) - 107.05) < 1e-9 and abs(short.retrace_fraction(107.9) - 0.79) < 1e-9


def synthetic_impulse_and_retest():
    """5-minute structure: base, impulsive leg up 100->140, pullback into 0.62-0.79, then up."""
    path = []
    # base: a V over 30 minutes (lows fall to ~95.5 then recover) so a unique 5m swing low exists
    for i in range(30):
        lo = 100 - 0.3 * i if i < 15 else 95.5 + 0.3 * (i - 15)
        path.append((lo + 1.0, lo + 1.5, lo, lo + 0.8))
    # impulse: 40 minutes straight up to 140 (clean)
    for i in range(40):
        p = 100 + (i + 1) * 1.0
        path.append((p - 1, p + 0.5, p - 1.2, p))
    # top: 15 minutes of a small cap
    for i in range(15):
        path.append((139.5, 140.0 - (i % 2) * 0.2, 138.5, 139.2))
    # pullback: 30 minutes down to 112 (0.70 of a 40-pt leg from 140)
    for i in range(30):
        p = 139 - (i + 1) * 0.9
        path.append((p + 0.9, p + 1.0, p - 0.3, p))
    # consolidation inside the zone (111-115) for 15 minutes
    for i in range(15):
        path.append((112.5, 113.5, 111.5, 112.5 + (i % 2) * 0.5))
    # resume up to 150
    for i in range(40):
        p = 112 + (i + 1) * 1.0
        path.append((p - 1, p + 0.5, p - 1.2, p))
    return path


def frame_from_path(path, start="2024-01-03 09:30"):
    idx = pd.date_range(start, periods=len(path), freq="1min", tz="America/New_York").tz_convert("UTC")
    df = pd.DataFrame(path, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 100.0
    return df


def test_ote_detects_leg_retest_and_signals_once():
    cfg = OTEConfig(leg_minutes=5, swing_width=2, min_displacement_sigma=1.0, require_bias=False, confirmation="close_inside", touch_level=0.62)
    st = OTEState(cfg)
    sigs = []
    df = frame_from_path(synthetic_impulse_and_retest())
    from atm_engine.data.schema import iter_bars

    for k, bar in enumerate(iter_bars(df)):
        sigs.extend(st.update(bar, rho=5.0, minutes_since_open=k))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.direction is Direction.BUYING
    assert 95 <= s.origin <= 96 and 140 <= s.extreme <= 141
    assert s.stop_price < s.origin and s.target_price == s.extreme
    assert 0.62 <= s.deepest <= 0.8
    assert s.bars_since_leg > 0 and s.entry_reference == pytest.approx(s.extreme - 0.705 * (s.extreme - s.origin))
    # the signal prints after the retest, which is after the leg was confirmed, which is after the top
    assert s.ts > df.index[85]


def test_ote_bias_gate_blocks_signal():
    cfg = OTEConfig(leg_minutes=5, swing_width=2, min_displacement_sigma=1.0, require_bias=True)
    st = OTEState(cfg)
    df = frame_from_path(synthetic_impulse_and_retest())
    from atm_engine.data.schema import iter_bars

    sigs = []
    for k, bar in enumerate(iter_bars(df)):
        sigs.extend(st.update(bar, rho=5.0, minutes_since_open=k))
    assert sigs == []  # 170 minutes cannot establish a 60-minute structure bias


def test_ote_zone_invalidated_by_close_through_origin():
    cfg = OTEConfig(leg_minutes=5, swing_width=2, min_displacement_sigma=1.0, require_bias=False, confirmation="range_break")
    st = OTEState(cfg)
    path = synthetic_impulse_and_retest()[:85]
    # after the top, crash straight through the origin
    for i in range(30):
        p = 139 - (i + 1) * 2.0
        path.append((p + 2, p + 2.2, p - 0.5, p))
    df = frame_from_path(path)
    from atm_engine.data.schema import iter_bars

    sigs = []
    for k, bar in enumerate(iter_bars(df)):
        sigs.extend(st.update(bar, rho=5.0, minutes_since_open=k))
    assert sigs == [] and st.legs[Direction.BUYING] is None


def test_run_ote_and_simulate_with_explicit_geometry():
    cfg = config_for("NQ")
    df = frame_from_path(synthetic_impulse_and_retest())
    sig = run_ote(df, cfg, OTEConfig(leg_minutes=5, swing_width=2, min_displacement_sigma=0.5, require_bias=False, breakout_min_sigma=0.05))
    assert len(sig) == 1 and sig.iloc[0]["rung"] == "OTE long" and sig.iloc[0]["trigger"] == "range_break"
    assert sig.iloc[0]["range_lo"] <= 112.0 and sig.iloc[0]["stop_price"] < sig.iloc[0]["range_lo"]
    tr = simulate(sig, df, "NQ", ExecutionSpec(horizon_bars=200))
    assert len(tr) == 1
    t = tr.iloc[0]
    assert t.side == "long" and t.reason == "target"
    assert abs(t.exit - (sig.iloc[0]["target_price"] - 0.25)) < 1e-9  # long target exit sells a tick lower
    assert t.r_multiple > 0


def test_simulate_explicit_stop_skips_when_already_through():
    cfg = config_for("NQ")
    df = frame_from_path(synthetic_impulse_and_retest())
    ev = pd.DataFrame([{"ts": df.index[100], "direction": "Buying", "level_price": 120.0, "stop_price": 200.0, "target_price": 150.0, "anchor": 120.0, "rho": 5.0, "is_entry": True, "score": 0.9, "session_date": "2024-01-03", "rung": "x"}])
    assert simulate(ev, df, "NQ").empty
