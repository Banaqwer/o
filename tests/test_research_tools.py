import numpy as np
import pandas as pd
import pytest

from atm_engine.config import ReversalConfig
from atm_engine.research.execution import CONTRACTS, ExecutionSpec, simulate
from atm_engine.research.fit import FEATURES, fit_weights, ridge_logistic
from atm_engine.research.validation import block_bootstrap_mean, first_passage_labels, matched_baseline_events, performance, session_pnl


def make_bars(path, start="2026-01-05 14:30", tz="UTC"):
    idx = pd.date_range(start, periods=len(path), freq="1min", tz=tz)
    o = np.array([p[0] for p in path], float)
    h = np.array([p[1] for p in path], float)
    l = np.array([p[2] for p in path], float)
    c = np.array([p[3] for p in path], float)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 100.0}, index=idx)


def event(ts, direction, level, anchor, rho=2.0, is_entry=True):
    return pd.DataFrame([{"ts": pd.Timestamp(ts, tz="UTC"), "direction": direction, "level_price": level, "anchor": anchor, "rho": rho, "z": (level - anchor) / rho, "is_entry": is_entry, "score": 0.8, "session_date": "2026-01-05", "rung": "Ω I"}])


def test_simulate_short_hits_target_at_anchor_with_costs():
    # signal bar 0; entry at open of bar 1 = 104; anchor 100; stop at level 104 + 2*2 = 108
    bars = make_bars([(104, 104.5, 103.5, 104), (104, 105, 103, 103.5), (103.5, 104, 99.5, 100.5)])
    ev = event("2026-01-05 14:30", "Selling", 104.0, 100.0)
    tr = simulate(ev, bars, "NQ", ExecutionSpec(stop_sigma=2.0, horizon_bars=10))
    assert len(tr) == 1
    t = tr.iloc[0]
    assert t.reason == "target" and t.side == "short"
    # short fills a tick lower on entry and a tick higher on exit
    assert t.entry == pytest.approx(104.0 - 0.25) and t.exit == pytest.approx(100.0 + 0.25)
    assert t.points == pytest.approx(3.5)
    assert t.costs == pytest.approx(2 * 2.5 + 2 * 0.25 * 20)
    assert t.net == pytest.approx(3.5 * 20 - 15.0)


def test_simulate_stop_takes_precedence_in_same_bar_and_long_side():
    # long from alpha level 96, anchor 100, stop at 96 - 2*2 = 92; bar 1 hits both
    bars = make_bars([(96, 96.5, 95.5, 96), (96, 101, 91, 95), (95, 96, 94, 95)])
    ev = event("2026-01-05 14:30", "Buying", 96.0, 100.0)
    tr = simulate(ev, bars, "ES", ExecutionSpec(stop_sigma=2.0, horizon_bars=10))
    t = tr.iloc[0]
    assert t.reason == "stop" and t.side == "long"
    assert t.entry == pytest.approx(96.25) and t.exit == pytest.approx(92.0 - 0.25)
    assert t.points == pytest.approx(92.0 - 0.25 - 96.25)


def test_simulate_time_stop_and_flat_at_close():
    bars = make_bars([(100, 100.5, 99.5, 100)] * 6)
    ev = event("2026-01-05 14:30", "Selling", 102.0, 100.0)
    tr = simulate(ev, bars, "NQ", ExecutionSpec(stop_sigma=2.0, horizon_bars=3, target="none"))
    assert tr.iloc[0].reason == "time" and tr.iloc[0].bars_held == 3
    # a bar at 15:59 ET (20:59 UTC in winter) forces a flat
    bars2 = make_bars([(100, 100.5, 99.5, 100)] * 4, start="2026-01-05 20:57")
    ev2 = event("2026-01-05 20:57", "Selling", 102.0, 100.0)
    tr2 = simulate(ev2, bars2, "NQ", ExecutionSpec(stop_sigma=2.0, horizon_bars=10, target="none"))
    assert tr2.iloc[0].reason == "close"


