"""Core value types shared by every layer of the engine."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Tuple


class Direction(str, Enum):
    """Direction label printed with each event.

    The label belongs to the rung, not to the price move: Omega rungs sit
    above price and are selling levels; Alpha rungs sit below and are buying
    levels.
    """

    SELLING = "Selling"
    BUYING = "Buying"


class Rung(str, Enum):
    OMEGA_II = "Ω II"
    OMEGA_I = "Ω I"
    ALPHA_I = "α I"
    ALPHA_II = "α II"

    @property
    def direction(self) -> Direction:
        return Direction.SELLING if self in (Rung.OMEGA_I, Rung.OMEGA_II) else Direction.BUYING

    @property
    def is_upper(self) -> bool:
        return self.direction is Direction.SELLING

    @property
    def is_outer(self) -> bool:
        return self in (Rung.OMEGA_II, Rung.ALPHA_II)

    @property
    def partner(self) -> "Rung":
        return {
            Rung.OMEGA_II: Rung.OMEGA_I,
            Rung.OMEGA_I: Rung.OMEGA_II,
            Rung.ALPHA_I: Rung.ALPHA_II,
            Rung.ALPHA_II: Rung.ALPHA_I,
        }[self]


# Display order on the dashboard: top of the ladder first.
RUNG_ORDER: Tuple[Rung, ...] = (Rung.OMEGA_II, Rung.OMEGA_I, Rung.ALPHA_I, Rung.ALPHA_II)


@dataclass(frozen=True)
class Bar:
    """One time bar. ``buy_volume``/``sell_volume`` are optional; when absent,
    order flow is inferred by bulk-volume classification."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Bar.ts must be timezone-aware")
        if not (self.low <= min(self.open, self.close) and self.high >= max(self.open, self.close)):
            raise ValueError(f"inconsistent OHLC at {self.ts}: {self.open},{self.high},{self.low},{self.close}")
        if self.volume < 0:
            raise ValueError("volume must be non-negative")

    @property
    def typical(self) -> float:
        return (self.high + self.low + self.close) / 3.0


@dataclass(frozen=True)
class Proposal:
    """A candidate reaction price put forward by one component."""

    price: float
    weight: float
    source: str
    detail: str = ""


@dataclass(frozen=True)
class Level:
    rung: Rung
    price: float
    confluence: float  # total proposal weight that pulled the level
    sources: Tuple[str, ...]

    @property
    def direction(self) -> Direction:
        return self.rung.direction


@dataclass(frozen=True)
class Ladder:
    """The four published levels plus the state they were computed from."""

    ts: datetime
    instrument: str
    anchor: float
    rho: float
    width_multiplier: float
    levels: Dict[Rung, Level]

    def __getitem__(self, rung: Rung) -> Level:
        return self.levels[rung]

    def ordered(self) -> Tuple[Level, ...]:
        return tuple(self.levels[r] for r in RUNG_ORDER)

    def validate(self) -> None:
        o2, o1, a1, a2 = (self.levels[r].price for r in RUNG_ORDER)
        if not (o2 > o1 > a1 > a2):
            raise AssertionError(f"ladder not monotonic: {o2}, {o1}, {a1}, {a2}")


@dataclass(frozen=True)
class RegimeSnapshot:
    vol_ratio: float
    efficiency: float
    illiquidity_z: float
    relative_volume: float
    width_multiplier: float
    confidence: float  # in [0, 1]; 1 = conditions most favourable to reversion
    exogenous_z: float = 0.0


@dataclass
class Event:
    """A level test printed by the reversal engine."""

    ts: datetime
    instrument: str
    rung: Rung
    direction: Direction
    level_price: float
    test_price: float
    close: float
    anchor: float
    rho: float
    z: float
    score: float
    is_entry: bool
    components: Dict[str, float]
    regime: RegimeSnapshot
    ladder: Dict[str, float]
    session_date: str
    reaction: Optional["Reaction"] = None
    context: Dict[str, float] = field(default_factory=dict)

    def to_record(self) -> Dict[str, object]:
        rec = {
            "ts": self.ts.isoformat(),
            "session_date": self.session_date,
            "instrument": self.instrument,
            "rung": self.rung.value,
            "direction": self.direction.value,
            "level_price": self.level_price,
            "test_price": self.test_price,
            "close": self.close,
            "anchor": self.anchor,
            "rho": self.rho,
            "z": self.z,
            "score": self.score,
            "is_entry": self.is_entry,
        }
        rec.update({f"c_{k}": v for k, v in self.components.items()})
        rec.update({f"r_{k}": v for k, v in asdict(self.regime).items()})
        rec.update({f"l_{k}": v for k, v in self.ladder.items()})
        rec.update({f"ctx_{k}": v for k, v in self.context.items()})
        if self.reaction is not None:
            rec.update(self.reaction.to_record())
        return rec


@dataclass(frozen=True)
class Reaction:
    """How price behaved after an event, per horizon, in points and sigma units.

    Favourable means in the direction of the rung (down after a Selling
    level, up after a Buying level)."""

    favourable: Dict[int, float]
    adverse: Dict[int, float]
    reverted_to_anchor: Dict[int, bool]
    rho: float

    def to_record(self) -> Dict[str, object]:
        rec: Dict[str, object] = {}
        for h in sorted(self.favourable):
            rec[f"mfe_{h}"] = self.favourable[h]
            rec[f"mae_{h}"] = self.adverse[h]
            rec[f"mfe_sigma_{h}"] = self.favourable[h] / self.rho if self.rho > 0 else float("nan")
            rec[f"mae_sigma_{h}"] = self.adverse[h] / self.rho if self.rho > 0 else float("nan")
            rec[f"reverted_{h}"] = self.reverted_to_anchor[h]
        return rec
