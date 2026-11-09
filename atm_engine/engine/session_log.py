"""Per-session record of every level and every event, with its reaction.

Storage is one directory per instrument with JSON-lines files per session:
``<root>/<INSTRUMENT>/<YYYY-MM-DD>.ladder.jsonl`` holds the published
ladder at every bar, ``<root>/<INSTRUMENT>/<YYYY-MM-DD>.events.jsonl`` holds
each event once its reaction has been measured.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from ..types import RUNG_ORDER, Event, Ladder


def ladder_record(ladder: Ladder, session_date: str) -> Dict[str, object]:
    rec: Dict[str, object] = {
        "ts": ladder.ts.isoformat(),
        "session_date": session_date,
        "instrument": ladder.instrument,
        "anchor": ladder.anchor,
        "rho": ladder.rho,
        "width_multiplier": ladder.width_multiplier,
    }
    for r in RUNG_ORDER:
        lv = ladder.levels[r]
        rec[f"{r.name.lower()}"] = lv.price
        rec[f"{r.name.lower()}_confluence"] = lv.confluence
        rec[f"{r.name.lower()}_sources"] = "|".join(lv.sources)
    return rec


class SessionLog:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, instrument: str, session_date: str, kind: str) -> Path:
        d = self.root / instrument.upper()
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{session_date}.{kind}.jsonl"

    def record_ladder(self, ladder: Ladder, session_date: str) -> None:
        with self._path(ladder.instrument, session_date, "ladder").open("a", encoding="utf-8") as f:
            f.write(json.dumps(ladder_record(ladder, session_date)) + "\n")

    def record_event(self, event: Event) -> None:
        with self._path(event.instrument, event.session_date, "events").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_record(), default=str) + "\n")

    def sessions(self, instrument: str) -> List[str]:
        d = self.root / instrument.upper()
        if not d.exists():
            return []
        return sorted({p.name.split(".")[0] for p in d.glob("*.jsonl")})

    def load_events(self, instrument: str, session_date: Optional[str] = None) -> pd.DataFrame:
        return self._load(instrument, session_date, "events")

    def load_ladders(self, instrument: str, session_date: Optional[str] = None) -> pd.DataFrame:
        return self._load(instrument, session_date, "ladder")

    def _load(self, instrument: str, session_date: Optional[str], kind: str) -> pd.DataFrame:
        dates = [session_date] if session_date else self.sessions(instrument)
        rows: List[dict] = []
        for d in dates:
            p = self.root / instrument.upper() / f"{d}.{kind}.jsonl"
            if p.exists():
                with p.open(encoding="utf-8") as f:
                    rows.extend(json.loads(line) for line in f if line.strip())
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values("ts", kind="stable").reset_index(drop=True)


class MemoryLog:
    """In-memory log with the same interface, for research runs."""

    def __init__(self) -> None:
        self.ladders: List[Dict[str, object]] = []
        self.events: List[Event] = []

    def record_ladder(self, ladder: Ladder, session_date: str) -> None:
        self.ladders.append(ladder_record(ladder, session_date))

    def record_event(self, event: Event) -> None:
        self.events.append(event)

    def events_frame(self) -> pd.DataFrame:
        if not self.events:
            return pd.DataFrame()
        df = pd.DataFrame([e.to_record() for e in self.events])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.sort_values("ts", kind="stable").reset_index(drop=True)

    def ladders_frame(self) -> pd.DataFrame:
        if not self.ladders:
            return pd.DataFrame()
        df = pd.DataFrame(self.ladders)
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.set_index("ts")
