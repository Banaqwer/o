import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from atm_engine.config import EngineConfig, LadderConfig, ReactionConfig, config_for
from atm_engine.engine.ladder import LadderBuilder
from atm_engine.engine.reaction import ReactionTracker
from atm_engine.engine.reversal import ReversalEngine, RungState
from atm_engine.engine.session_log import MemoryLog, SessionLog
from atm_engine.features.deviation import DeviationSnapshot
from atm_engine.research.backtest import replay
from atm_engine.research.stats import session_summary, summarize
from atm_engine.types import RUNG_ORDER, Bar, Direction, Event, Proposal, RegimeSnapshot, Rung

TZ = ZoneInfo("America/New_York")


def neutral_regime(width=1.0):
    return RegimeSnapshot(1.0, 0.5, 0.0, 1.0, width, 0.5)


def dev(anchor=100.0, rho=2.0, z=0.0, k_in=1.0, k_out=2.0):
    return DeviationSnapshot(anchor, rho, z, k_in, k_out, 0.5, True)


def mk(i, o, h, l, c, v=100.0):
    return Bar(datetime(2024, 1, 3, 9, 30, tzinfo=TZ) + timedelta(minutes=i), o, h, l, c, v)


# ---------------------------------------------------------------- ladder


def test_ladder_bands_bracket_price_and_are_ordered():
    b = LadderBuilder(LadderConfig(), 0.25, "NQ")
    lad = b.build(mk(0, 100, 100, 100, 100).ts, 100.0, dev(), neutral_regime(), [], {})
    o2, o1, a1, a2 = (lad.levels[r].price for r in RUNG_ORDER)
    assert (o2, o1, a1, a2) == (104.0, 102.0, 98.0, 96.0)
    assert lad[Rung.OMEGA_I].direction is Direction.SELLING and lad[Rung.ALPHA_II].direction is Direction.BUYING


def test_ladder_steps_out_when_price_is_beyond_inner_band():
    b = LadderBuilder(LadderConfig(), 0.25, "NQ")
    lad = b.build(mk(0, 1, 1, 1, 1).ts, 102.5, dev(z=1.25), neutral_regime(), [], {})
    assert lad[Rung.OMEGA_I].price == 104.0 and lad[Rung.OMEGA_II].price == 106.0
    assert lad[Rung.ALPHA_I].price == 98.0


def test_ladder_width_multiplier_scales_bands():
    b = LadderBuilder(LadderConfig(), 0.25, "NQ")
    lad = b.build(mk(0, 1, 1, 1, 1).ts, 100.0, dev(), neutral_regime(width=1.5), [], {})
    assert lad[Rung.OMEGA_I].price == 103.0 and lad[Rung.ALPHA_II].price == 94.0


def test_ladder_snaps_to_confluent_proposal_and_records_source():
    b = LadderBuilder(LadderConfig(), 0.25, "NQ")
    props = [Proposal(102.4, 1.0, "structure", "prior_high"), Proposal(150.0, 1.0, "structure", "far_away")]
    lad = b.build(mk(0, 1, 1, 1, 1).ts, 100.0, dev(), neutral_regime(), props, {"structure": 1.0})
    o1 = lad[Rung.OMEGA_I]
    assert 102.0 < o1.price <= 102.5
    assert o1.confluence > 0 and "prior_high" in o1.sources
    assert lad[Rung.OMEGA_II].sources == ()


def test_ladder_hysteresis_holds_then_drifts():
    b = LadderBuilder(LadderConfig(hysteresis_sigma=0.2), 0.25, "NQ")
    ts = mk(0, 1, 1, 1, 1).ts
    first = b.build(ts, 100.0, dev(), neutral_regime(), [], {})
    # anchor moves by 0.1 sigma: within hysteresis, levels held
    held = b.build(ts, 100.2, dev(anchor=100.2), neutral_regime(), [], {}, prev=first)
    assert held[Rung.OMEGA_I].price == first[Rung.OMEGA_I].price
    # anchor moves by 1 sigma while price stays below the rung: the rung drifts with its band
    moved = b.build(ts, 101.0, dev(anchor=102.0), neutral_regime(), [], {}, prev=first)
    assert moved[Rung.OMEGA_I].price == 104.0
    assert moved[Rung.OMEGA_II].price == 106.0


