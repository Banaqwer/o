"""The reversal engine.

Consumes one bar at a time and, during the regular session:

* updates every component on the bar;
* reads the bar against the ladder that was published *before* it -- a
  level is tested when the bar trades into it, and broken when the bar
  closes through it by the break tolerance;
* prints an event for each test with price, direction and timestamp, and a
  score that weighs the full ladder (position of the test within the
  ladder, how many rungs on that side have already given way) together
  with confluence, overshoot, flow divergence, climactic volume and regime
  confidence; an event is an *entry* when its score clears the rolling
  quantile of past scores;
* republishes the ladder for the next bar.

The same object serves research replay and live streaming.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from ..config import EngineConfig
from ..data.sessions import SessionClock, SessionStamp, minutes_since_open
from ..features.deviation import DeviationState
from ..features.estimators import SortedWindow, clip, logistic
from ..features.liquidity import LiquidityState
from ..features.orderflow import OrderFlowState
from ..features.regime import RegimeState
from ..features.structure import StructureState
from ..types import RUNG_ORDER, Bar, Direction, Event, Ladder, Proposal, RegimeSnapshot, Rung
from .ladder import LadderBuilder
from .reaction import ReactionTracker


class RungState(str, Enum):
    ARMED = "armed"
    TESTED = "tested"  # touched; waiting for price to retreat before re-arming
    BROKEN = "broken"


@dataclass
class StepResult:
    bar: Bar
    stamp: SessionStamp
    ladder: Optional[Ladder]
    events: List[Event]
    regime: Optional[RegimeSnapshot]
    anchor: float
    rho: float
    z: float


@dataclass
class _SessionState:
    date: str
    rung_state: Dict[Rung, RungState] = field(default_factory=lambda: {r: RungState.ARMED for r in RUNG_ORDER})
    broken_upper: int = 0
    broken_lower: int = 0
    tested: Dict[Rung, int] = field(default_factory=lambda: {r: 0 for r in RUNG_ORDER})


class ReversalEngine:
    def __init__(self, cfg: EngineConfig, log=None):
        self.cfg = cfg
        self.log = log
        self.clock = SessionClock(cfg.session)
        self.deviation = DeviationState(cfg.deviation, cfg.tick_size)
        self.orderflow = OrderFlowState(cfg.orderflow)
        self.liquidity = LiquidityState(cfg.liquidity, cfg.tick_size)
        self.structure = StructureState(cfg.structure, cfg.session.opening_range_bars)
        self.regime = RegimeState(cfg.regime)
        self.builder = LadderBuilder(cfg.ladder, cfg.tick_size, cfg.instrument)
        self.reactions = ReactionTracker(cfg.reaction, self._on_reaction)
        self._scores = SortedWindow(cfg.reversal.entry_window)
        self.ladder: Optional[Ladder] = None
        self._session: Optional[_SessionState] = None
        self._bar_index = 0
        self._last_rho = cfg.tick_size * 8
        self.events: List[Event] = []

    # ---------------------------------------------------------------- plumbing
    def _on_reaction(self, event: Event) -> None:
        if self.log is not None:
            self.log.record_event(event)

    def _start_session(self, stamp: SessionStamp) -> None:
        if self._session is not None:
            self.reactions.close_session()
        self._session = _SessionState(stamp.session_date.isoformat())
        self.liquidity.start_session(self._last_rho)
        self.ladder = None

    def finish(self) -> None:
        """Flush pending reactions at the end of a replay or a live day."""
        self.reactions.close_session()

    # ------------------------------------------------------------------- main
    def on_bar(self, bar: Bar) -> StepResult:
        self._bar_index += 1
        stamp = self.clock.stamp(bar.ts)
        if stamp.is_open_bar:
            self._start_session(stamp)

        dev = self.deviation.update(bar, stamp.in_rth, stamp.is_open_bar)
        of = self.orderflow.update(bar, stamp.is_open_bar)
        minute = int(max(minutes_since_open(bar.ts, self.cfg.session), 0))
        liq = self.liquidity.update(bar, of.delta, minute, stamp.in_rth)
        reg = self.regime.update(bar, liq.illiquidity_z, liq.relative_volume)
        tol = self.cfg.reversal.touch_tolerance_sigma * dev.rho
        self.structure.update(bar, stamp.in_rth, stamp.is_open_bar, tol)

        if not stamp.in_rth or self._session is None:
            return StepResult(bar, stamp, None, [], reg, dev.anchor, dev.rho, dev.z)

        self._last_rho = dev.rho
        self.reactions.on_bar(bar, self._bar_index)

        events: List[Event] = []
        breached: Set[Rung] = set()
        if self.ladder is not None:
            events, breached = self._read_ladder(bar, dev, reg, liq)
            for e in events:
                self.reactions.add(e, self._bar_index)
                self.events.append(e)

        proposals: List[Proposal] = []
        proposals.extend(self.orderflow.proposals(self.cfg.structure.swing_half_life))
        proposals.extend(self.liquidity.proposals())
        proposals.extend(self.structure.proposals())
        self.ladder = self.builder.build(
            bar.ts, bar.close, dev, reg, proposals, self.regime.component_scale(), self.ladder, breached
        )
        for r in breached:
            self._session.rung_state[r] = RungState.ARMED
        self._rearm(bar, dev.rho)
        if self.log is not None:
            self.log.record_ladder(self.ladder, self._session.date)
        return StepResult(bar, stamp, self.ladder, events, reg, dev.anchor, dev.rho, dev.z)

    # ------------------------------------------------------------- level tests
    def _read_ladder(self, bar: Bar, dev, reg: RegimeSnapshot, liq):
        assert self.ladder is not None and self._session is not None
        cfg = self.cfg.reversal
        rho = dev.rho
        tol = cfg.touch_tolerance_sigma * rho
        brk = cfg.break_sigma * rho
        sess = self._session
        events: List[Event] = []
        breached: Set[Rung] = set()

        for rung in RUNG_ORDER:
            lv = self.ladder.levels[rung]
            state = sess.rung_state[rung]
            if rung.is_upper:
                touched = bar.high >= lv.price - tol
                broken = bar.close > lv.price + brk
                test_price = bar.high
            else:
                touched = bar.low <= lv.price + tol
                broken = bar.close < lv.price - brk
                test_price = bar.low

            if touched and state is RungState.ARMED:
                sess.tested[rung] += 1
                z_test = (test_price - dev.anchor) / rho
                ev = self._make_event(bar, rung, lv.price, test_price, dev, reg, liq, z_test)
                events.append(ev)
                sess.rung_state[rung] = RungState.TESTED
            if broken:
                breached.add(rung)
                if rung.is_upper:
                    sess.broken_upper += 1
                else:
                    sess.broken_lower += 1
                sess.rung_state[rung] = RungState.BROKEN
        return events, breached

    def _rearm(self, bar: Bar, rho: float) -> None:
        assert self.ladder is not None and self._session is not None
        back = self.cfg.reversal.rearm_sigma * rho
        for rung in RUNG_ORDER:
            if self._session.rung_state[rung] is RungState.TESTED:
                lv = self.ladder.levels[rung]
                away = (lv.price - bar.high) >= back if rung.is_upper else (bar.low - lv.price) >= back
                if away:
                    self._session.rung_state[rung] = RungState.ARMED

    # ------------------------------------------------------------------ scoring
    def _make_event(self, bar: Bar, rung: Rung, level_price: float, test_price: float, dev, reg, liq, z_test: float) -> Event:
        assert self.ladder is not None and self._session is not None
        cfg = self.cfg.reversal
        lv = self.ladder.levels[rung]
        direction = rung.direction

        confluence = math.tanh(lv.confluence / 2.0)
        if dev.warmed_up:
            overshoot = self.deviation.abs_z_rank(z_test)
        else:
            overshoot = clip(abs(z_test) / (2.0 * dev.k_outer), 0.0, 1.0)
        divergence = self.orderflow.divergence(bar, direction)
        climax = logistic(liq.relative_volume_z)
        regime_conf = reg.confidence

        top = self.ladder.levels[Rung.OMEGA_II].price
        bot = self.ladder.levels[Rung.ALPHA_II].price
        u = (test_price - bot) / (top - bot) if top > bot else 0.5
        extremity = clip(2.0 * abs(u - 0.5), 0.0, 1.0)
        broken_same = self._session.broken_upper if rung.is_upper else self._session.broken_lower
        ladder_ctx = extremity * (0.5 ** broken_same)

        logit = (
            cfg.bias
            + cfg.s_confluence * confluence
            + cfg.s_overshoot * overshoot
            + cfg.s_divergence * divergence
            + cfg.s_climax * climax
            + cfg.s_regime * regime_conf
            + cfg.s_ladder * ladder_ctx
        )
        score = logistic(logit)
        thr = self._scores.quantile(cfg.entry_quantile) if len(self._scores) >= 50 else None
        threshold = cfg.warmup_entry_threshold if thr is None else thr
        is_entry = score >= threshold
        self._scores.push(score)

        return Event(
            ts=bar.ts,
            instrument=self.cfg.instrument,
            rung=rung,
            direction=direction,
            level_price=level_price,
            test_price=test_price,
            close=bar.close,
            anchor=dev.anchor,
            rho=dev.rho,
            z=z_test,
            score=score,
            is_entry=is_entry,
            components={
                "confluence": confluence,
                "overshoot": overshoot,
                "divergence": divergence,
                "climax": climax,
                "regime": regime_conf,
                "ladder": ladder_ctx,
                "threshold": threshold,
            },
            regime=reg,
            ladder={r.name.lower(): self.ladder.levels[r].price for r in RUNG_ORDER},
            session_date=self._session.date,
        )
