from datetime import date

import numpy as np
import pandas as pd
import pytest

from atm_engine.research.context import CONTEXT_COLUMNS, DailyContext, build_context_frame
from atm_engine.research.backtest import replay
from atm_engine.research.stats import summarize_by


def synthetic_daily(n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2023-01-02", periods=n)
    vix = pd.Series(np.exp(np.log(18) + np.cumsum(rng.normal(0, 0.03, n))), index=idx)
    px = pd.Series(15000 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=idx)
    fred = pd.DataFrame({"VIXCLS": vix, "T10Y2Y": rng.normal(-0.3, 0.1, n), "NASDAQ100": px})
    fred.index.name = "date"
    factors = pd.DataFrame({"Mkt-RF": rng.normal(0, 0.01, n), "RF": 0.0001}, index=idx)
    return fred, factors


def test_build_context_frame_columns_and_warmup():
    fred, factors = synthetic_daily()
    f = build_context_frame(fred, factors)
    assert list(f.columns) == list(CONTEXT_COLUMNS)
    assert np.isnan(f["vix_z"].iloc[10]) and np.isfinite(f["vix_z"].iloc[-1])
    assert 0.0 <= f["vix_pct_1y"].dropna().max() <= 1.0
    assert f["index_dd_63d"].dropna().max() <= 1e-12


def test_for_session_uses_strictly_prior_day():
    fred, factors = synthetic_daily()
    ctx = DailyContext(build_context_frame(fred, factors))
    d = ctx.frame.index[300].date()
    snap = ctx.for_session(d)
    assert snap is not None and snap.asof < d
    assert snap.asof == ctx.frame.index[299].date()
    assert snap.vix == pytest.approx(float(ctx.frame["vix"].iloc[299]))
    assert ctx.for_session(ctx.frame.index[0].date()) is None


def test_context_csv_roundtrip(tmp_path):
    fred, factors = synthetic_daily()
    ctx = DailyContext(build_context_frame(fred, factors))
    p = tmp_path / "ctx.csv"
    ctx.to_csv(str(p))
    back = DailyContext.from_csv(str(p))
    pd.testing.assert_frame_equal(back.frame, ctx.frame, check_freq=False)


def test_engine_uses_context_and_records_it(bars, cfg):
    fred, factors = synthetic_daily(n=600, seed=3)
    frame = build_context_frame(fred, factors)
    # force an extreme VIX regime on the bars' dates: ladder must widen
    frame.loc[:, "vix_z"] = 3.0
    hot = DailyContext(frame)
    frame_cold = frame.copy()
    frame_cold.loc[:, "vix_z"] = -3.0
    cold = DailyContext(frame_cold)

    res_hot = replay(bars, cfg, context=hot)
    res_cold = replay(bars, cfg, context=cold)
    assert res_hot.ladders["width_multiplier"].mean() > res_cold.ladders["width_multiplier"].mean()
    assert "ctx_vix_z" in res_hot.events.columns and (res_hot.events["ctx_vix_z"] == 3.0).all()
    assert (res_hot.events["r_exogenous_z"] == 3.0).all()
    by = summarize_by(pd.concat([res_hot.events, res_cold.events]), "ctx_vix_z", bins=2, n_boot=10)
    assert not by.empty and by["n"].sum() > 0


def test_join_events_attaches_columns(bars, cfg):
    fred, factors = synthetic_daily(n=600, seed=3)
    ctx = DailyContext(build_context_frame(fred, factors))
    res = replay(bars, cfg)
    joined = ctx.join_events(res.events)
    assert "ctx_vix" in joined.columns and "ctx_asof" in joined.columns
    assert len(joined) == len(res.events)
    for sd, asof in zip(joined["session_date"], joined["ctx_asof"]):
        assert asof is None or asof < sd
