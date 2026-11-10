"""Forward reaction measurement for printed events.

For every event the tracker follows subsequent bars and records, at each
configured horizon, the maximum favourable excursion, the maximum adverse
excursion and whether price returned to the anchor that was in force when
the level was tested. Excursions are measured from the open of the bar
after the event (the first price obtainable once the event is known), not
from the level price: the test bar's own rejection is part of the event's
evidence, not of its reaction. Excursions are in points; the record also
carries them in sigma units via the event's ``rho``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..config import ReactionConfig
from ..types import Bar, Direction, Event, Reaction


@dataclass
class _Pending:
    event: Event
    start_index: int
    ref: float = float("nan")  # the next bar's open
    max_high: float = float("-inf")
    min_low: float = float("inf")
    fav: Dict[int, float] = field(default_factory=dict)
    adv: Dict[int, float] = field(default_factory=dict)
    rev: Dict[int, bool] = field(default_factory=dict)


class ReactionTracker:
    def __init__(self, cfg: ReactionConfig, on_complete: Optional[Callable[[Event], None]] = None):
        self.horizons: Tuple[int, ...] = tuple(sorted(cfg.horizons))
        self._pending: List[_Pending] = []
        self._on_complete = on_complete
        self.completed: List[Event] = []

    def add(self, event: Event, bar_index: int) -> None:
        self._pending.append(_Pending(event, bar_index))

    def on_bar(self, bar: Bar, bar_index: int) -> None:
        done: List[_Pending] = []
        for p in self._pending:
            n = bar_index - p.start_index
            if n <= 0:
                continue
            if n == 1:
                p.ref = bar.open
            p.max_high = max(p.max_high, bar.high)
            p.min_low = min(p.min_low, bar.low)
            if n in self.horizons:
                self._record(p, n)
            if n >= self.horizons[-1]:
                done.append(p)
        for p in done:
            self._pending.remove(p)
            self._finish(p)

    def _record(self, p: _Pending, h: int) -> None:
        e = p.event
        ref = p.ref
        if e.direction is Direction.SELLING:
            p.fav[h] = ref - p.min_low
            p.adv[h] = p.max_high - ref
            p.rev[h] = p.min_low <= e.anchor
        else:
            p.fav[h] = p.max_high - ref
            p.adv[h] = ref - p.min_low
            p.rev[h] = p.max_high >= e.anchor

    def _finish(self, p: _Pending) -> None:
        for h in self.horizons:
            if h not in p.fav:
                p.fav[h] = float("nan")
                p.adv[h] = float("nan")
                p.rev[h] = False
        p.event.reaction = Reaction(dict(p.fav), dict(p.adv), dict(p.rev), p.event.rho)
        self.completed.append(p.event)
        if self._on_complete is not None:
            self._on_complete(p.event)

    def close_session(self) -> None:
        """Finalize pending events; horizons the session did not reach stay NaN."""
        for p in self._pending:
            self._finish(p)
        self._pending.clear()

    @property
    def pending(self) -> int:
        return len(self._pending)
