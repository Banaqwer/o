"""Liquidity dynamics.

* **Price impact** -- Amihud illiquidity (|return| per unit volume) and
  Kyle's lambda (price change per unit signed volume), both as EWMAs, with the
  standardised log-Amihud reported to the regime component.
* **Relative volume** -- volume against an exponentially-weighted
  time-of-day profile built across prior sessions, so a climactic print at
  10:03 is judged against what 10:03 usually does.
* **Volume profile** -- per-session distribution of traded volume by price,
  from which the point of control, value area and high-volume nodes of the
  prior session and of the developing session are proposed as levels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..config import LiquidityConfig
from ..types import Bar, Proposal
from .estimators import Ewma, EwmVar


@dataclass(frozen=True)
class LiquiditySnapshot:
    amihud: float
    illiquidity_z: float
    kyle_lambda: float
    relative_volume: float
    relative_volume_z: float


@dataclass(frozen=True)
class ProfileSummary:
    poc: float
    vah: float
    val: float
    hvns: Tuple[Tuple[float, float], ...]  # (price, volume share)
    total: float


class VolumeProfile:
    """Price-binned volume for one session."""

    def __init__(self, bin_width: float):
        if bin_width <= 0:
            raise ValueError("bin_width must be positive")
        self.bin_width = bin_width
        self.bins: Dict[int, float] = {}
        self.total = 0.0

    def add(self, bar: Bar) -> None:
        if bar.volume <= 0:
            return
        lo_i = int(math.floor(bar.low / self.bin_width))
        hi_i = int(math.floor(bar.high / self.bin_width))
        n = hi_i - lo_i + 1
        share = bar.volume / n
        for i in range(lo_i, hi_i + 1):
            self.bins[i] = self.bins.get(i, 0.0) + share
        self.total += bar.volume

    def summary(self, value_area: float, hvn_quantile: float) -> Optional[ProfileSummary]:
        if not self.bins or self.total <= 0:
            return None
        items = sorted(self.bins.items())
        idx = [i for i, _ in items]
        vol = [v for _, v in items]
        k = max(range(len(vol)), key=vol.__getitem__)
        poc = (idx[k] + 0.5) * self.bin_width
        # value area: expand from POC toward the larger neighbour until share reached
        target = value_area * self.total
        acc = vol[k]
        lo, hi = k, k
        while acc < target and (lo > 0 or hi < len(vol) - 1):
            up = vol[hi + 1] if hi < len(vol) - 1 else -1.0
            dn = vol[lo - 1] if lo > 0 else -1.0
            if up >= dn:
                hi += 1
                acc += up
            else:
                lo -= 1
                acc += dn
        vah = (idx[hi] + 1.0) * self.bin_width
        val = idx[lo] * self.bin_width
        # high-volume nodes: contiguous runs of bins above the quantile
        srt = sorted(vol)
        q = srt[min(len(srt) - 1, int(hvn_quantile * (len(srt) - 1)))]
        hvns: List[Tuple[float, float]] = []
        run_v = 0.0
        run_pv = 0.0
        prev_i: Optional[int] = None
        for i, v in zip(idx, vol):
            if v >= q and v > 0:
                if prev_i is not None and i != prev_i + 1 and run_v > 0:
                    hvns.append((run_pv / run_v, run_v / self.total))
                    run_v = run_pv = 0.0
                run_v += v
                run_pv += v * (i + 0.5) * self.bin_width
                prev_i = i
            elif run_v > 0:
                hvns.append((run_pv / run_v, run_v / self.total))
                run_v = run_pv = 0.0
                prev_i = None
        if run_v > 0:
            hvns.append((run_pv / run_v, run_v / self.total))
        return ProfileSummary(poc, vah, val, tuple(hvns), self.total)


class LiquidityState:
    def __init__(self, cfg: LiquidityConfig, tick_size: float):
        self.cfg = cfg
        self.tick = tick_size
        self._amihud = Ewma(cfg.amihud_half_life)
        self._log_amihud = EwmVar(cfg.amihud_half_life * 8)
        self._cov = Ewma(cfg.kyle_half_life)
        self._var_delta = Ewma(cfg.kyle_half_life)
        self._tod: Dict[int, Ewma] = {}
        self._relvol_var = EwmVar(cfg.amihud_half_life * 4)
        self._prev_close: float | None = None
        self._sess_vol_sum = 0.0
        self._sess_vol_n = 0
        self.current: Optional[VolumeProfile] = None
        self.prior: Optional[ProfileSummary] = None
        self._bin_width = max(tick_size * 4, 1e-9)
        self.snapshot: LiquiditySnapshot | None = None

    def start_session(self, rho_hint: float) -> None:
        if self.current is not None:
            self.prior = self.current.summary(self.cfg.value_area, self.cfg.hvn_quantile)
        width = max(self.cfg.profile_bin_sigma * rho_hint, self.tick)
        self._bin_width = round(width / self.tick) * self.tick or self.tick
        self.current = VolumeProfile(self._bin_width)
        self._sess_vol_sum = 0.0
        self._sess_vol_n = 0

    def update(self, bar: Bar, delta: float, minute_of_session: int, in_rth: bool) -> LiquiditySnapshot:
        ret = 0.0 if self._prev_close is None or self._prev_close <= 0 else math.log(bar.close / self._prev_close)
        dp = 0.0 if self._prev_close is None else bar.close - self._prev_close
        self._prev_close = bar.close

        if bar.volume > 0:
            am = abs(ret) / bar.volume
            self._amihud.update(am)
            self._log_amihud.update(math.log(am + 1e-18))
        illiq_z = self._log_amihud.z(math.log(self._amihud.value + 1e-18)) if self._amihud.ready else 0.0

        self._cov.update(dp * delta)
        self._var_delta.update(delta * delta)
        kyle = self._cov.value / self._var_delta.value if self._var_delta.ready and self._var_delta.value > 0 else 0.0

        rel = 1.0
        rel_z = 0.0
        if in_rth:
            prof = self._tod.setdefault(minute_of_session, Ewma(self.cfg.tod_sessions))
            if prof.ready and prof.value > 0:
                expected = prof.value
            elif self._sess_vol_n > 0:
                expected = self._sess_vol_sum / self._sess_vol_n
            else:
                expected = 0.0
            if expected > 0:
                rel = bar.volume / expected
                lr = math.log(max(rel, 1e-9))
                rel_z = self._relvol_var.z(lr)
                self._relvol_var.update(lr)
            prof.update(bar.volume)
            self._sess_vol_sum += bar.volume
            self._sess_vol_n += 1
            if self.current is not None:
                self.current.add(bar)

        self.snapshot = LiquiditySnapshot(self._amihud.value if self._amihud.ready else 0.0, illiq_z, kyle, rel, rel_z)
        return self.snapshot

    def proposals(self) -> List[Proposal]:
        out: List[Proposal] = []
        if self.prior is not None:
            out.append(Proposal(self.prior.poc, 1.0, "liquidity", "prior_poc"))
            out.append(Proposal(self.prior.vah, 0.8, "liquidity", "prior_vah"))
            out.append(Proposal(self.prior.val, 0.8, "liquidity", "prior_val"))
            for price, share in self.prior.hvns:
                out.append(Proposal(price, min(1.0, 4.0 * share), "liquidity", "prior_hvn"))
        if self.current is not None:
            dev = self.current.summary(self.cfg.value_area, self.cfg.hvn_quantile)
            if dev is not None:
                out.append(Proposal(dev.poc, 0.6, "liquidity", "dev_poc"))
                out.append(Proposal(dev.vah, 0.4, "liquidity", "dev_vah"))
                out.append(Proposal(dev.val, 0.4, "liquidity", "dev_val"))
        return out