def test_simulate_entries_only_filter_and_unknown_instrument():
    bars = make_bars([(100, 100.5, 99.5, 100)] * 3)
    ev = event("2026-01-05 14:30", "Selling", 102.0, 100.0, is_entry=False)
    assert simulate(ev, bars, "NQ").empty
    assert len(simulate(ev, bars, "NQ", ExecutionSpec(entries_only=False))) == 1
    with pytest.raises(KeyError):
        simulate(ev, bars, "ZZ")


def test_performance_and_block_bootstrap():
    rng = np.random.default_rng(0)
    x = rng.normal(10, 5, 300)
    lo, hi = block_bootstrap_mean(x, block=5, n_boot=500)
    assert lo < x.mean() < hi and hi - lo < 4
    trades = pd.DataFrame({"session_date": [f"2026-01-{d:02d}" for d in (5, 5, 6, 7)], "net": [100.0, -40.0, 60.0, -20.0], "reason": ["target", "stop", "target", "time"], "r_multiple": [1, -1, 1, -0.3]})
    sessions = pd.Index(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])
    sp = session_pnl(trades, sessions)
    assert list(sp) == [60.0, 60.0, -20.0, 0.0]
    perf = performance(trades, sessions, n_boot=200)
    assert perf["trades"] == 4 and perf["hit_rate"] == 0.5 and perf["total_net"] == 100.0
    assert perf["trades_per_session"] == 1.0 and perf["exit_stop"] == 0.25


def test_first_passage_labels():
    bars = make_bars([(104, 104.5, 103.5, 104), (104, 104.5, 103, 103.5), (103.5, 104, 101.5, 102)])
    ev = event("2026-01-05 14:30", "Selling", 104.0, 100.0)  # fav at 102, adv at 106
    lab = first_passage_labels(ev, bars, 1.0, 1.0, 10)
    assert lab.iloc[0] == 1.0
    bars2 = make_bars([(104, 104.5, 103.5, 104), (104, 106.5, 103, 106)])
    assert first_passage_labels(ev, bars2, 1.0, 1.0, 10).iloc[0] == 0.0
    bars3 = make_bars([(104, 104.5, 103.5, 104), (104, 104.5, 103.5, 104)])
    assert np.isnan(first_passage_labels(ev, bars3, 1.0, 1.0, 10).iloc[0])


def test_ridge_logistic_recovers_sign_and_fit_weights_maps_to_config():
    rng = np.random.default_rng(1)
    n = 3000
    X = rng.normal(size=(n, len(FEATURES)))
    true_w = np.array([0.0, 0.5, 1.5, -1.0, 0.3, 0.8])
    p = 1 / (1 + np.exp(-(X @ true_w - 0.2)))
    y = (rng.random(n) < p).astype(float)
    w, b = ridge_logistic(X, y, lam=1.0)
    assert np.corrcoef(w, true_w)[0, 1] > 0.95 and w[3] < 0 < w[2]
    ev = pd.DataFrame(X, columns=list(FEATURES))
    ev["session_date"] = [f"s{i // 30}" for i in range(n)]
    res = fit_weights(ev, pd.Series(y), lam_grid=(1.0, 10.0), folds=3)
    assert res.n == n and res.lam in (1.0, 10.0)
    cfg = res.to_config(ReversalConfig())
    assert cfg.s_divergence > 0 > cfg.s_climax
    assert abs(cfg.s_divergence - res.weights["c_divergence"]) < 1e-12


def test_matched_baseline_matches_distance_and_side():
    idx = pd.date_range("2026-01-05 14:30", periods=400, freq="1min", tz="UTC")
    rng = np.random.default_rng(2)
    anchor = 100.0
    close = anchor + rng.normal(0, 3, 400)
    bars = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1.0}, index=idx)
    lad = pd.DataFrame({"anchor": anchor, "rho": 2.0, "session_date": "2026-01-05"}, index=idx)
    ev = pd.DataFrame({"z": [2.0, -2.5, 1.5], "ts": idx[:3]})
    base = matched_baseline_events(ev, lad, bars, tol=0.1)
    assert len(base) == 3
    for z, (_, b) in zip(ev["z"], base.iterrows()):
        assert abs(abs(b["z"]) - abs(z)) <= 0.1 * abs(z) + 0.02 + 1e-9
        assert b["direction"] == ("Selling" if b["z"] > 0 else "Buying")
