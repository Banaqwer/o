"""
Unified signal representation.

All strategy-specific signals are normalized into TradingSignal
for use by the aggregator and position manager.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, Any
from enum import Enum


class SignalDirection(str, Enum):
    LONG  = "long"
    SHORT = "short"
    EXIT  = "exit"


class SignalSource(str, Enum):
    LUNATION_DUAD_QUALITY      = "lunation_duad_quality"
    EIGHTH_WAY                 = "eighth_way"
    SOLAR_TREND                = "solar_trend"
    LUNAR_TREND_CONFIRMATION   = "lunar_trend_confirmation"
    ELEMENTAL_QUALITY          = "elemental_quality_connection"
    GOLDEN_RATIO               = "golden_ratio"
    SUN_NEPTUNE                = "sun_neptune"
    MUTABLE_FACTOR             = "mutable_factor"
    LUNAR_PHASE_DUAD           = "lunar_phase_duad"
    INTERMARKET_DIVERGENCE     = "intermarket_divergence"


@dataclass
class TradingSignal:
    """
    A normalized trade signal output from any of the 10 strategies.
    """
    source: SignalSource
    direction: SignalDirection
    signal_date: date
    symbol: str
    entry_price: float
    stop_price: float
    target_price: float
    risk: float = 0.0
    risk_reward_ratio: float = 0.0

    # Optional secondary targets (for 2-part exits like Mutable Factor)
    target_price_half: Optional[float] = None

    # Confidence: 1 (single strategy) up to 10 (all strategies agree)
    confidence: int = 1

    # Raw signal object from the strategy
    raw_signal: Optional[Any] = None

    # Additional metadata
    notes: str = ""

    def __post_init__(self):
        if self.stop_price and self.entry_price:
            self.risk = abs(self.entry_price - self.stop_price)
        if self.risk and self.target_price:
            potential_reward = abs(self.target_price - self.entry_price)
            self.risk_reward_ratio = potential_reward / self.risk if self.risk else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source":            self.source.value,
            "direction":         self.direction.value,
            "signal_date":       str(self.signal_date),
            "symbol":            self.symbol,
            "entry_price":       round(self.entry_price, 4),
            "stop_price":        round(self.stop_price, 4),
            "target_price":      round(self.target_price, 4),
            "risk":              round(self.risk, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "confidence":        self.confidence,
            "notes":             self.notes,
        }
