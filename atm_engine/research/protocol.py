"""The pre-registered research pipeline (docs/protocol.md).

Phases:

* ``dev``      replay the development years with the hand-set engine, fit
               the score weights on the reversion label, write diagnostics;
* ``val``      replay validation with the fitted weights for each entry
               quantile, run the 18-cell overlay grid, choose one cell;
* ``holdout``  run the chosen cell once on NQ hold-out, then unchanged on
               ES and GC, with baselines and cost sensitivity.

Every phase writes its tables to markdown and its decisions to JSON so the
results document is a transcript, not a selection.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, replace
from datetime import time as dtime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import EngineConfig, ReversalConfig, config_for
from ..data.schema import validate_frame
from .backtest import replay
from .context import DailyContext
from .execution import ExecutionSpec, simulate
from .fit import FEATURES, FitResult, fit_weights, logloss
from .validation import first_passage_labels, matched_baseline_events, performance


def entry_labels(ev: pd.DataFrame, bars: pd.DataFrame) -> pd.Series:
    """Reversion label measured from the executable entry: the next bar's open (amendment 1)."""
    pos = pd.Series(np.arange(len(bars)), index=bars.index)
    i = pos.reindex(pd.to_datetime(ev["ts"], utc=True)).to_numpy()
    ok = np.isfinite(i)
    nxt = np.full(len(ev), np.nan)
    ii = np.clip(i[ok].astype(int) + 1, 0, len(bars) - 1)
    nxt[ok] = bars["open"].to_numpy()[ii]
    e2 = ev.copy()
    e2["level_price"] = nxt
    e2 = e2[np.isfinite(nxt)]
    lab = first_passage_labels(e2, bars, **LABEL)
    return lab.reindex(ev.index)

WARMUP_MONTHS = 3
GRID_Q = (0.50, 0.60, 0.70)
GRID_STOP = (2.0, 3.0, 5.0)  # amended after development: levels behave as zones
GRID_H = (15, 60)
LABEL = dict(k_fav=1.0, k_adv=1.0, horizon=60)
FIT_MIN_GAIN = 0.005  # fitted weights must beat the intercept model's CV log-loss by this much
MORNING = (dtime(9, 30), dtime(12, 0))  # the single secondary hypothesis
PERIODS = {
    "dev": ("2018-01-01", "2022-01-01"),
    "val": ("2022-01-01", "2024-01-01"),
    "holdout": ("2024-01-01", "2025-11-01"),
    "seen": ("2025-11-01", "2026-11-09"),
}


# ----------------------------------------------------------------------- data
def load_hist(hist_dir: Path, inst: str, start: str, end: str) -> pd.DataFrame:
    y0, y1 = int(start[:4]), int(end[:4])
    parts = []
    for y in range(y0, y1 + 1):
        p = hist_dir / f"{inst}_{y}.csv"
        if p.exists():
            parts.append(pd.read_csv(p, parse_dates=["ts"], index_col="ts"))
    if not parts:
        raise FileNotFoundError(f"no history for {inst} {y0}-{y1} in {hist_dir}")
    df = pd.concat(parts)
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    df = df[(df.index >= pd.Timestamp(start, tz="UTC")) & (df.index < pd.Timestamp(end, tz="UTC"))]
    return validate_frame(df)


def warm_start(start: str) -> str:
    return (pd.Timestamp(start) - pd.DateOffset(months=WARMUP_MONTHS)).strftime("%Y-%m-%d")


