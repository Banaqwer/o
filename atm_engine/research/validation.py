"""Session-level inference and null baselines.

Events cluster within sessions and sessions cluster within weeks, so the
unit of inference is the session and the resampling unit is a block of
sessions. Event-level t-statistics are not used.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


def session_pnl(trades: pd.DataFrame, sessions: Optional[pd.Index] = None) -> pd.Series:
    """Net P&L per session; sessions without a trade count as zero when ``sessions`` is given."""

    if trades.empty:
        s = pd.Series(dtype=float)
    else:
        s = trades.groupby("session_date")["net"].sum()
    if sessions is not None:
        s = s.reindex(pd.Index(sessions).astype(str), fill_value=0.0)
    return s.sort_index()


def block_bootstrap_mean(x: np.ndarray, block: int = 5, n_boot: int = 2000, seed: int = 11) -> Tuple[float, float]:
    """95% interval for the mean under a moving-block bootstrap."""

    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return (float("nan"), float("nan"))
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    offs = np.arange(block)
    idx = (starts[:, :, None] + offs[None, None, :]).reshape(n_boot, -1)[:, :n]
    means = x[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def performance(trades: pd.DataFrame, sessions: pd.Index, block: int = 5, n_boot: int = 2000) -> Dict[str, float]:
    """Costed performance with session-level inference."""

    n_sess = len(sessions)
    out: Dict[str, float] = {"sessions": n_sess, "trades": int(len(trades))}
    if trades.empty or n_sess == 0:
        out.update({"trades_per_session": 0.0, "hit_rate": np.nan, "avg_net": np.nan, "total_net": 0.0, "session_mean": 0.0, "session_ci_lo": np.nan, "session_ci_hi": np.nan, "sharpe": np.nan, "max_dd": 0.0, "profit_factor": np.nan})
        return out
    sp = session_pnl(trades, sessions)
    x = sp.to_numpy()
    lo, hi = block_bootstrap_mean(x, block=block, n_boot=n_boot)
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    eq = np.cumsum(x)
    dd = eq - np.maximum.accumulate(eq)
    wins = trades.loc[trades["net"] > 0, "net"].sum()
    losses = -trades.loc[trades["net"] < 0, "net"].sum()
    out.update(
        {
            "trades_per_session": len(trades) / n_sess,
            "hit_rate": float((trades["net"] > 0).mean()),
            "avg_net": float(trades["net"].mean()),
            "median_net": float(trades["net"].median()),
            "avg_r": float(trades["r_multiple"].mean()) if "r_multiple" in trades else np.nan,
            "total_net": float(trades["net"].sum()),
            "session_mean": float(x.mean()),
            "session_ci_lo": lo,
            "session_ci_hi": hi,
            "sharpe": float(x.mean() / sd * np.sqrt(252)) if sd and sd > 0 else np.nan,
            "max_dd": float(dd.min()),
            "profit_factor": float(wins / losses) if losses > 0 else np.inf,
            "pct_sessions_positive": float((x > 0).mean()),
            "exit_stop": float((trades["reason"] == "stop").mean()),
            "exit_target": float((trades["reason"] == "target").mean()),
        }
    )
    # scale-free edge: points per unit of rho, gross and net of all friction, so periods at different
    # price levels can be compared (USD costs are fixed while rho in USD is not)
    if "points" in trades and "rho" in trades and float(trades["rho"].sum()) > 0:
        nz = trades[trades["points"] != 0]
        mult = float((nz["gross"] / nz["points"]).iloc[0]) if len(nz) else np.nan
        out["gross_per_rho"] = float(trades["points"].sum() / trades["rho"].sum())
        out["net_per_rho"] = float((trades["net"] / mult).sum() / trades["rho"].sum()) if mult and np.isfinite(mult) else np.nan
    return out


def matched_baseline_events(events: pd.DataFrame, ladders: pd.DataFrame, bars: pd.DataFrame, tol: float = 0.10, seed: int = 3, in_rth_only: bool = True) -> pd.DataFrame:
    """For each event, a random bar at the same |z| (within ``tol``), faded toward the anchor.

    Returns a frame shaped like the event frame as far as ``simulate`` needs:
    ts, direction, level_price (the bar close), anchor, rho, session_date, is_entry.
    """

    if events.empty or ladders.empty:
        return events.iloc[0:0]
    rng = np.random.default_rng(seed)
    lad = ladders.copy()
    close = bars["close"].reindex(lad.index)
    lad["z"] = (close - lad["anchor"]) / lad["rho"]
    lad = lad[np.isfinite(lad["z"]) & (np.abs(lad["z"]) > 0.25)]
    absz = np.abs(lad["z"].to_numpy())
    order = np.argsort(absz)
    absz_sorted = absz[order]
    rows = []
    for r in events.itertuples(index=False):
        z = abs(float(r.z))
        lo, hi = np.searchsorted(absz_sorted, z * (1 - tol)), np.searchsorted(absz_sorted, z * (1 + tol) + 0.02)
        if hi <= lo:
            continue
        j = order[rng.integers(lo, hi)]
        row = lad.iloc[j]
        ts = lad.index[j]
        rows.append(
            {
                "ts": ts,
                "direction": "Selling" if row["z"] > 0 else "Buying",
                "level_price": float(close.loc[ts]),
                "anchor": float(row["anchor"]),
                "rho": float(row["rho"]),
                "z": float(row["z"]),
                "session_date": str(row["session_date"]) if "session_date" in row else str(ts.date()),
                "is_entry": True,
                "score": np.nan,
                "rung": "baseline",
            }
        )
    return pd.DataFrame(rows)


def first_passage_labels(events: pd.DataFrame, bars: pd.DataFrame, k_fav: float = 1.0, k_adv: float = 1.0, horizon: int = 60, session_tz: str = "America/New_York") -> pd.Series:
    """1 if price moves k_fav*rho in the rung's direction before k_adv*rho against it, 0 if the reverse, NaN if neither."""

    from zoneinfo import ZoneInfo

    idx = bars.index
    pos = pd.Series(np.arange(len(idx)), index=idx)
    h = bars["high"].to_numpy(dtype=float)
    l = bars["low"].to_numpy(dtype=float)
    loc = idx.tz_convert(ZoneInfo(session_tz))
    last_rth = np.asarray((loc.hour == 15) & (loc.minute == 59))
    out = np.full(len(events), np.nan)
    ts_values = pd.to_datetime(events["ts"], utc=True)
    for k, (ts, r) in enumerate(zip(ts_values, events.itertuples(index=False))):
        if ts not in pos.index:
            continue
        i = int(pos[ts])
        side = 1 if r.direction == "Selling" else -1
        fav = float(r.level_price) - side * k_fav * float(r.rho)
        adv = float(r.level_price) + side * k_adv * float(r.rho)
        for n in range(1, horizon + 1):
            j = i + n
            if j >= len(h):
                break
            hit_adv = h[j] >= adv if side > 0 else l[j] <= adv
            hit_fav = l[j] <= fav if side > 0 else h[j] >= fav
            if hit_adv:
                out[k] = 0.0
                break
            if hit_fav:
                out[k] = 1.0
                break
            if last_rth[j]:
                break
    return pd.Series(out, index=events.index, name="label")
