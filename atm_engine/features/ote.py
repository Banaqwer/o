"""Optimal Trade Entry (OTE): retracement zones inside an impulsive leg.

Extracted from the "OTE Blueprint" lesson (slides and charts) and the public
ICT material it follows:

* a *leg* is a clean, impulsive swing from a confirmed swing low to a
  confirmed swing high (bullish) or the reverse;
* a Fibonacci retracement is drawn from the leg's origin (1.0) to its
  extreme (0.0) with levels 0.79, 0.705, 0.62, 0.5, 0.25;
* the lesson trades two levels, 0.705 and 0.5 (fair value and equilibrium);
  the 0.62-0.79 band of the public ICT material is kept as ``zone_lo`` /
  ``zone_hi`` for the ``close_inside`` confirmation only;
* checklist: confirm the higher-timeframe bias (a break-of-structure state
  on four-hour bars), mark a proper zone (no chop), wait for the tap, wait
  for consolidation *at the level* that is small next to the leg, enter on
  the break of that box with displacement, stop beyond the box or the 1.0
  level, target the 0.0 level or its expansion, or trail after expansion.

Everything here is scale-free (displacement in units of ``rho``) and
incremental: swings are confirmed with a lag, zones become active only
after confirmation, and a signal is printed only on a bar after the retest.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from ..types import Bar, Direction

FIB_LEVELS: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.62, 0.705, 0.79, 1.0)


@dataclass(frozen=True)
class OTEConfig:
    leg_minutes: int = 5  # bar size on which legs are identified
    bias_minutes: int = 240  # bar size for the higher-timeframe bias ("the four hour timeframe")
    swing_width: int = 3  # fractal half-width on the leg timeframe
    bias_swing_width: int = 3
    # "bos": break-of-structure state, +1 after a close above the last confirmed swing high, -1 after a close
    # below the last confirmed swing low, held until the opposite break ("took out all these highs");
    # "hh_hl": the earlier higher-highs-and-higher-lows reading, which can be undefined (0)
    bias_mode: str = "bos"
    min_displacement_sigma: float = 3.0  # leg range in units of rho
    max_displacement_sigma: float = 30.0  # "such a huge range": prefer a lower-timeframe leg instead
    max_chop: float = 0.5  # deepest counter-move inside the leg, as a share of the leg
    zone_lo: float = 0.62
    zone_hi: float = 0.79
    sweet: float = 0.705
    equilibrium: float = 0.5
    invalidation: float = 1.0  # a close through this retracement kills the zone
    invalidate_on_extension: bool = True  # after the tap, a bar trading beyond the 0.0 level kills the zone (the move resumed without us)
    stop_buffer_sigma: float = 0.25  # stop beyond the 1.0 level (or beyond the consolidation range)
    target: str = "extreme"  # "extreme" (0.0 level) | "expansion" (-0.5) | "symmetrical" (-1.0)
    touch_level: float = 0.5  # the zone is "tapped" once price retraces at least this far (0.5 or 0.705 in the lesson)
    confirmation: str = "range_break"  # "none" | "close_inside" | "close_back" | "range_break" | "range_or_bos"
    # range_break: the box is the last ``consolidation_bars`` one-minute bars before the trigger bar. It must
    # be small (range at most ``consolidation_max_sigma`` rho and ``consolidation_max_leg_fraction`` of the
    # leg), sit at the tapped level (reach within ``consolidation_band`` of the leg of it) and be sideways
    # (net drift across it at most ``consolidation_max_drift`` of its range). The trigger is a bar closing
    # beyond the box in the leg's direction with a body of at least ``breakout_min_sigma`` rho.
    consolidation_bars: int = 15
    consolidation_max_sigma: float = 1.5
    consolidation_max_leg_fraction: float = 0.20  # the lesson's five-minute example boxes about 0.18 of its leg
    consolidation_band: float = 0.10
    consolidation_max_drift: float = 0.5
    breakout_min_sigma: float = 0.5
    # break of structure: after the tap, a bar with a large body closing beyond the highest high
    # (lowest low) of the last ``bos_lookback`` bars substitutes for the consolidation ("such a huge candle")
    bos_lookback: int = 15
    bos_min_sigma: float = 1.0
    stop_at: str = "range"  # "range": beyond the consolidation range | "origin": beyond the 1.0 level
    require_bias: bool = True
    max_zone_age_bars: int = 390  # one session
    session_tz: str = "America/New_York"


@dataclass
class Swing:
    price: float
    index: int  # index of the aggregated bar
    ts: datetime
    is_high: bool


@dataclass
class Leg:
    direction: Direction  # BUYING for a bullish leg (we buy the retrace), SELLING for bearish
    origin: float  # 1.0 level
    extreme: float  # 0.0 level
    origin_ts: datetime
    extreme_ts: datetime
    confirmed_at: int  # 1-minute bar index when the leg became known
    displacement_sigma: float
    chop: float
    touched: bool = False
    deepest: float = 0.0  # deepest retracement fraction reached since confirmation
    signalled: bool = False
    inside_count: int = 0
    range_hi: float = float("nan")  # the box at the trigger (range_break only)
    range_lo: float = float("nan")
    recent_opens: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    recent_highs: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    recent_lows: Deque[float] = field(default_factory=lambda: deque(maxlen=64))
    recent_closes: Deque[float] = field(default_factory=lambda: deque(maxlen=64))

    def push(self, bar: Bar) -> None:
        self.recent_opens.append(bar.open)
        self.recent_highs.append(bar.high)
        self.recent_lows.append(bar.low)
        self.recent_closes.append(bar.close)

    def level(self, f: float) -> float:
        return self.extreme + (self.origin - self.extreme) * f

    def retrace_fraction(self, price: float) -> float:
        span = self.origin - self.extreme
        return (price - self.extreme) / span if span != 0 else 0.0


@dataclass(frozen=True)
class OTESignal:
    ts: datetime
    direction: Direction
    entry_reference: float  # the sweet-spot price
    stop_price: float
    target_price: float
    origin: float
    extreme: float
    displacement_sigma: float
    chop: float
    deepest: float
    bias: int
    rho: float
    minutes_since_open: float
    bars_since_leg: int
    trigger: str = ""
    range_hi: float = float("nan")  # consolidation range at the trigger (range_break only)
    range_lo: float = float("nan")
    bias_60: int = 0  # diagnostic: the same break-of-structure state on 60-minute bars
    mom24: int = 0  # diagnostic: sign of the close-to-close change over the last 1440 one-minute bars
    reward_risk: float = float("nan")  # |target - close| / |close - stop| at the signal bar


class _Aggregator:
    """Builds fixed-minute bars from 1-minute bars on exchange-local clock boundaries."""

    def __init__(self, minutes: int, tz: str):
        self.minutes = minutes
        self.tz = ZoneInfo(tz)
        self._key: Optional[int] = None
        self._o = self._h = self._l = self._c = 0.0
        self._ts: Optional[datetime] = None

    def update(self, bar: Bar) -> Optional[Bar]:
        loc = bar.ts.astimezone(self.tz)
        key = (loc.year * 10000 + loc.month * 100 + loc.day) * 10000 + (loc.hour * 60 + loc.minute) // self.minutes
        done: Optional[Bar] = None
        if self._key is not None and key != self._key:
            done = Bar(self._ts, self._o, self._h, self._l, self._c, 0.0)
        if self._key is None or key != self._key:
            self._key, self._ts = key, bar.ts
            self._o, self._h, self._l, self._c = bar.open, bar.high, bar.low, bar.close
        else:
            self._h = max(self._h, bar.high)
            self._l = min(self._l, bar.low)
            self._c = bar.close
        return done


class _SwingDetector:
    def __init__(self, width: int):
        self.w = width
        self.buf: Deque[Tuple[int, Bar]] = deque(maxlen=2 * width + 1)
        self.n = 0
        self.highs: List[Swing] = []
        self.lows: List[Swing] = []
        self._pending_low_min: Dict[int, float] = {}

    def update(self, bar: Bar) -> List[Swing]:
        self.n += 1
        self.buf.append((self.n, bar))
        out: List[Swing] = []
        if len(self.buf) < 2 * self.w + 1:
            return out
        mid_i, mid = self.buf[self.w]
        highs = [b.high for _, b in self.buf]
        lows = [b.low for _, b in self.buf]
        if mid.high >= max(highs) and highs.count(mid.high) == 1:
            s = Swing(mid.high, mid_i, mid.ts, True)
            self.highs.append(s)
            out.append(s)
        if mid.low <= min(lows) and lows.count(mid.low) == 1:
            s = Swing(mid.low, mid_i, mid.ts, False)
            self.lows.append(s)
            out.append(s)
        if len(self.highs) > 64:
            del self.highs[:-64]
        if len(self.lows) > 64:
            del self.lows[:-64]
        return out


class OTEState:
    def __init__(self, cfg: OTEConfig):
        self.cfg = cfg
        self.tz = ZoneInfo(cfg.session_tz)
        self._agg = _Aggregator(cfg.leg_minutes, cfg.session_tz)
        self._bias_agg = _Aggregator(cfg.bias_minutes, cfg.session_tz)
        self._bias60_agg = _Aggregator(60, cfg.session_tz)
        self._swings = _SwingDetector(cfg.swing_width)
        self._bias_swings = _SwingDetector(cfg.bias_swing_width)
        self._bias60_swings = _SwingDetector(cfg.bias_swing_width)
        self._closes: Deque[float] = deque(maxlen=1440)
        self._leg_bars: List[Bar] = []  # aggregated bars, to measure chop inside a leg
        self._i = 0
        self.legs: Dict[Direction, Optional[Leg]] = {Direction.BUYING: None, Direction.SELLING: None}
        self.bias = 0
        self.bias_60 = 0
        self.mom24 = 0

    # ------------------------------------------------------------------ bias
    def _structure_state(self, det: _SwingDetector, done: Bar, prev: int) -> int:
        """Break-of-structure state: +1 after a close above the last confirmed swing high, -1 after a close
        below the last confirmed swing low, otherwise unchanged. The confirming swing is never the bar itself."""
        hs, ls = det.highs, det.lows
        if hs and done.close > hs[-1].price:
            return 1
        if ls and done.close < ls[-1].price:
            return -1
        return prev

    def _update_bias(self, bar: Bar) -> None:
        self._closes.append(bar.close)
        if len(self._closes) == self._closes.maxlen:
            d = bar.close - self._closes[0]
            self.mom24 = 1 if d > 0 else -1 if d < 0 else self.mom24
        d60 = self._bias60_agg.update(bar)
        if d60 is not None:
            self.bias_60 = self._structure_state(self._bias60_swings, d60, self.bias_60)
            self._bias60_swings.update(d60)
        done = self._bias_agg.update(bar)
        if done is None:
            return
        if self.cfg.bias_mode == "bos":
            self.bias = self._structure_state(self._bias_swings, done, self.bias)
            self._bias_swings.update(done)
            return
        self._bias_swings.update(done)
        hs, ls = self._bias_swings.highs, self._bias_swings.lows
        if len(hs) >= 2 and len(ls) >= 2:
            hh = hs[-1].price > hs[-2].price
            hl = ls[-1].price > ls[-2].price
            lh = hs[-1].price < hs[-2].price
            ll = ls[-1].price < ls[-2].price
            self.bias = 1 if (hh and hl) else -1 if (lh and ll) else 0

    # ------------------------------------------------------------------ legs
    def _consider_legs(self, new_swings: List[Swing], rho: float, ts: datetime) -> None:
        c = self.cfg
        for s in new_swings:
            if s.is_high:
                lows = [l for l in self._swings.lows if l.index < s.index]
                if not lows:
                    continue
                origin = max(lows, key=lambda l: l.index)
                # the leg runs from the last swing low before this high; prefer the lowest low after the previous high
                prev_highs = [h for h in self._swings.highs if h.index < s.index and h is not s]
                if prev_highs:
                    ph = max(prev_highs, key=lambda h: h.index)
                    cand = [l for l in lows if l.index > ph.index]
                    if cand:
                        origin = min(cand, key=lambda l: l.price)
                self._make_leg(Direction.BUYING, origin, s, rho, ts)
            else:
                highs = [h for h in self._swings.highs if h.index < s.index]
                if not highs:
                    continue
                origin = max(highs, key=lambda h: h.index)
                prev_lows = [l for l in self._swings.lows if l.index < s.index and l is not s]
                if prev_lows:
                    pl = max(prev_lows, key=lambda l: l.index)
                    cand = [h for h in highs if h.index > pl.index]
                    if cand:
                        origin = max(cand, key=lambda h: h.price)
                self._make_leg(Direction.SELLING, origin, s, rho, ts)

    def _make_leg(self, direction: Direction, origin: Swing, extreme: Swing, rho: float, ts: datetime) -> None:
        c = self.cfg
        span = abs(extreme.price - origin.price)
        if rho <= 0 or span / rho < c.min_displacement_sigma or span / rho > c.max_displacement_sigma:
            return
        # chop: deepest counter-move inside the leg on the aggregated bars
        seg = [b for idx, b in self._indexed_leg_bars() if origin.index <= idx <= extreme.index]
        chop = 0.0
        if seg:
            if direction is Direction.BUYING:
                run_max = seg[0].high
                for b in seg:
                    run_max = max(run_max, b.high)
                    chop = max(chop, (run_max - b.low) / span)
            else:
                run_min = seg[0].low
                for b in seg:
                    run_min = min(run_min, b.low)
                    chop = max(chop, (b.high - run_min) / span)
        if chop > c.max_chop:
            return
        self.legs[direction] = Leg(direction, origin.price, extreme.price, origin.ts, extreme.ts, self._i, span / rho, chop)

    def _indexed_leg_bars(self):
        n = self._swings.n
        start = n - len(self._leg_bars) + 1
        return [(start + k, b) for k, b in enumerate(self._leg_bars)]

    # ---------------------------------------------------------------- update
    def update(self, bar: Bar, rho: float, minutes_since_open: float) -> List[OTESignal]:
        self._i += 1
        self._update_bias(bar)
        done = self._agg.update(bar)
        if done is not None:
            self._leg_bars.append(done)
            if len(self._leg_bars) > 400:
                del self._leg_bars[:-400]
            self._consider_legs(self._swings.update(done), rho, bar.ts)

        signals: List[OTESignal] = []
        c = self.cfg
        for direction, leg in list(self.legs.items()):
            if leg is None:
                continue
            if self._i - leg.confirmed_at > c.max_zone_age_bars:
                self.legs[direction] = None
                continue
            bull = direction is Direction.BUYING
            # extension of the leg before the retest: redraw the 0.0 level
            if not leg.touched:
                if bull and bar.high > leg.extreme:
                    leg.extreme = bar.high
                elif not bull and bar.low < leg.extreme:
                    leg.extreme = bar.low
            # invalidation: close through the origin
            inval = leg.level(c.invalidation)
            if (bull and bar.close < inval) or (not bull and bar.close > inval):
                self.legs[direction] = None
                continue
            # retest depth on this bar
            probe = bar.low if bull else bar.high
            frac = leg.retrace_fraction(probe)
            if frac >= c.touch_level:
                leg.touched = True
            leg.deepest = max(leg.deepest, frac)
            if not leg.touched or leg.signalled:
                leg.push(bar)
                continue
            # the move resumed past the 0.0 level without a trigger: the range is "already broken out of"
            if c.invalidate_on_extension and ((bull and bar.high > leg.extreme) or (not bull and bar.low < leg.extreme)):
                self.legs[direction] = None
                continue
            close_frac = leg.retrace_fraction(bar.close)
            inside = c.zone_lo <= close_frac <= c.zone_hi
            trigger = c.confirmation
            stop_ref: Optional[float] = None
            if c.confirmation == "none":
                ok = True
            elif c.confirmation == "close_inside":
                leg.inside_count += 1 if inside else 0
                ok = leg.inside_count >= 1
            elif c.confirmation == "close_back":  # price closed back on the extreme side of the zone after touching it
                ok = close_frac < c.zone_lo
            else:  # range_break / range_or_bos
                ok = False
                body = abs(bar.close - bar.open)
                span = abs(leg.origin - leg.extreme)
                level_t = leg.level(c.touch_level)
                tol = c.consolidation_band * span
                m = c.consolidation_bars
                if len(leg.recent_highs) >= m:
                    hs, ls = list(leg.recent_highs)[-m:], list(leg.recent_lows)[-m:]
                    box_hi, box_lo = max(hs), min(ls)
                    rng = box_hi - box_lo
                    cap = min(c.consolidation_max_sigma * rho, c.consolidation_max_leg_fraction * span)
                    at_level = (box_lo - tol) <= level_t <= (box_hi + tol)
                    drift = abs(leg.recent_closes[-1] - list(leg.recent_opens)[-m])
                    sideways = drift <= c.consolidation_max_drift * rng
                    if rng <= cap and at_level and sideways:
                        broke = (bar.close > box_hi) if bull else (bar.close < box_lo)
                        if broke and body >= c.breakout_min_sigma * rho:
                            ok = True
                            stop_ref = box_lo if bull else box_hi
                            leg.range_hi, leg.range_lo = box_hi, box_lo
                if not ok and c.confirmation == "range_or_bos" and len(leg.recent_highs) >= c.bos_lookback:
                    look_h = list(leg.recent_highs)[-c.bos_lookback:]
                    look_l = list(leg.recent_lows)[-c.bos_lookback:]
                    bos = (bar.close > max(look_h)) if bull else (bar.close < min(look_l))
                    if bos and body >= c.bos_min_sigma * rho:
                        ok = True
                        trigger = "bos"
                        stop_ref = min(look_l + [bar.low]) if bull else max(look_h + [bar.high])
                leg.push(bar)
            if not ok:
                continue
            if c.require_bias and self.bias != (1 if bull else -1):
                leg.signalled = True  # one chance per zone; no bias, no trade
                continue
            leg.signalled = True
            if c.stop_at == "range" and stop_ref is not None:
                stop = stop_ref - (c.stop_buffer_sigma * rho if bull else -c.stop_buffer_sigma * rho)
            else:
                stop = leg.level(c.invalidation) - (c.stop_buffer_sigma * rho if bull else -c.stop_buffer_sigma * rho)
            tgt_f = {"extreme": 0.0, "expansion": -0.5, "symmetrical": -1.0}[c.target]
            target = leg.level(tgt_f)
            risk = abs(bar.close - stop)
            rr = abs(target - bar.close) / risk if risk > 0 else float("nan")
            signals.append(
                OTESignal(
                    ts=bar.ts,
                    direction=direction,
                    entry_reference=leg.level(c.sweet),
                    stop_price=stop,
                    target_price=target,
                    trigger=trigger,
                    range_hi=(leg.range_hi if trigger == "range_break" else (stop_ref if (trigger == "bos" and not bull) else float("nan"))),
                    range_lo=(leg.range_lo if trigger == "range_break" else (stop_ref if (trigger == "bos" and bull) else float("nan"))),
                    origin=leg.origin,
                    extreme=leg.extreme,
                    displacement_sigma=leg.displacement_sigma,
                    chop=leg.chop,
                    deepest=leg.deepest,
                    bias=self.bias,
                    bias_60=self.bias_60,
                    mom24=self.mom24,
                    reward_risk=rr,
                    rho=rho,
                    minutes_since_open=minutes_since_open,
                    bars_since_leg=self._i - leg.confirmed_at,
                )
            )
        return signals
