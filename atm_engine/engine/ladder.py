"""Holistic synthesis of the four-rung ladder.

Given the deviation anchor and dispersion, the regime width multiplier and
the proposals from the order-flow, liquidity and structure components, the
builder publishes Omega II / Omega I above price and Alpha I / Alpha II below
it. The procedure:

1. **Band sequence.** Multiples of ``rho`` read from the empirical |z|
   distribution (inner, outer, then equally spaced extensions) are scaled by
   the regime multiplier and laid out around the anchor on both sides.
2. **Confluence.** Every proposal attaches to the nearest band within a
   kernel window and pulls it with weight ``component weight x regime scale
   x kernel(distance)``. The summed weight is the band's confluence. The
   result is a set of *candidate* levels per side.
3. **Placement.** A rung with no published value, or one that has just been
   broken, takes the first candidate that clears price by the minimum gap
   (rung II: the first candidate clearing rung I by the minimum rung gap).
   When price is already beyond the inner band the rung therefore steps out
   to the next band -- the ladder "adapts as price moves".
4. **Hysteresis.** A published rung that has not been broken is compared
   with the candidate nearest to it: it is held while that candidate stays
   within a tolerance, drifts with it when the candidate moves materially
   and still sits beyond price, and is otherwise held. A held rung can be
   traded through intrabar, and even closed through within the break
   tolerance, without moving -- that is what makes it testable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..config import LadderConfig
from ..features.deviation import DeviationSnapshot
from ..types import RUNG_ORDER, Ladder, Level, Proposal, RegimeSnapshot, Rung

Candidate = Tuple[float, float, Tuple[str, ...]]  # price, confluence, sources


class LadderBuilder:
    N_BANDS = 8

    def __init__(self, cfg: LadderConfig, tick_size: float, instrument: str):
        self.cfg = cfg
        self.tick = tick_size
        self.instrument = instrument

    # ------------------------------------------------------------------ helpers
    def _round(self, x: float) -> float:
        return round(round(x / self.tick) * self.tick, 10)

    def _band_sequence(self, k_in: float, k_out: float) -> List[float]:
        gap = max(k_out - k_in, self.cfg.min_rung_gap_sigma)
        seq = [k_in, k_in + gap]
        while len(seq) < self.N_BANDS:
            seq.append(seq[-1] + gap)
        return seq

    def _candidates(
        self,
        dev: DeviationSnapshot,
        width: float,
        proposals: Iterable[Proposal],
        scales: Dict[str, float],
    ) -> Tuple[List[Candidate], List[Candidate]]:
        """Snapped band candidates above and below the anchor, nearest first."""

        c = self.cfg
        rho, anchor = dev.rho, dev.anchor
        ks = self._band_sequence(dev.k_inner, dev.k_outer)
        ups = [anchor + k * rho * width for k in ks]
        dns = [anchor - k * rho * width for k in ks]
        bands = ups + dns
        n = len(bands)
        window = c.snap_window_sigma * rho
        comp_w = {"orderflow": c.w_orderflow, "liquidity": c.w_liquidity, "structure": c.w_structure}

        num = [c.deviation_weight * b for b in bands]
        den = [c.deviation_weight] * n
        conf = [0.0] * n
        srcs: List[List[str]] = [[] for _ in range(n)]
        for p in proposals:
            j = min(range(n), key=lambda i: abs(bands[i] - p.price))
            d = abs(bands[j] - p.price)
            if d > window:
                continue
            kern = 1.0 - (d / window) ** 2
            w = p.weight * comp_w.get(p.source, 0.5) * scales.get(p.source, 1.0) * kern
            if w <= 0:
                continue
            num[j] += w * p.price
            den[j] += w
            conf[j] += w
            srcs[j].append(p.detail or p.source)

        out = [(self._round(num[i] / den[i]), conf[i], tuple(sorted(set(srcs[i])))) for i in range(n)]
        up_c = sorted(out[: len(ups)], key=lambda t: t[0])
        dn_c = sorted(out[len(ups) :], key=lambda t: -t[0])
        return up_c, dn_c

    # -------------------------------------------------------------------- build
    def build(
        self,
        ts: datetime,
        price: float,
        dev: DeviationSnapshot,
        regime: RegimeSnapshot,
        proposals: Iterable[Proposal],
        scales: Dict[str, float],
        prev: Optional[Ladder] = None,
        breached: Optional[Set[Rung]] = None,
    ) -> Ladder:
        breached = breached or set()
        rho = dev.rho
        width = regime.width_multiplier
        up_c, dn_c = self._candidates(dev, width, list(proposals), scales)
        gap_in = self.cfg.min_inner_gap_sigma * rho
        gap_rung = self.cfg.min_rung_gap_sigma * rho
        h = self.cfg.hysteresis_sigma * rho

        def old(r: Rung) -> Optional[Level]:
            if prev is None or r in breached:
                return None
            return prev.levels[r]

        levels: Dict[Rung, Level] = {}
        # upper side
        o1 = self._place(Rung.OMEGA_I, old(Rung.OMEGA_I), up_c, price + gap_in, +1, h, rho)
        o2 = self._place(Rung.OMEGA_II, old(Rung.OMEGA_II), up_c, o1.price + gap_rung, +1, h, rho)
        # lower side
        a1 = self._place(Rung.ALPHA_I, old(Rung.ALPHA_I), dn_c, price - gap_in, -1, h, rho)
        a2 = self._place(Rung.ALPHA_II, old(Rung.ALPHA_II), dn_c, a1.price - gap_rung, -1, h, rho)
        levels = {Rung.OMEGA_II: o2, Rung.OMEGA_I: o1, Rung.ALPHA_I: a1, Rung.ALPHA_II: a2}

        o2p, o1p, a1p, a2p = (levels[r].price for r in RUNG_ORDER)
        if not (o2p > o1p > a1p > a2p):
            # held rungs from different bars can cross after a violent bar; re-place everything
            o1 = self._place(Rung.OMEGA_I, None, up_c, price + gap_in, +1, h, rho)
            o2 = self._place(Rung.OMEGA_II, None, up_c, o1.price + gap_rung, +1, h, rho)
            a1 = self._place(Rung.ALPHA_I, None, dn_c, price - gap_in, -1, h, rho)
            a2 = self._place(Rung.ALPHA_II, None, dn_c, a1.price - gap_rung, -1, h, rho)
            levels = {Rung.OMEGA_II: o2, Rung.OMEGA_I: o1, Rung.ALPHA_I: a1, Rung.ALPHA_II: a2}
        ladder = Ladder(ts, self.instrument, dev.anchor, rho, width, levels)
        ladder.validate()
        return ladder

    def _place(
        self,
        rung: Rung,
        old: Optional[Level],
        cands: List[Candidate],
        floor: float,
        sign: int,
        h: float,
        rho: float,
    ) -> Level:
        """Choose the level for ``rung``.

        ``floor`` is the price the level must clear (above it when sign=+1,
        below when sign=-1) if it is freshly placed or drifting.
        """

        def clears(x: float) -> bool:
            return x >= floor if sign > 0 else x <= floor

        def fresh() -> Level:
            for p, conf, src in cands:
                if clears(p):
                    return Level(rung, p, conf, src)
            # beyond the last band: extend from the floor by one rung gap
            p = self._round(floor + sign * self.cfg.min_rung_gap_sigma * rho)
            return Level(rung, p, 0.0, ())

        if old is None:
            return fresh()

        # rung II must stay beyond rung I; if it no longer does, re-place it
        if not clears(old.price):
            if rung.is_outer:
                return fresh()
            # rung I: a close slightly through the level is a test in progress; hold
            return old

        nearest = min(cands, key=lambda t: abs(t[0] - old.price))
        p, conf, src = nearest
        if abs(p - old.price) < h:
            return Level(rung, old.price, conf, src)  # hold, refresh confluence
        if clears(p):
            return Level(rung, p, conf, src)  # drift with the band
        return old