def run_replay(hist_dir: Path, inst: str, start: str, end: str, cfg: EngineConfig, ctx: Optional[DailyContext]):
    bars = load_hist(hist_dir, inst, warm_start(start), end)
    t = time.time()
    res = replay(bars, cfg, context=ctx)
    ev = res.events
    lad = res.ladders
    cut = pd.Timestamp(start, tz="UTC")
    ev = ev[ev["ts"] >= cut].reset_index(drop=True)
    lad = lad[lad.index >= cut]
    sessions = pd.Index(sorted(lad["session_date"].astype(str).unique()))
    return bars, ev, lad, sessions, time.time() - t


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("nan" if not np.isfinite(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def perf_row(name: str, perf: Dict[str, float]) -> Dict[str, object]:
    keys = ["sessions", "trades", "trades_per_session", "hit_rate", "avg_net", "session_mean", "session_ci_lo", "session_ci_hi", "sharpe", "max_dd", "profit_factor", "pct_sessions_positive", "exit_stop", "exit_target"]
    row: Dict[str, object] = {"name": name}
    row.update({k: perf.get(k, np.nan) for k in keys})
    return row


def cost_variants(spec: ExecutionSpec) -> Dict[str, ExecutionSpec]:
    return {
        "stated costs": spec,
        "zero costs": replace(spec, commission_per_side=0.0, slippage_ticks=0.0),
        "double costs": replace(spec, commission_per_side=2 * spec.commission_per_side, slippage_ticks=2 * spec.slippage_ticks),
    }


# ---------------------------------------------------------------------- phases
def phase_dev(hist: Path, out: Path, ctx: Optional[DailyContext]) -> None:
    start, end = PERIODS["dev"]
    cfg = config_for("NQ")
    bars, ev, lad, sessions, secs = run_replay(hist, "NQ", start, end, cfg, ctx)
    ev.to_csv(out / "dev_events.csv", index=False)
    labels_level = first_passage_labels(ev, bars, **LABEL)
    labels = entry_labels(ev, bars)
    fit = fit_weights(ev, labels)
    # intercept-only reference under the same grouped folds is approximated by the entropy of the base rate
    p0 = fit.base_rate
    null_ll = float(-(p0 * np.log(p0) + (1 - p0) * np.log(1 - p0)))
    gain = null_ll - fit.cv_logloss[fit.lam]
    use_fitted = gain >= FIT_MIN_GAIN
    (out / "fitted_reversal.json").write_text(json.dumps({"use_fitted": bool(use_fitted), "cv_gain_over_null": gain, "weights": fit.weights, "bias": fit.bias, "lam": fit.lam, "cv_logloss": {str(k): v for k, v in fit.cv_logloss.items()}, "null_logloss": null_ll, "n": fit.n, "base_rate": fit.base_rate}, indent=2))

    lines = [f"# Development phase: NQ {start} to {end}", "", f"{len(bars)} bars incl. warm-up, {len(sessions)} sessions, {len(ev)} level tests, replay {secs:.0f}s.", ""]
    lines += ["## Reversion label", "", f"Amended label: 1 rho favourable before 1 rho adverse within 60 bars, measured from the next bar's open. Labelled events: {fit.n} ({labels.notna().mean():.1%} of tests). Base rate = {fit.base_rate:.3f}. (Original from-level label base rate {labels_level.mean():.3f}, shown alongside for the record.)", ""]
    comp_rows = []
    for f in FEATURES:
        q = pd.qcut(ev[f], 3, labels=["low", "mid", "high"], duplicates="drop")
        for lab, g in ev.groupby(q, observed=True):
            lg, ll = labels[g.index], labels_level[g.index]
            comp_rows.append({"component": f, "tercile": lab, "n": len(g), "p_fav_from_entry": float(lg.mean()) if lg.notna().any() else np.nan, "p_fav_from_level": float(ll.mean()) if ll.notna().any() else np.nan, "reverted60": float(g["reverted_60"].mean())})
    lines += ["## Components by tercile (development data)", "", md_table(pd.DataFrame(comp_rows)), ""]
    lines += ["## Fitted weights on the amended label (L2 logistic, grouped 5-fold CV)", "", f"lambda = {fit.lam}; CV log-loss by lambda: " + ", ".join(f"{k}: {v:.4f}" for k, v in fit.cv_logloss.items()) + f"; intercept-only log-loss {null_ll:.4f}; gain {gain:.4f}; rule needs {FIT_MIN_GAIN}.", "", md_table(pd.DataFrame([{"feature": k, "weight": v} for k, v in fit.weights.items()] + [{"feature": "bias", "weight": fit.bias}]), "{:.4f}"), ""]
    hand = ReversalConfig()
    lines += [f"**Decision: {'fitted weights' if use_fitted else 'hand-set weights kept'}.** Hand-set weights: " + ", ".join(f"{k}={getattr(hand, 's_' + k.split('_', 1)[1]):.2f}" for k in FEATURES) + f", bias={hand.bias:.2f}.", ""]

    # in-sample calibration of the fitted score (flagged as in-sample)
    X = ev[list(FEATURES)].to_numpy(dtype=float)
    logit = X @ np.array([fit.weights[f] for f in FEATURES]) + fit.bias
    ev["fitted_score"] = 1 / (1 + np.exp(-logit))
    dec = pd.qcut(ev["fitted_score"], 10, labels=False, duplicates="drop") + 1
    cal = ev.groupby(dec).apply(lambda d: pd.Series({"n": len(d), "p_fav_first": float(labels[d.index].mean()), "edge15_sigma": float((d["mfe_sigma_15"] - d["mae_sigma_15"]).mean()), "reverted60": float(d["reverted_60"].mean())}), include_groups=False).reset_index().rename(columns={"fitted_score": "decile"})
    lines += ["## Calibration of the fitted score by decile (IN-SAMPLE on development data)", "", md_table(cal), ""]

    # overlay on development data across the amended grid, hand-set entries, stated costs
    rows = []
    for stop in GRID_STOP:
        for H in GRID_H:
            spec = ExecutionSpec(stop_sigma=stop, horizon_bars=H)
            rows.append(perf_row(f"entries stop {stop} H {H}", performance(simulate(ev, bars, "NQ", spec), sessions)))
            rows.append(perf_row(f"entries stop {stop} H {H} 09:30-12:00", performance(simulate(ev, bars, "NQ", replace(spec, entry_window=MORNING)), sessions)))
    spec = ExecutionSpec(stop_sigma=3.0, horizon_bars=60)
    rows.append(perf_row("all tests stop 3 H 60", performance(simulate(ev, bars, "NQ", replace(spec, entries_only=False)), sessions)))
    base = matched_baseline_events(ev[ev["is_entry"]], lad, bars)
    rows.append(perf_row("matched baseline (entries) stop 3 H 60", performance(simulate(base, bars, "NQ", spec), sessions)))
    lines += ["## Overlay on development data (hand-set entries, target anchor, stated costs, USD per contract)", "", md_table(pd.DataFrame(rows), "{:.2f}"), ""]
    (out / "dev.md").write_text("\n".join(lines))
    print("\n".join(lines))


def load_fit(out: Path) -> Tuple[FitResult, bool]:
    d = json.loads((out / "fitted_reversal.json").read_text())
    fit = FitResult(d["weights"], d["bias"], d["lam"], {float(k): v for k, v in d["cv_logloss"].items()}, d["n"], d["base_rate"])
    return fit, bool(d.get("use_fitted", False))


def fitted_config(inst: str, fit: FitResult, q: float, use_fitted: bool) -> EngineConfig:
    base = fit.to_config(ReversalConfig()) if use_fitted else ReversalConfig()
    return config_for(inst, reversal=replace(base, entry_quantile=q))


def phase_val(hist: Path, out: Path, ctx: Optional[DailyContext]) -> None:
    start, end = PERIODS["val"]
    fit, use_fitted = load_fit(out)
    lines = [f"# Validation phase: NQ {start} to {end}", "", f"Weights: {'fitted on development' if use_fitted else 'hand-set (development decision rule)'}; amended 18-cell grid, all cells reported.", ""]
    cells: List[Dict[str, object]] = []
    cache = {}
    for q in GRID_Q:
        bars, ev, lad, sessions, secs = run_replay(hist, "NQ", start, end, fitted_config("NQ", fit, q, use_fitted), ctx)
        cache[q] = (bars, ev, lad, sessions)
        ev.to_csv(out / f"val_events_q{int(q * 100)}.csv", index=False)
        for stop in GRID_STOP:
            for H in GRID_H:
                spec = ExecutionSpec(stop_sigma=stop, horizon_bars=H)
                p = performance(simulate(ev, bars, "NQ", spec), sessions)
                row = {"q": q, "stop": stop, "H": H}
                row.update(perf_row("", p))
                row.pop("name")
                cells.append(row)
        lines.append(f"q={q}: {len(ev)} tests, {int(ev['is_entry'].sum())} entries, {len(sessions)} sessions, replay {secs:.0f}s.")
    grid = pd.DataFrame(cells)
    lines += ["", "## Grid (stated costs, USD per contract, session-level inference)", "", md_table(grid, "{:.2f}"), ""]
    ok = grid[grid["trades_per_session"] >= 0.5].copy()
    ok = ok.sort_values(["sharpe", "stop", "H"], ascending=[False, False, False])
    chosen = ok.iloc[0] if not ok.empty else grid.sort_values("sharpe", ascending=False).iloc[0]
    choice = {"q": float(chosen["q"]), "stop": float(chosen["stop"]), "H": int(chosen["H"])}
    (out / "chosen_cell.json").write_text(json.dumps(choice, indent=2))
    lines += [f"## Chosen cell (pre-specified criterion): q={choice['q']}, stop={choice['stop']} rho, H={choice['H']}", ""]
    bars, ev, lad, sessions = cache[choice["q"]]
    spec = ExecutionSpec(stop_sigma=choice["stop"], horizon_bars=choice["H"])
    rows = [perf_row(name, performance(simulate(ev, bars, "NQ", s), sessions)) for name, s in cost_variants(spec).items()]
    base = matched_baseline_events(ev[ev["is_entry"]], lad, bars)
    rows.append(perf_row("matched baseline, stated costs", performance(simulate(base, bars, "NQ", spec), sessions)))
    rows.append(perf_row("secondary: 09:30-12:00 ET signals only, stated costs", performance(simulate(ev, bars, "NQ", replace(spec, entry_window=MORNING)), sessions)))
    lines += ["## Chosen cell: cost sensitivity, baseline and the secondary hypothesis", "", md_table(pd.DataFrame(rows), "{:.2f}"), ""]
    # how many of 18 cells positive
    lines += [f"Cells with positive session mean: {(grid['session_mean'] > 0).sum()} of {len(grid)}; with CI above zero: {(grid['session_ci_lo'] > 0).sum()} of {len(grid)}.", ""]
    (out / "val.md").write_text("\n".join(lines))
    print("\n".join(lines))


def phase_holdout(hist: Path, out: Path, ctx: Optional[DailyContext], instruments: Tuple[str, ...] = ("NQ", "ES", "GC")) -> None:
    fit, use_fitted = load_fit(out)
    choice = json.loads((out / "chosen_cell.json").read_text())
    spec = ExecutionSpec(stop_sigma=choice["stop"], horizon_bars=choice["H"])
    lines = ["# Hold-out phase", "", f"Configuration frozen from development and validation: {'fitted' if use_fitted else 'hand-set'} weights, q={choice['q']}, stop={choice['stop']} rho, target anchor, H={choice['H']}. Run once per instrument.", ""]
    summary = []
    for inst in instruments:
        for period in ("holdout", "seen"):
            start, end = PERIODS[period]
            try:
                bars, ev, lad, sessions, secs = run_replay(hist, inst, start, end, fitted_config(inst, fit, choice["q"], use_fitted), ctx)
            except FileNotFoundError as e:
                lines.append(f"{inst} {period}: {e}")
                continue
            ev.to_csv(out / f"{period}_{inst}_events.csv", index=False)
            tag = f"{inst} {period} {start}..{end}" + (" (SEEN before protocol; not evidence)" if period == "seen" else "")
            rows = [perf_row(name, performance(simulate(ev, bars, inst, s), sessions)) for name, s in cost_variants(spec).items()]
            base = matched_baseline_events(ev[ev["is_entry"]], lad, bars)
            rows.append(perf_row("matched baseline, stated costs", performance(simulate(base, bars, inst, spec), sessions)))
            rows.append(perf_row("all tests, stated costs", performance(simulate(ev, bars, inst, replace(spec, entries_only=False)), sessions)))
            rows.append(perf_row("secondary: 09:30-12:00 ET signals only, stated costs", performance(simulate(ev, bars, inst, replace(spec, entry_window=MORNING)), sessions)))
            lines += [f"## {tag}", "", f"{len(ev)} tests, {int(ev['is_entry'].sum())} entries, {len(sessions)} sessions.", "", md_table(pd.DataFrame(rows), "{:.2f}"), ""]
            tr = simulate(ev, bars, inst, spec)
            if not tr.empty:
                tr["year"] = pd.to_datetime(tr["session_date"]).dt.year
                by_year = tr.groupby("year").apply(lambda d: pd.Series(performance(d, pd.Index(sorted(set(d["session_date"]))))), include_groups=False)[["sessions", "trades", "hit_rate", "avg_net", "session_mean", "sharpe", "max_dd"]].reset_index()
                lines += ["By year (sessions with trades only):", "", md_table(by_year, "{:.2f}"), ""]
                if "ctx_vix_z" in ev.columns:
                    evt = ev[ev["is_entry"]]
                    trv = tr.merge(evt[["ts", "ctx_vix_z"]].rename(columns={"ts": "ts_sig"}), left_on=tr["ts_entry"] - pd.Timedelta(minutes=1), right_on="ts_sig", how="left")
                    if trv["ctx_vix_z"].notna().sum() > 30:
                        terc = pd.qcut(trv["ctx_vix_z"], 3, labels=["low VIX", "mid VIX", "high VIX"], duplicates="drop")
                        by_vix = trv.groupby(terc, observed=True).apply(lambda d: pd.Series({"trades": len(d), "hit_rate": (d["net"] > 0).mean(), "avg_net": d["net"].mean(), "total_net": d["net"].sum()}), include_groups=False).reset_index()
                        lines += ["By previous-close VIX tercile:", "", md_table(by_vix, "{:.2f}"), ""]
            p = performance(tr, sessions)
            summary.append({"instrument": inst, "period": period, "sessions": len(sessions), "trades": p["trades"], "session_mean_usd": p["session_mean"], "ci_lo": p["session_ci_lo"], "ci_hi": p["session_ci_hi"], "sharpe": p["sharpe"], "hit_rate": p["hit_rate"], "avg_net": p["avg_net"]})
    lines += ["## Summary", "", md_table(pd.DataFrame(summary), "{:.2f}"), ""]
    (out / "holdout.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atm-engine protocol")
    p.add_argument("phase", choices=["dev", "val", "holdout"])
    p.add_argument("--hist", required=True, help="directory of <INST>_<YEAR>.csv files")
    p.add_argument("--out", required=True)
    p.add_argument("--context", default=None)
    p.add_argument("--instruments", default="NQ,ES,GC")
    a = p.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ctx = DailyContext.from_csv(a.context) if a.context else None
    hist = Path(a.hist)
    if a.phase == "dev":
        phase_dev(hist, out, ctx)
    elif a.phase == "val":
        phase_val(hist, out, ctx)
    else:
        phase_holdout(hist, out, ctx, tuple(a.instruments.split(",")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
