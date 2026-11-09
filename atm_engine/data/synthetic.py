"""Seeded synthetic futures bars for tests and demonstrations.

Clearly labelled, exactly as the source material labels its own dashboard
illustration: *the price path is synthetic, not algorithm output or a record
of trading.* The generator is a mean-reverting process around a slowly
drifting session anchor with an intraday volatility and volume smile, fat
tails and occasional regime switches between ranging and trending days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ..config import SessionConfig


@dataclass(frozen=True)
class SyntheticSpec:
    start_price: float = 20_000.0
    sessions: int = 10
    bar_minutes: int = 1
    # Daily vol of the anchor process (fraction of price).
    anchor_daily_vol: float = 0.008
    # Per-minute vol of the deviation process around the anchor at mid-day.
    minute_vol: float = 0.00035
    # Mean reversion speed per minute of the deviation process (ranging days).
    kappa_range: float = 0.015
    kappa_trend: float = 0.002
    p_trend_day: float = 0.3
    base_volume: float = 900.0
    tick_size: float = 0.25
    include_overnight: bool = False
    seed: int = 20241017


def _smile(u: np.ndarray) -> np.ndarray:
    """U-shaped intraday multiplier on u in [0, 1]."""
    return 0.6 + 1.4 * (2.0 * u - 1.0) ** 2 + 0.3 * np.exp(-(u**2) / 0.01)


def generate(spec: SyntheticSpec = SyntheticSpec(), session: SessionConfig = SessionConfig()) -> pd.DataFrame:
    rng = np.random.default_rng(spec.seed)
    tz = ZoneInfo(session.tz)
    start = datetime(2024, 1, 2, tzinfo=tz)
    while start.weekday() >= 5:
        start += timedelta(days=1)

    open_dt = datetime.combine(start.date(), session.open, tzinfo=tz)
    close_dt = datetime.combine(start.date(), session.close, tzinfo=tz)
    bars_per_session = int((close_dt - open_dt).total_seconds() // 60 // spec.bar_minutes)

    rows = []
    anchor = spec.start_price
    price = anchor
    day = start.date()
    for _ in range(spec.sessions):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        trending = rng.random() < spec.p_trend_day
        kappa = spec.kappa_trend if trending else spec.kappa_range
        drift_day = rng.normal(0.0, spec.anchor_daily_vol) * anchor
        vol_scale = np.exp(rng.normal(0.0, 0.25))
        u = (np.arange(bars_per_session) + 0.5) / bars_per_session
        smile = _smile(u)
        dev = price - anchor
        day_open = datetime.combine(day, session.open, tzinfo=tz)
        for i in range(bars_per_session):
            ts = day_open + timedelta(minutes=i * spec.bar_minutes)
            anchor += drift_day / bars_per_session
            sigma = spec.minute_vol * vol_scale * smile[i] * anchor
            # Student-t innovations for fat tails.
            eps = rng.standard_t(4) / np.sqrt(2.0)
            dev += -kappa * dev + sigma * eps
            o = price
            c = anchor + dev
            # intrabar range from a Brownian bridge-ish approximation
            path = rng.normal(0.0, sigma * 0.5, size=4)
            hi = max(o, c) + abs(path).max() * 0.6
            lo = min(o, c) - abs(path).min() * 0.6 - abs(rng.normal(0, sigma * 0.2))
            q = spec.tick_size
            o, hi, lo, c = (round(x / q) * q for x in (o, hi, lo, c))
            hi = max(hi, o, c)
            lo = min(lo, o, c)
            vol = spec.base_volume * smile[i] * np.exp(rng.normal(0, 0.35)) * (1 + 2.0 * abs(eps) / 3.0)
            # order flow: buy share tilted by the bar's return
            tilt = np.tanh((c - o) / max(sigma, 1e-9) * 0.8)
            buy = vol * (0.5 + 0.5 * tilt) * np.exp(rng.normal(0, 0.1))
            buy = min(max(buy, 0.0), vol)
            rows.append((ts, o, hi, lo, c, float(round(vol)), float(round(buy)), float(round(vol - buy))))
            price = c
        day += timedelta(days=1)

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "buy_volume", "sell_volume"])
    df = df.set_index("ts")
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    df.attrs["synthetic"] = True
    df.attrs["note"] = "Synthetic. Not algorithm output or a record of trading."
    return df
