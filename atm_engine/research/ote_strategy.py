"""Run the OTE detector over bars and emit signal frames the overlay can trade."""

from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

import pandas as pd

from ..config import EngineConfig
from ..data.schema import iter_bars, validate_frame
from ..data.sessions import SessionClock, minutes_since_open
from ..features.deviation import DeviationState
from ..features.ote import OTEConfig, OTEState


def run_ote(df: pd.DataFrame, cfg: EngineConfig, ote_cfg: OTEConfig = OTEConfig(), rth_only: bool = True) -> pd.DataFrame:
    """Signals as a frame with the columns ``simulate`` needs plus OTE diagnostics."""

    frame = validate_frame(df)
    clock = SessionClock(cfg.session)
    dev = DeviationState(cfg.deviation, cfg.tick_size)
    ote = OTEState(ote_cfg)
    rows: List[dict] = []
    for bar in iter_bars(frame):
        stamp = clock.stamp(bar.ts)
        snap = dev.update(bar, stamp.in_rth, stamp.is_open_bar)
        mso = minutes_since_open(bar.ts, cfg.session)
        signals = ote.update(bar, snap.rho, mso)
        if rth_only and not stamp.in_rth:
            continue
        for s in signals:
            d = asdict(s)
            d.update(
                {
                    "direction": s.direction.value,
                    "level_price": s.entry_reference,
                    "anchor": snap.anchor,
                    "z": snap.z,
                    "is_entry": True,
                    "score": float("nan"),
                    "session_date": stamp.session_date.isoformat(),
                    "rung": "OTE " + ("long" if s.direction.value == "Buying" else "short"),
                    "close": bar.close,
                }
            )
            rows.append(d)
    if not rows:
        return pd.DataFrame(columns=["ts", "direction", "level_price", "stop_price", "target_price", "anchor", "rho", "is_entry", "score", "session_date", "rung"])
    out = pd.DataFrame(rows)
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out.sort_values("ts", kind="stable").reset_index(drop=True)
