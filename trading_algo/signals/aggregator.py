"""
Signal Aggregator.

Collects signals from all strategies, normalizes them into TradingSignal objects,
scores confidence based on agreement across strategies, and filters by:
1. Solar Trend Indicator direction (primary filter)
2. Minimum confidence threshold
3. Minimum risk-reward ratio

The aggregator also deduplicates signals that are very close to each other
(same direction, same date, similar price levels).
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd

from .signal import TradingSignal, SignalDirection, SignalSource


class SignalAggregator:
    """
    Aggregates and scores signals from all strategies.
    """

    def __init__(
        self,
        symbol: str,
        min_confidence: int = 1,
        min_risk_reward: float = 1.0,
        use_solar_filter: bool = True,
    ):
        self.symbol           = symbol
        self.min_confidence   = min_confidence
        self.min_risk_reward  = min_risk_reward
        self.use_solar_filter = use_solar_filter
        self._solar_states: Dict[date, SolarTrendState] = {}

    def set_solar_states(self, states: Dict[date, Any]):
        """Load Solar Trend Indicator daily states for filtering."""
        self._solar_states = states

    def _get_solar_trend(self, d: date) -> str:
        """Get Solar Trend direction on a given date."""
        relevant = [sd for sd in self._solar_states if sd <= d]
        if not relevant:
            return "neutral"
        return self._solar_states[max(relevant)].trend

    def normalize_signal(
        self,
        raw_signal: Any,
        source: SignalSource,
        symbol: str,
    ) -> Optional[TradingSignal]:
        """
        Convert a raw strategy signal to a normalized TradingSignal.
        """
        try:
            direction = SignalDirection(raw_signal.direction)
            entry     = getattr(raw_signal, "entry_price", 0.0)
            stop      = getattr(raw_signal, "stop_price",  0.0)
            target    = getattr(raw_signal, "target_price",
                        getattr(raw_signal, "target_price_full", 0.0))
            sig_date  = getattr(raw_signal, "signal_date",
                        getattr(raw_signal, "entry_date", date.today()))
            target_half = getattr(raw_signal, "target_price_half", None)
            notes     = getattr(raw_signal, "signal_type", source.value)

            return TradingSignal(
                source=source,
                direction=direction,
                signal_date=sig_date,
                symbol=symbol,
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                target_price_half=target_half,
                raw_signal=raw_signal,
                notes=notes,
            )
        except Exception:
            return None

    def aggregate(
        self,
        signal_batches: Dict[SignalSource, List[Any]],
        start_date: date,
        end_date: date,
    ) -> List[TradingSignal]:
        """
        Aggregate signals from all sources, score confidence, filter, sort.

        signal_batches: dict mapping source → list of raw strategy signals.
        """
        all_signals: List[TradingSignal] = []

        for source, raw_signals in signal_batches.items():
            for raw in raw_signals:
                sig = self.normalize_signal(raw, source, self.symbol)
                if sig is None:
                    continue
                if not (start_date <= sig.signal_date <= end_date):
                    continue
                all_signals.append(sig)

        # Score confidence: count how many strategies agree on same day/direction
        confidence_map: Dict[tuple, int] = {}
        for sig in all_signals:
            key = (sig.signal_date, sig.direction)
            confidence_map[key] = confidence_map.get(key, 0) + 1

        for sig in all_signals:
            key = (sig.signal_date, sig.direction)
            sig.confidence = confidence_map[key]

        # Filter by Solar Trend direction
        filtered = []
        for sig in all_signals:
            if self.use_solar_filter and self._solar_states:
                solar = self._get_solar_trend(sig.signal_date)
                if solar == "bear" and sig.direction != SignalDirection.SHORT:
                    continue
                if solar == "bull" and sig.direction != SignalDirection.LONG:
                    continue
                # neutral: pass all

            if sig.confidence < self.min_confidence:
                continue

            if sig.risk_reward_ratio < self.min_risk_reward:
                continue

            filtered.append(sig)

        # Sort: by date, then confidence (desc), then risk-reward (desc)
        filtered.sort(key=lambda s: (s.signal_date, -s.confidence, -s.risk_reward_ratio))

        # Deduplicate: same direction within 1 day and same entry zone (±2%)
        deduplicated = []
        for sig in filtered:
            duplicate = False
            for existing in deduplicated:
                if (existing.direction == sig.direction and
                        abs((existing.signal_date - sig.signal_date).days) <= 1 and
                        abs(existing.entry_price - sig.entry_price) / max(existing.entry_price, 0.01) < 0.02):
                    # Keep the higher-confidence one
                    if sig.confidence > existing.confidence:
                        deduplicated.remove(existing)
                    else:
                        duplicate = True
                    break
            if not duplicate:
                deduplicated.append(sig)

        return deduplicated

    def print_signals(self, signals: List[TradingSignal]):
        """Print a formatted table of signals."""
        if not signals:
            print("No signals generated.")
            return

        print(f"\n{'='*90}")
        print(f"{'Date':<12} {'Dir':<6} {'Source':<30} {'Entry':>8} {'Stop':>8} "
              f"{'Target':>8} {'R:R':>6} {'Conf':>5}")
        print(f"{'='*90}")

        for sig in signals:
            print(
                f"{str(sig.signal_date):<12} "
                f"{sig.direction.value:<6} "
                f"{sig.source.value[:28]:<30} "
                f"{sig.entry_price:>8.2f} "
                f"{sig.stop_price:>8.2f} "
                f"{sig.target_price:>8.2f} "
                f"{sig.risk_reward_ratio:>6.1f} "
                f"{sig.confidence:>5}"
            )
        print(f"{'='*90}\n")
