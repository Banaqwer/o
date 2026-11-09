"""Statistical deviation analysis.

Price is measured against the session's volume-weighted anchor (VWAP). The
dispersion unit ``rho`` is the volume-weighted standard deviation of traded
prices around that anchor, floored by the one-bar volatility so that the
unit is defined from the very first print of the session.

The band multipliers that place the inner and outer rungs are *not*
constants: they are quantiles of the rolling empirical distribution of |z|,
so the rungs sit where price has historically spent a given share of its
time, and they re-scale automatically as the instrument's behaviour changes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import DeviationConfig
from ..types import Bar
from .estimators import EwmVar, SortedWindow


@dataclass(frozen=True)
class DeviationSnapshot:
    anchor: float
    rho: float
    z: float
    k_inner: float
    k_outer: float
    bar_sigma: float  # one-bar price volatility in points
    warmed_up: bool


class DeviationState:
    def __init__(self, cfg: DeviationConfig, tick_size: float):
        self.cfg = cfg
        self.tick = tick_size
        self._sv = 0.0
        self._spv = 0.0
        self._sppv = 0.0
        self._ret_var = EwmVar(cfg.vol_half_life)
        self._abs_z = SortedWindow(cfg.quantile_window)
        self._prev_close: float | None = None
        self._last_range = 0.0
        self.snapshot: DeviationSnapshot | None = None

    def reset_session(self) -> None:
        self._sv = self._spv = self._sppv = 0.0

    def update(self, bar: Bar, in_rth: bool, is_open_bar: bool) -> DeviationSnapshot:
        if is_open_bar:
            self.reset_session()
        if self._prev_close is not None and self._prev_close > 0 and bar.close > 0:
            self._ret_var.update(math.log(bar.close / self._prev_close))
        self._prev_close = bar.close
        self._last_range = bar.high - bar.low

        if in_rth:
            p = bar.typical
            v = bar.volume
            self._sv += v
            self._spv += p * v
            self._sppv += p * p * v

        anchor = self._spv / self._sv if self._sv > 0 else bar.close
        var_vwap = max(self._sppv / self._sv - anchor * anchor, 0.0) if self._sv > 0 else 0.0

        bar_sigma = self._ret_var.std * bar.close if self._ret_var.n > 1 and self._ret_var.std == self._ret_var.std else float("nan")
        if not (bar_sigma == bar_sigma) or bar_sigma <= 0:
            bar_sigma = max(self._last_range, self.tick)
        rho = math.sqrt(var_vwap + bar_sigma * bar_sigma)
        rho = max(rho, self.tick)

        z = (bar.close - anchor) / rho
        if in_rth and not is_open_bar:
            self._abs_z.push(abs(z))

        warmed = len(self._abs_z) >= self.cfg.min_samples
        if warmed:
            k_in = self._abs_z.quantile(self.cfg.inner_quantile) or self.cfg.warmup_inner
            k_out = self._abs_z.quantile(self.cfg.outer_quantile) or self.cfg.warmup_outer
        else:
            k_in, k_out = self.cfg.warmup_inner, self.cfg.warmup_outer
        self.snapshot = DeviationSnapshot(anchor, rho, z, k_in, k_out, bar_sigma, warmed)
        return self.snapshot

    def abs_z_rank(self, value: float) -> float:
        """Empirical CDF of |z| -- used to measure how far beyond a band price went."""
        return self._abs_z.rank(abs(value))
