"""Replay a bar frame through the engine and collect ladders and events.

The replay uses the identical ``ReversalEngine`` code path as live use, bar
by bar. Nothing is vectorised across time, by design: a replay that cannot
peek ahead is the only kind whose statistics mean anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..config import EngineConfig
from ..data.schema import iter_bars, validate_frame
from ..engine.reversal import ReversalEngine
from ..engine.session_log import MemoryLog


@dataclass
class ReplayResult:
    events: pd.DataFrame
    ladders: pd.DataFrame
    n_bars: int
    engine: ReversalEngine


def replay(df: pd.DataFrame, cfg: Optional[EngineConfig] = None, log=None, context=None) -> ReplayResult:
    cfg = cfg or EngineConfig()
    frame = validate_frame(df)
    mem = MemoryLog()
    engine = ReversalEngine(cfg, log=_Tee(mem, log))
    if context is not None:
        engine.set_context(context)
    n = 0
    for bar in iter_bars(frame):
        engine.on_bar(bar)
        n += 1
    engine.finish()
    return ReplayResult(mem.events_frame(), mem.ladders_frame(), n, engine)


class _Tee:
    def __init__(self, *logs):
        self.logs = [l for l in logs if l is not None]

    def record_ladder(self, ladder, session_date):
        for l in self.logs:
            l.record_ladder(ladder, session_date)

    def record_event(self, event):
        for l in self.logs:
            l.record_event(event)
