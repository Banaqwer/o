"""Engine configuration.

Design rule, taken from the source material: *there are no fixed thresholds*.
Every quantity that touches price is expressed in one of three scale-free
units and is resolved against live data at run time:

* **sigma units** -- multiples of the live dispersion estimate ``rho``;
* **probabilities** -- quantiles of a rolling empirical distribution;
* **horizons** -- bar counts or half-lives.

Nothing in this file is denominated in index points or dollars, so the same
configuration serves NQ, ES, GC or SI without re-tuning. The configuration is
frozen: a running engine cannot be re-parameterised mid-session, which keeps
the ladder every client sees identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Tuple


@dataclass(frozen=True)
class SessionConfig:
    """Regular-trading-hours definition in the exchange time zone."""

    tz: str = "America/New_York"
    open: time = time(9, 30)
    close: time = time(16, 0)
    # Bars of the opening range used as a structural reference (count of bars).
    opening_range_bars: int = 15


@dataclass(frozen=True)
class DeviationConfig:
    """Statistical deviation analysis: price against the session anchor."""

    # Half-life (bars) of the EWMA return variance used as the floor of rho.
    vol_half_life: int = 30
    # Rolling sample of |z| from which the inner / outer band multipliers are
    # read as quantiles. Measured in bars (e.g. 20 sessions of 1-minute RTH
    # bars = 7800).
    quantile_window: int = 7800
    inner_quantile: float = 0.80
    outer_quantile: float = 0.95
    # Fallback multipliers used only until the quantile window has warmed up.
    warmup_inner: float = 1.25
    warmup_outer: float = 2.25
    # Minimum number of |z| samples before quantiles are trusted.
    min_samples: int = 300


@dataclass(frozen=True)
class OrderFlowConfig:
    """Bulk-volume classification and delta analytics."""

    # Half-life (bars) for the price-change scale used by BVC.
    bvc_half_life: int = 60
    # Half-life (bars) for standardising per-bar delta.
    delta_half_life: int = 120
    # Lookback (bars) for delta divergence at price extremes.
    divergence_window: int = 10
    # |delta z| beyond which a bar is treated as an absorption / imbalance
    # print whose extreme becomes a level proposal.
    absorption_quantile: float = 0.97
    # Rolling window of |delta z| used to resolve ``absorption_quantile``.
    absorption_window: int = 2000


@dataclass(frozen=True)
class LiquidityConfig:
    """Liquidity dynamics: price impact, volume relative to the clock, profile nodes."""

    # Half-life (bars) for the Amihud illiquidity EWMA.
    amihud_half_life: int = 120
    # Half-life for Kyle's lambda regression moments.
    kyle_half_life: int = 240
    # Number of past sessions in the time-of-day volume profile.
    tod_sessions: int = 20
    # Volume-profile bin width, in sigma units of rho.
    profile_bin_sigma: float = 0.10
    # Share of volume inside the value area.
    value_area: float = 0.70
    # A bin is a high-volume node when its volume exceeds this quantile of bins.
    hvn_quantile: float = 0.85


@dataclass(frozen=True)
class StructureConfig:
    """Price structure: swings, reference levels and profiles from prior sessions."""

    # Fractal half-width (bars) for swing confirmation.
    swing_width: int = 5
    # Maximum number of swings kept per side.
    max_swings: int = 12
    # Recency half-life (bars) for swing weights.
    swing_half_life: int = 390


@dataclass(frozen=True)
class RegimeConfig:
    """Regime detection and its mapping to ladder width and confidence."""

    fast_vol_half_life: int = 15
    slow_vol_half_life: int = 240
    efficiency_window: int = 30
    # Rolling window for standardising regime statistics.
    standardise_window: int = 2000
    # Sensitivities of the ladder width multiplier to the standardised
    # trend-efficiency, volatility-ratio and illiquidity statistics.
    beta_trend: float = 0.20
    beta_vol: float = 0.25
    beta_illiq: float = 0.10
    # Sensitivity to an exogenous daily context (standardised log-VIX from
    # the previous close), when a DailyContext is attached to the engine.
    beta_exogenous: float = 0.15
    width_bounds: Tuple[float, float] = (0.6, 2.5)


@dataclass(frozen=True)
class LadderConfig:
    """Holistic synthesis of the four-rung ladder."""

    # Window, in sigma units, within which proposals from the other
    # components may pull a deviation band toward confluence.
    snap_window_sigma: float = 0.35
    # Weight of the statistical-deviation anchor relative to one unit of
    # proposal weight.
    deviation_weight: float = 1.0
    # Component weights (neutral regime). Rescaled by regime.
    w_orderflow: float = 0.8
    w_liquidity: float = 0.9
    w_structure: float = 1.0
    # Minimum separation between rung I and rung II, in sigma units.
    min_rung_gap_sigma: float = 0.45
    # Minimum distance of rung I from price, in sigma units.
    min_inner_gap_sigma: float = 0.25
    # A published level is only moved when the recomputed value differs by
    # more than this many sigma, or the level has been breached.
    hysteresis_sigma: float = 0.20


@dataclass(frozen=True)
class ReversalConfig:
    """Level-test detection and entry evaluation."""

    # Touch tolerance around a level, in sigma units.
    touch_tolerance_sigma: float = 0.08
    # A close beyond the level by this many sigma breaks it.
    break_sigma: float = 0.30
    # Price must retreat this far (sigma) from a level before a re-test counts.
    rearm_sigma: float = 0.50
    # Entry score weights (logit space).
    s_confluence: float = 0.60
    s_overshoot: float = 0.80
    s_divergence: float = 0.90
    s_climax: float = 0.50
    s_regime: float = 0.70
    s_ladder: float = 0.60
    bias: float = -1.0
    # Entry threshold is the rolling quantile of past scores.
    entry_quantile: float = 0.60
    entry_window: int = 500
    # Fallback threshold during warm-up.
    warmup_entry_threshold: float = 0.50


@dataclass(frozen=True)
class ReactionConfig:
    """Post-event reaction measurement horizons (bars)."""

    horizons: Tuple[int, ...] = (5, 15, 30, 60)


@dataclass(frozen=True)
class EngineConfig:
    instrument: str = "NQ"
    tick_size: float = 0.25
    session: SessionConfig = field(default_factory=SessionConfig)
    deviation: DeviationConfig = field(default_factory=DeviationConfig)
    orderflow: OrderFlowConfig = field(default_factory=OrderFlowConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    ladder: LadderConfig = field(default_factory=LadderConfig)
    reversal: ReversalConfig = field(default_factory=ReversalConfig)
    reaction: ReactionConfig = field(default_factory=ReactionConfig)

    def __post_init__(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        d = self.deviation
        if not (0 < d.inner_quantile < d.outer_quantile < 1):
            raise ValueError("deviation quantiles must satisfy 0 < inner < outer < 1")
        lo, hi = self.regime.width_bounds
        if not (0 < lo < hi):
            raise ValueError("regime.width_bounds must be increasing and positive")
        if self.ladder.min_rung_gap_sigma <= 0 or self.ladder.min_inner_gap_sigma <= 0:
            raise ValueError("ladder gaps must be positive")
        if not self.reaction.horizons or min(self.reaction.horizons) <= 0:
            raise ValueError("reaction horizons must be positive bar counts")


# Instruments the source material names: index and metals futures.
INSTRUMENT_TICKS = {
    "NQ": 0.25,
    "ES": 0.25,
    "YM": 1.0,
    "RTY": 0.10,
    "GC": 0.10,
    "SI": 0.005,
    "HG": 0.0005,
    "PL": 0.10,
}


def config_for(instrument: str, **overrides) -> EngineConfig:
    """Build a configuration for a named futures contract."""

    sym = instrument.upper()
    if sym not in INSTRUMENT_TICKS:
        raise KeyError(f"unknown instrument {instrument!r}; known: {sorted(INSTRUMENT_TICKS)}")
    return EngineConfig(instrument=sym, tick_size=INSTRUMENT_TICKS[sym], **overrides)