def test_ladder_held_rung_can_be_traded_through_until_breached():
    b = LadderBuilder(LadderConfig(), 0.25, "NQ")
    ts = mk(0, 1, 1, 1, 1).ts
    first = b.build(ts, 100.0, dev(), neutral_regime(), [], {})
    # price closes a hair above Omega I without a break: level stays, still testable
    through = b.build(ts, 102.2, dev(z=1.1), neutral_regime(), [], {}, prev=first)
    assert through[Rung.OMEGA_I].price == 102.0
    # the engine reports a break: the rung is re-placed beyond price
    broken = b.build(ts, 102.8, dev(z=1.4), neutral_regime(), [], {}, prev=first, breached={Rung.OMEGA_I})
    assert broken[Rung.OMEGA_I].price == 104.0
    assert broken[Rung.OMEGA_II].price >= broken[Rung.OMEGA_I].price + LadderConfig().min_rung_gap_sigma * 2.0
    broken.validate()


def test_ladder_levels_on_tick():
    b = LadderBuilder(LadderConfig(), 0.25, "GC")
    lad = b.build(mk(0, 1, 1, 1, 1).ts, 2000.13, dev(anchor=2000.13, rho=3.17, k_in=1.37, k_out=2.41), neutral_regime(1.13), [], {})
    for lv in lad.levels.values():
        assert math.isclose(lv.price / 0.25, round(lv.price / 0.25), abs_tol=1e-9)


# -------------------------------------------------------------- reactions


def make_event(ts, rung, level, anchor, rho=2.0):
    return Event(ts, "NQ", rung, rung.direction, level, level, level, anchor, rho, 0.0, 0.5, True, {}, neutral_regime(), {}, "2024-01-03")


def test_reaction_tracker_measures_excursions_per_horizon():
    tr = ReactionTracker(ReactionConfig(horizons=(2, 4)))
    ev = make_event(mk(0, 1, 1, 1, 1).ts, Rung.OMEGA_I, level=102.0, anchor=100.0)
    tr.add(ev, bar_index=0)
    path = [(101, 103, 100.5, 101), (101, 101.5, 99.5, 100), (100, 100.5, 98, 99), (99, 104, 98.5, 103)]
    for i, (o, h, l, c) in enumerate(path, start=1):
        tr.on_bar(mk(i, o, h, l, c), i)
    assert tr.pending == 0 and ev.reaction is not None
    r = ev.reaction
    assert r.favourable[2] == 102.0 - 99.5 and r.adverse[2] == 103.0 - 102.0 and r.reverted_to_anchor[2] is True
    assert r.favourable[4] == 102.0 - 98.0 and r.adverse[4] == 104.0 - 102.0
    rec = r.to_record()
    assert math.isclose(rec["mfe_sigma_2"], 2.5 / 2.0)


def test_reaction_tracker_close_session_leaves_unreached_horizons_nan():
    tr = ReactionTracker(ReactionConfig(horizons=(2, 10)))
    ev = make_event(mk(0, 1, 1, 1, 1).ts, Rung.ALPHA_I, level=98.0, anchor=100.0)
    tr.add(ev, 0)
    tr.on_bar(mk(1, 98, 99, 97, 98.5), 1)
    tr.on_bar(mk(2, 98.5, 100.5, 98, 100), 2)
    tr.close_session()
    assert ev.reaction.favourable[2] == 2.5 and math.isnan(ev.reaction.favourable[10])
    assert ev.reaction.reverted_to_anchor[2] is True


# ----------------------------------------------------------------- engine


def test_engine_detects_test_and_break_on_handcrafted_bars():
    cfg = config_for("NQ")
    eng = ReversalEngine(cfg)
    # flat session so rho is tiny and the ladder sits close to price
    for i in range(30):
        eng.on_bar(mk(i, 100.0, 100.5, 99.5, 100.0, 100))
    lad = eng.ladder
    assert lad is not None
    o1 = lad[Rung.OMEGA_I].price
    res = eng.on_bar(mk(30, 100.0, o1 + 0.01, 100.0, 100.0, 300))  # wick into Omega I
    assert len(res.events) >= 1
    ev = [e for e in res.events if e.rung is Rung.OMEGA_I][0]
    assert ev.direction is Direction.SELLING and ev.level_price == o1 and ev.test_price == o1 + 0.01
    assert eng._session.rung_state[Rung.OMEGA_I] is RungState.TESTED
    # no second event while still at the level (not re-armed)
    res2 = eng.on_bar(mk(31, 100.0, o1, 100.0, 100.0, 100))
    assert not [e for e in res2.events if e.rung is Rung.OMEGA_I]
    # break: close far through the level; ladder re-places Omega I above price
    big = o1 + 5 * res2.rho
    res3 = eng.on_bar(mk(32, 100.0, big + 0.5, 100.0, big, 500))
    assert eng.ladder[Rung.OMEGA_I].price > big
    assert eng._session.broken_upper >= 1


