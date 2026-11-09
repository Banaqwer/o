"""Plain execution overlay for turning printed events into costed trades.

Deliberately simple and fixed in advance (see docs/protocol.md): enter at
the next bar's open after the test bar, toward the anchor; stop a fixed
number of sigma beyond the level; target at the anchor in force at the
test; time stop; flat at the regular-session close; stop before target when
both print in one bar; one contract per event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ContractSpec:
    multiplier: float  # USD per point
    tick: float


CONTRACTS: Dict[str, ContractSpec] = {
    "NQ": ContractSpec(20.0, 0.25),
    "MNQ": ContractSpec(2.0, 0.25),
    "ES": ContractSpec(50.0, 0.25),
    "MES": ContractSpec(5.0, 0.25),
    "YM": ContractSpec(5.0, 1.0),
    "RTY": ContractSpec(50.0, 0.10),
    "GC": ContractSpec(100.0, 0.10),
    "SI": ContractSpec(5000.0, 0.005),
    "HG": ContractSpec(25000.0, 0.0005),
    "PL": ContractSpec(50.0, 0.10),
}


@dataclass(frozen=True)
class ExecutionSpec:
    stop_sigma: float = 2.0
    target: str = "anchor"  # "anchor" | "none"
    horizon_bars: int = 60
    entries_only: bool = True
    commission_per_side: float = 2.50
    slippage_ticks: float = 1.0
    flat_at_close: bool = True
    session_tz: str = "America/New_York"
    close_hour: int = 16


def _rth_last_bar_flags(index: pd.DatetimeIndex, tz: str, close_hour: int) -> np.ndarray:
    loc = index.tz_convert(ZoneInfo(tz))
    # last regular-session bar: the minute before the close
    return np.asarray((loc.hour == close_hour - 1) & (loc.minute == 59))


def simulate(events: pd.DataFrame, bars: pd.DataFrame, instrument: str, spec: ExecutionSpec = ExecutionSpec()) -> pd.DataFrame:
    """One trade per event. Returns a frame with one row per trade."""

    if instrument not in CONTRACTS:
        raise KeyError(f"no contract spec for {instrument}")
    c = CONTRACTS[instrument]
    ev = events
    if spec.entries_only and "is_entry" in ev.columns:
        ev = ev[ev["is_entry"].astype(bool)]
    if ev.empty:
        return _empty()

    idx = bars.index
    pos = pd.Series(np.arange(len(idx)), index=idx)
    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    l = bars["low"].to_numpy(dtype=float)
    cl = bars["close"].to_numpy(dtype=float)
    last_rth = _rth_last_bar_flags(idx, spec.session_tz, spec.close_hour)
    slip = spec.slippage_ticks * c.tick
    cost = 2.0 * spec.commission_per_side + 2.0 * slip * c.multiplier
    n = len(idx)

    rows: List[dict] = []
    ts_values = pd.to_datetime(ev["ts"], utc=True)
    for ts, r in zip(ts_values, ev.itertuples(index=False)):
        if ts not in pos.index:
            continue
        i = int(pos[ts])
        if i + 1 >= n:
            continue
        side = 1 if r.direction == "Selling" else -1  # +1 short, -1 long
        entry = o[i + 1] - side * slip  # short fills a tick lower, long a tick higher
        rho = float(r.rho)
        stop = float(r.level_price) + side * spec.stop_sigma * rho
        target: Optional[float] = None
        if spec.target == "anchor":
            a = float(r.anchor)
            if (side > 0 and a < entry) or (side < 0 and a > entry):
                target = a
        exit_px = None
        reason = "time"
        j = i + 1
        for k in range(spec.horizon_bars):
            j = i + 1 + k
            if j >= n:
                j = n - 1
                exit_px, reason = cl[j], "end"
                break
            hit_stop = h[j] >= stop if side > 0 else l[j] <= stop
            hit_tgt = target is not None and ((l[j] <= target) if side > 0 else (h[j] >= target))
            if hit_stop:
                exit_px, reason = stop + side * slip, "stop"
                break
            if hit_tgt:
                exit_px, reason = target + side * slip, "target"
                break
            if spec.flat_at_close and last_rth[j]:
                exit_px, reason = cl[j] + side * slip, "close"
                break
            if k == spec.horizon_bars - 1:
                exit_px, reason = cl[j] + side * slip, "time"
        if exit_px is None:
            continue
        points = (entry - exit_px) * side
        gross = points * c.multiplier
        rows.append(
            {
                "ts_entry": idx[i + 1],
                "ts_exit": idx[j],
                "session_date": getattr(r, "session_date", str(ts.date())),
                "rung": getattr(r, "rung", ""),
                "side": "short" if side > 0 else "long",
                "entry": entry,
                "exit": exit_px,
                "reason": reason,
                "bars_held": j - i,
                "points": points,
                "gross": gross,
                "costs": cost,
                "net": gross - cost,
                "rho": rho,
                "r_multiple": points / (spec.stop_sigma * rho) if rho > 0 else np.nan,
                "score": getattr(r, "score", np.nan),
            }
        )
    if not rows:
        return _empty()
    return pd.DataFrame(rows)


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["ts_entry", "ts_exit", "session_date", "rung", "side", "entry", "exit", "reason", "bars_held", "points", "gross", "costs", "net", "rho", "r_multiple", "score"])
