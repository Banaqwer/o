"""Price structure.

Reference prices the market is known to react to, each confirmed only when
it is knowable at the time (swings need ``swing_width`` bars either side,
so a swing becomes a proposal ``swing_width`` bars after it printed):

* prior regular session high, low and close;
* overnight (Globex) high and low;
* opening range high and low;
* developing session high and low;
* confirmed fractal swing highs and lows, weighted by recency and by the
  number of times they were re-tested.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

from ..config import StructureConfig
from ..types import Bar, Proposal


@dataclass
class Swing:
    price: float
    bar_index: int
    is_high: bool
    touches: int = 0


@dataclass
class SessionRefs:
    prior_high: Optional[float] = None
    prior_low: Optional[float] = None
    prior_close: Optional[float] = None
    on_high: Optional[float] = None
    on_low: Optional[float] = None
    or_high: Optional[float] = None
    or_low: Optional[float] = None
    sess_high: Optional[float] = None
    sess_low: Optional[float] = None
    rth_bars: int = 0


class StructureState:
    def __init__(self, cfg: StructureConfig, opening_range_bars: int):
        self.cfg = cfg
        self.or_bars = opening_range_bars
        self.refs = SessionRefs()
        self._buf: Deque[Bar] = deque(maxlen=2 * cfg.swing_width + 1)
        self._i = 0
        self.swings: List[Swing] = []
        self._cur_high: Optional[float] = None
        self._cur_low: Optional[float] = None
        self._cur_close: Optional[float] = None
        self._on_high: Optional[float] = None
        self._on_low: Optional[float] = None

    def update(self, bar: Bar, in_rth: bool, is_open_bar: bool, tol: float) -> None:
        self._i += 1
        r = self.refs
        if is_open_bar:
            # roll the prior session and overnight references
            if self._cur_high is not None:
                r.prior_high, r.prior_low, r.prior_close = self._cur_high, self._cur_low, self._cur_close
            r.on_high, r.on_low = self._on_high, self._on_low
            self._on_high = self._on_low = None
            r.or_high = r.or_low = None
            r.sess_high = r.sess_low = None
            r.rth_bars = 0
            self._cur_high = self._cur_low = self._cur_close = None

        if in_rth:
            r.rth_bars += 1
            self._cur_high = bar.high if self._cur_high is None else max(self._cur_high, bar.high)
            self._cur_low = bar.low if self._cur_low is None else min(self._cur_low, bar.low)
            self._cur_close = bar.close
            r.sess_high, r.sess_low = self._cur_high, self._cur_low
            if r.rth_bars <= self.or_bars:
                r.or_high = bar.high if r.or_high is None else max(r.or_high, bar.high)
                r.or_low = bar.low if r.or_low is None else min(r.or_low, bar.low)
        else:
            self._on_high = bar.high if self._on_high is None else max(self._on_high, bar.high)
            self._on_low = bar.low if self._on_low is None else min(self._on_low, bar.low)

        # swing confirmation with lag
        self._buf.append(bar)
        w = self.cfg.swing_width
        if len(self._buf) == 2 * w + 1:
            mid = self._buf[w]
            highs = [b.high for b in self._buf]
            lows = [b.low for b in self._buf]
            if mid.high >= max(highs) and highs.count(mid.high) == 1:
                self._add_swing(Swing(mid.high, self._i - w, True), tol)
            if mid.low <= min(lows) and lows.count(mid.low) == 1:
                self._add_swing(Swing(mid.low, self._i - w, False), tol)

        # count touches of existing swings
        for s in self.swings:
            if s.bar_index < self._i and bar.low - tol <= s.price <= bar.high + tol:
                s.touches += 1

    def _add_swing(self, s: Swing, tol: float) -> None:
        for existing in self.swings:
            if existing.is_high == s.is_high and abs(existing.price - s.price) <= tol:
                existing.touches += 1
                existing.bar_index = s.bar_index
                return
        self.swings.append(s)
        side = [x for x in self.swings if x.is_high == s.is_high]
        if len(side) > self.cfg.max_swings:
            oldest = min(side, key=lambda x: x.bar_index)
            self.swings.remove(oldest)

    def proposals(self) -> List[Proposal]:
        r = self.refs
        out: List[Proposal] = []
        for name, price, w in (
            ("prior_high", r.prior_high, 1.0),
            ("prior_low", r.prior_low, 1.0),
            ("prior_close", r.prior_close, 0.7),
            ("on_high", r.on_high, 0.8),
            ("on_low", r.on_low, 0.8),
            ("or_high", r.or_high if r.rth_bars >= self.or_bars else None, 0.6),
            ("or_low", r.or_low if r.rth_bars >= self.or_bars else None, 0.6),
            ("sess_high", r.sess_high, 0.5),
            ("sess_low", r.sess_low, 0.5),
        ):
            if price is not None:
                out.append(Proposal(price, w, "structure", name))
        hl = self.cfg.swing_half_life
        for s in self.swings:
            age = self._i - s.bar_index
            w = 0.6 * (0.5 ** (age / hl)) * (1.0 + 0.5 * min(s.touches, 4))
            if w > 0.05:
                out.append(Proposal(s.price, w, "structure", "swing_high" if s.is_high else "swing_low"))
        return out