def test_engine_no_lookahead(bars, cfg):
    """The ladder and events through bar t must not depend on bars after t."""
    full = replay(bars, cfg)
    cut = len(bars) // 2
    half = replay(bars.iloc[:cut], cfg)
    a = full.ladders.iloc[:cut][["omega_ii", "omega_i", "alpha_i", "alpha_ii", "anchor", "rho"]]
    b = half.ladders[["omega_ii", "omega_i", "alpha_i", "alpha_ii", "anchor", "rho"]]
    pd.testing.assert_frame_equal(a, b)
    t_cut = bars.index[cut - 1]
    ev_full = full.events[full.events["ts"] <= t_cut][["ts", "rung", "level_price", "score"]].reset_index(drop=True)
    ev_half = half.events[half.events["ts"] <= t_cut][["ts", "rung", "level_price", "score"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(ev_full, ev_half)


def test_replay_outputs_schema_and_invariants(bars, cfg):
    res = replay(bars, cfg)
    assert res.n_bars == len(bars)
    lad = res.ladders
    assert (lad["omega_ii"] > lad["omega_i"]).all() and (lad["omega_i"] > lad["alpha_i"]).all() and (lad["alpha_i"] > lad["alpha_ii"]).all()
    ev = res.events
    assert not ev.empty
    assert set(ev["direction"].unique()) <= {"Selling", "Buying"}
    sel = ev[ev["direction"] == "Selling"]
    assert set(sel["rung"].unique()) <= {"Ω I", "Ω II"}
    # a Selling test prints at or above the level less the tolerance; Buying at or below
    assert (sel["test_price"] >= sel["level_price"] - cfg.reversal.touch_tolerance_sigma * sel["rho"] - 1e-9).all()
    buy = ev[ev["direction"] == "Buying"]
    assert (buy["test_price"] <= buy["level_price"] + cfg.reversal.touch_tolerance_sigma * buy["rho"] + 1e-9).all()
    assert ev["score"].between(0, 1).all()
    for h in cfg.reaction.horizons:
        assert f"mfe_sigma_{h}" in ev.columns and f"reverted_{h}" in ev.columns
    # the same instant can carry at most one event per rung
    assert not ev.duplicated(["ts", "rung"]).any()


def test_replay_is_deterministic(bars, cfg):
    a = replay(bars, cfg)
    b = replay(bars, cfg)
    pd.testing.assert_frame_equal(a.events, b.events)
    pd.testing.assert_frame_equal(a.ladders, b.ladders)


def test_engine_publishes_no_ladder_outside_rth(cfg):
    eng = ReversalEngine(cfg)
    pre = Bar(datetime(2024, 1, 3, 8, 0, tzinfo=TZ), 100, 101, 99, 100, 10)
    res = eng.on_bar(pre)
    assert res.ladder is None and not res.stamp.in_rth


def test_session_log_roundtrip(tmp_path, bars, cfg):
    log = SessionLog(tmp_path)
    res = replay(bars, cfg, log=log)
    sessions = log.sessions("NQ")
    assert len(sessions) == bars.index.tz_convert(TZ).normalize().nunique()
    ev = log.load_events("NQ")
    assert len(ev) == len(res.events)
    lad = log.load_ladders("NQ", sessions[0])
    assert {"omega_ii", "omega_i", "alpha_i", "alpha_ii"} <= set(lad.columns)


def test_stats_summary_shapes(bars, cfg):
    res = replay(bars, cfg)
    s = summarize(res.events, n_boot=50)
    assert {"group", "horizon", "n", "edge_sigma", "p_reverted"} <= set(s.columns)
    assert (s[s["group"] == "all"]["n"] <= len(res.events)).all()
    ss = session_summary(res.events)
    assert ss["events"].sum() == len(res.events)


def test_pure_mean_reversion_shows_positive_reaction(cfg):
    """Sanity: when the data truly mean-reverts, levels must show favourable reaction."""
    from atm_engine.data.synthetic import SyntheticSpec, generate

    df = generate(SyntheticSpec(sessions=12, p_trend_day=0.0, seed=7), cfg.session)
    res = replay(df, cfg)
    s = summarize(res.events, n_boot=0)
    row = s[(s["group"] == "all") & (s["horizon"] == 60)].iloc[0]
    assert row["edge_sigma"] > 0 and row["t_stat"] > 2.0


def test_config_rejects_bad_values():
    with pytest.raises(ValueError):
        EngineConfig(tick_size=0)
    with pytest.raises(KeyError):
        config_for("XYZ")
