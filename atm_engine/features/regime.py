"""Regime detection.

Three standardised statistics describe the environment:

* ``vol_ratio`` -- fast over slow EWMA volatility (expanding / contracting);
* ``efficiency`` -- Kaufman's efficiency ratio (trending vs. two-sided);
* ``illiquidity_z`` -- standardised log-Amihud from the liquidity component;
* optionally ``exogenous_z`` -- a daily context such as the standardised
  log-VIX at the previous close (see :mod:`atm_engine.research.context`).

They are combined into a log-linear **width multiplier** on the ladder and a
**confidence** in [0, 1] that reversion behaviour is intact. Both are
centred on the instrument's own recent history, so a "high-volatility
regime" for GC is defined relative to GC, not to a fixed number.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Dict

from ..config import RegimeConfig
from ..types import Bar, RegimeSnapshot
from .estimators import EwmVar, clip, logistic


class RegimeState:
    def __init__(self, cfg: RegimeConfig):
        self.cfg = cfg
        self._fast = EwmVar(cfg.fast_vol_half_life)
        self._slow = EwmVar(cfg.slow_vol_half_life)
        self._closes: Deque[float] = deque(maxlen=cfg.efficiency_window + 1)
        self._abs_moves: Deque[float] = deque(maxlen=cfg.efficiency_window)
        hl = max(cfg.standardise_window / 2, 10)
        self._z_vol = EwmVar(hl)
        self._z_er = EwmVar(hl)
        self._prev_close: float | None = None
        self.snapshot: RegimeSnapshot | None = None

    def update(self, bar: Bar, illiquidity_z: float, relative_volume: float, exogenous_z: float = 0.0) -> RegimeSnapshot:
        if self._prev_close is not None and self._prev_close > 0:
            r = math.log(bar.close / self._prev_close)
            self._fast.update(r)
            self._slow.update(r)
            self._abs_moves.append(abs(bar.close - self._prev_close))
        self._prev_close = bar.close
        self._closes.append(bar.close)

        fs, ss = self._fast.std, self._slow.std
        vol_ratio = fs / ss if fs == fs and ss == ss and ss > 0 else 1.0
        log_vr = math.log(max(vol_ratio, 1e-9))
        z_vol = self._z_vol.z(log_vr)
        self._z_vol.update(log_vr)

        if len(self._closes) == self._closes.maxlen and sum(self._abs_moves) > 0:
            er = abs(self._closes[-1] - self._closes[0]) / sum(self._abs_moves)
        else:
            er = 0.5
        z_er = self._z_er.z(er)
        self._z_er.update(er)

        c = self.cfg
        raw = clip(
            c.beta_trend * z_er + c.beta_vol * z_vol + c.beta_illiq * illiquidity_z + c.beta_exogenous * exogenous_z,
            -3.0,
            3.0,
        )
        lo, hi = c.width_bounds
        width = clip(math.exp(raw), lo, hi)
        confidence = 1.0 - logistic(raw)
        self.snapshot = RegimeSnapshot(vol_ratio, er, illiquidity_z, relative_volume, width, confidence, exogenous_z)
        return self.snapshot

    def component_scale(self) -> Dict[str, float]:
        """Mild re-weighting of level sources by regime.

        Trending tape respects structural references more than statistical
        bands; expanding volatility makes flow-based absorption more
        informative; the deviation anchor is never down-weighted below its
        neutral value, only the others are raised."""

        s = self.snapshot
        if s is None:
            return {"orderflow": 1.0, "liquidity": 1.0, "structure": 1.0}
        z_er = self._z_er.z(s.efficiency)
        z_vol = self._z_vol.z(math.log(max(s.vol_ratio, 1e-9)))
        return {
            "orderflow": 1.0 + 0.25 * clip(z_vol, 0.0, 2.0),
            "liquidity": 1.0,
            "structure": 1.0 + 0.25 * clip(z_er, 0.0, 2.0),
        }
