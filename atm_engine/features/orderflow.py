"""Order flow.

When the feed carries bid/ask-classified volume it is used directly;
otherwise signed volume is inferred by bulk-volume classification
(Easley, Lopez de Prado, O'Hara): the buy share of a bar's volume is the
normal CDF of its standardised price change.

Two things come out of this component:

* **absorption proposals** -- bars whose standardised delta is in the upper
  tail of its rolling distribution while the body is small relative to the
  range: aggressive flow that failed to move price marks a level;
* **divergence at a test** -- price printing a new local extreme while the
  rolling delta fails to confirm, plus intrabar rejection.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List

from ..config import OrderFlowConfig
from ..types import Bar, Direction, Proposal
from .estimators import EwmVar, RollingSum, SortedWindow, clip, norm_cdf


@dataclass(frozen=True)
class OrderFlowSnapshot:
    delta: float
    delta_z: float
    cum_delta: float
    buy_fraction: float


@dataclass
class _Absorption:
    price: float
    weight: float
    age: int
    side: Direction


class OrderFlowState:
    def __init__(self, cfg: OrderFlowConfig):
        self.cfg = cfg
        self._dp_var = EwmVar(cfg.bvc_half_life)
        self._delta_var = EwmVar(cfg.delta_half_life)
        self._abs_dz = SortedWindow(cfg.absorption_window)
        self._prev_close: float | None = None
        self._cum = 0.0
        self._absorptions: Deque[_Absorption] = deque(maxlen=64)
        w = cfg.divergence_window
        self._delta_win = RollingSum(w)
        self._win_hist: Deque[float] = deque(maxlen=w + 1)  # window sums, oldest first
        self._win_var = EwmVar(cfg.delta_half_life)
        self._highs: Deque[float] = deque(maxlen=w + 1)
        self._lows: Deque[float] = deque(maxlen=w + 1)
        self.snapshot: OrderFlowSnapshot | None = None

    def update(self, bar: Bar, is_open_bar: bool) -> OrderFlowSnapshot:
        if is_open_bar:
            self._cum = 0.0
        dp = 0.0 if self._prev_close is None else bar.close - self._prev_close
        self._prev_close = bar.close
        self._dp_var.update(dp)

        if bar.buy_volume is not None and bar.sell_volume is not None:
            buy, sell = bar.buy_volume, bar.sell_volume
            frac = buy / bar.volume if bar.volume > 0 else 0.5
        else:
            s = self._dp_var.std
            if s == s and s > 0:
                frac = norm_cdf(dp / s)
            else:
                frac = 0.5 if dp == 0 else (1.0 if dp > 0 else 0.0)
            buy = bar.volume * frac
            sell = bar.volume - buy
        delta = buy - sell
        self._cum += delta
        self._delta_var.update(delta)
        dz = self._delta_var.z(delta)
        self._abs_dz.push(abs(dz))

        # window sums for divergence
        self._delta_win.push(delta)
        wsum = self._delta_win.value
        self._win_hist.append(wsum)
        self._win_var.update(wsum)
        self._highs.append(bar.high)
        self._lows.append(bar.low)

        # absorption: top-tail delta with little body
        for a in self._absorptions:
            a.age += 1
        thr = self._abs_dz.quantile(self.cfg.absorption_quantile)
        if thr is not None and len(self._abs_dz) >= 50 and abs(dz) >= thr and bar.high > bar.low:
            body = abs(bar.close - bar.open) / (bar.high - bar.low)
            weight = abs(dz) / max(thr, 1e-9) * (1.0 - body)
            if weight > 0:
                if delta > 0:
                    self._absorptions.append(_Absorption(bar.high, weight, 0, Direction.SELLING))
                else:
                    self._absorptions.append(_Absorption(bar.low, weight, 0, Direction.BUYING))

        self.snapshot = OrderFlowSnapshot(delta, dz, self._cum, frac)
        return self.snapshot

    def proposals(self, half_life_bars: int = 390) -> List[Proposal]:
        out: List[Proposal] = []
        for a in self._absorptions:
            decay = 0.5 ** (a.age / half_life_bars)
            w = a.weight * decay
            if w > 0.05:
                out.append(Proposal(a.price, w, "orderflow", f"absorption/{a.side.value}"))
        return out

    def divergence(self, bar: Bar, direction: Direction) -> float:
        """Score in [0, 1] that flow fails to confirm the move into the level."""

        if len(self._win_hist) < 2 or bar.high <= bar.low:
            return 0.0
        cur = self._win_hist[-1]
        prev = self._win_hist[0]
        s = self._win_var.std
        flow_ok = s == s and s > 0
        if direction is Direction.SELLING:
            new_extreme = bar.high >= max(list(self._highs)[:-1] or [bar.high])
            flow_fade = clip((prev - cur) / s, 0.0, 3.0) / 3.0 if flow_ok else 0.0
            rejection = (bar.high - bar.close) / (bar.high - bar.low)
        else:
            new_extreme = bar.low <= min(list(self._lows)[:-1] or [bar.low])
            flow_fade = clip((cur - prev) / s, 0.0, 3.0) / 3.0 if flow_ok else 0.0
            rejection = (bar.close - bar.low) / (bar.high - bar.low)
        div = flow_fade if new_extreme else 0.0
        return clip(0.5 * div + 0.5 * rejection, 0.0, 1.0)
