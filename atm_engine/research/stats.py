"""Reaction statistics.

The engine's output is analytical, so the research question is not P&L but
*did price react at the level?* For each horizon ``h`` we report, in sigma
units of the dispersion at the time of the event:

* mean favourable excursion (MFE) and mean adverse excursion (MAE);
* the mean of MFE - MAE with a bootstrap confidence interval and t-stat;
* the share of events after which price returned to the anchor.

Breakdowns are given by rung, by entry flag and by regime-confidence
tercile. All of it is descriptive: the sample is one instrument's history
and the usual caveats about regime dependence apply.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

import numpy as np
import pandas as pd


def _block(df: pd.DataFrame, h: int, rng: np.random.Generator, n_boot: int) -> dict:
    mfe = df[f"mfe_sigma_{h}"].to_numpy(dtype=float)
    mae = df[f"mae_sigma_{h}"].to_numpy(dtype=float)
    ok = np.isfinite(mfe) & np.isfinite(mae)
    mfe, mae = mfe[ok], mae[ok]
    n = len(mfe)
    out = {"horizon": h, "n": n}
    if n == 0:
        return out
    edge = mfe - mae
    out["mfe_sigma"] = float(mfe.mean())
    out["mae_sigma"] = float(mae.mean())
    out["edge_sigma"] = float(edge.mean())
    sd = float(edge.std(ddof=1)) if n > 1 else float("nan")
    out["t_stat"] = float(edge.mean() / (sd / np.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    if n > 1 and n_boot > 0:
        idx = rng.integers(0, n, size=(n_boot, n))
        means = edge[idx].mean(axis=1)
        out["edge_ci_lo"], out["edge_ci_hi"] = (float(x) for x in np.quantile(means, [0.025, 0.975]))
    rev = df.loc[ok, f"reverted_{h}"].astype(bool).to_numpy()
    out["p_reverted"] = float(rev.mean())
    out["p_mfe_gt_mae"] = float((mfe > mae).mean())
    return out


def summarize(events: pd.DataFrame, horizons: Optional[Iterable[int]] = None, n_boot: int = 2000, seed: int = 7) -> pd.DataFrame:
    if events is None or events.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    if horizons is None:
        horizons = sorted(int(c.split("_")[-1]) for c in events.columns if c.startswith("mfe_sigma_"))
    rows: List[dict] = []
    groups = [("all", events)]
    groups += [(f"rung={r}", g) for r, g in events.groupby("rung", sort=False)]
    groups += [(f"entry={bool(e)}", g) for e, g in events.groupby("is_entry", sort=False)]
    if "r_confidence" in events.columns and events["r_confidence"].nunique() >= 3:
        terc = pd.qcut(events["r_confidence"], 3, labels=["low", "mid", "high"], duplicates="drop")
        groups += [(f"regime_conf={t}", g) for t, g in events.groupby(terc, observed=True, sort=False)]
    for name, g in groups:
        for h in horizons:
            if f"mfe_sigma_{h}" not in g.columns:
                continue
            row = {"group": name}
            row.update(_block(g, h, rng, n_boot))
            rows.append(row)
    return pd.DataFrame(rows)


def session_summary(events: pd.DataFrame) -> pd.DataFrame:
    """One line per session: events, entries, per-rung counts."""
    if events is None or events.empty:
        return pd.DataFrame()
    g = events.groupby("session_date")
    out = pd.DataFrame(
        {
            "events": g.size(),
            "entries": g["is_entry"].sum().astype(int),
            "selling": g.apply(lambda d: int((d["direction"] == "Selling").sum()), include_groups=False),
            "buying": g.apply(lambda d: int((d["direction"] == "Buying").sum()), include_groups=False),
        }
    )
    return out
