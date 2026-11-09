import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from atm_engine.config import DeviationConfig, LiquidityConfig, OrderFlowConfig, RegimeConfig, StructureConfig
from atm_engine.features.deviation import DeviationState
from atm_engine.features.liquidity import LiquidityState, VolumeProfile
from atm_engine.features.orderflow import OrderFlowState
from atm_engine.features.regime import RegimeState
from atm_engine.features.structure import StructureState
from atm_engine.types import Bar, Direction

TZ = ZoneInfo("America/New_York")


def mk(i, o, h, l, c, v=100.0, bv=None, sv=None):
    return Bar(datetime(2024, 1, 3, 9, 30, tzinfo=TZ) + timedelta(minutes=i), o, h, l, c, v, bv, sv)


def test_deviation_anchor_and_rho_match_closed_form():
    st = DeviationState(DeviationConfig(), tick_size=0.25)
    bars = [mk(0, 100, 101, 99, 100, 10), mk(1, 100, 104, 100, 103, 30), mk(2, 103, 103, 97, 98, 20)]
    for i, b in enumerate(bars):
        snap = st.update(b, in_rth=True, is_open_bar=(i == 0))
    p = np.array([b.typical for b in bars])
    v = np.array([b.volume for b in bars])
    vwap = (p * v).sum() / v.sum()
    var = (p * p * v).sum() / v.sum() - vwap**2
    assert math.isclose(snap.anchor, vwap, rel_tol=1e-12)
    assert snap.rho >= math.sqrt(var)  # floored by one-bar vol
    assert snap.k_inner == DeviationConfig().warmup_inner  # not yet warmed up
    assert math.isclose(snap.z, (98 - vwap) / snap.rho)


def test_deviation_resets_on_open_bar():
    st = DeviationState(DeviationConfig(), 0.25)
    st.update(mk(0, 100, 101, 99, 100, 10), True, True)
    st.update(mk(1, 100, 101, 99, 100, 10), True, False)
    snap = st.update(mk(2, 200, 201, 199, 200, 10), True, True)
    assert math.isclose(snap.anchor, 200.0)


def test_bvc_splits_volume_and_prefers_explicit_flow():
    st = OrderFlowState(OrderFlowConfig())
    s = st.update(mk(0, 100, 101, 99, 100, 100, 70, 30), is_open_bar=True)
    assert math.isclose(s.delta, 40.0) and math.isclose(s.buy_fraction, 0.7)
    st2 = OrderFlowState(OrderFlowConfig())
    st2.update(mk(0, 100, 101, 99, 100, 100), True)
    for i in range(1, 40):
        st2.update(mk(i, 100, 101, 99, 100 + (1 if i % 2 else -1), 100), False)
    s2 = st2.update(mk(40, 100, 105, 100, 105, 100), False)
    assert s2.buy_fraction > 0.9  # big up move classifies as buying
    assert 0 <= s2.buy_fraction <= 1


def test_divergence_rejection_component():
    st = OrderFlowState(OrderFlowConfig(divergence_window=3))
    for i in range(6):
        st.update(mk(i, 100, 101, 99, 100, 100, 50, 50), i == 0)
    bar = mk(6, 100, 110, 100, 100.5, 100, 50, 50)  # long upper wick
    d = st.divergence(bar, Direction.SELLING)
    assert 0.4 < d <= 1.0
    assert st.divergence(mk(7, 100, 100, 100, 100), Direction.SELLING) == 0.0  # zero-range bar


def test_volume_profile_poc_value_area_and_hvn():
    vp = VolumeProfile(bin_width=1.0)
    vp.add(mk(0, 100.5, 100.9, 100.1, 100.5, 100))  # all in bin 100
    vp.add(mk(1, 101.5, 101.9, 101.1, 101.5, 20))
    vp.add(mk(2, 102.5, 102.9, 102.1, 102.5, 5))
    s = vp.summary(value_area=0.7, hvn_quantile=1.0)
    assert math.isclose(s.poc, 100.5)
    assert s.val == 100.0 and s.vah == 101.0  # 100 of 125 already exceeds 70%
    assert s.total == 125
    assert s.hvns and math.isclose(s.hvns[0][0], 100.5)


def test_volume_profile_spreads_bar_volume_across_bins():
    vp = VolumeProfile(1.0)
    vp.add(mk(0, 101, 103.5, 100.5, 102, 40))  # bins 100..103 -> 4 bins
    assert all(math.isclose(v, 10.0) for v in vp.bins.values()) and len(vp.bins) == 4


def test_liquidity_relative_volume_uses_tod_profile():
    st = LiquidityState(LiquidityConfig(), 0.25)
    st.start_session(rho_hint=10.0)
    for i in range(5):
        st.update(mk(i, 100, 101, 99, 100, 100), delta=0.0, minute_of_session=i, in_rth=True)
    st.start_session(rho_hint=10.0)
    s = st.update(mk(390, 100, 101, 99, 100, 300), 0.0, 0, True)
    assert math.isclose(s.relative_volume, 3.0)
    assert st.prior is not None and math.isclose(st.prior.poc, 100.0, abs_tol=1.0)


def test_structure_swings_confirm_with_lag_and_rolls_prior_session():
    st = StructureState(StructureConfig(swing_width=2), opening_range_bars=3)
    highs = [100, 101, 105, 101, 100, 99, 98]
    for i, h in enumerate(highs):
        st.update(mk(i, h - 1, h, h - 2, h - 1), True, i == 0, tol=0.1)
    swings = [s for s in st.swings if s.is_high]
    assert len(swings) == 1 and swings[0].price == 105
    names = {p.detail for p in st.proposals()}
    assert {"or_high", "or_low", "sess_high", "sess_low", "swing_high"} <= names
    # next session: prior refs roll
    st.update(mk(400, 100, 101, 99, 100), True, True, 0.1)
    r = st.refs
    assert r.prior_high == 105 and r.prior_low == min(h - 2 for h in highs) and r.prior_close == 97


def test_regime_width_within_bounds_and_neutral_early():
    st = RegimeState(RegimeConfig())
    rng = np.random.default_rng(0)
    price = 100.0
    for i in range(500):
        price *= math.exp(rng.normal(0, 0.001))
        snap = st.update(mk(i, price, price * 1.001, price * 0.999, price), 0.0, 1.0)
        lo, hi = RegimeConfig().width_bounds
        assert lo <= snap.width_multiplier <= hi
        assert 0.0 < snap.confidence < 1.0
    assert 0.7 < snap.width_multiplier < 1.4  # i.i.d. noise is a neutral regime
