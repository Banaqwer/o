"""Session calendar in the exchange time zone.

The engine treats the regular session (09:30-16:00 ET by default) as the
anchor window. Bars outside it are still consumed -- they feed the overnight
high/low structure -- but the session anchor, dispersion and profile are
reset at the open.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from ..config import SessionConfig


@dataclass(frozen=True)
class SessionStamp:
    session_date: date
    in_rth: bool
    is_open_bar: bool  # first RTH bar of the session


class SessionClock:
    """Classifies bar timestamps into sessions.

    A bar is attributed to the session date of its exchange-local calendar
    day; bars after the RTH close and before midnight belong to the *next*
    business day's overnight context, which is how futures Globex sessions
    are conventionally labelled.
    """

    def __init__(self, cfg: SessionConfig):
        self.cfg = cfg
        self.tz = ZoneInfo(cfg.tz)
        self._last_session: date | None = None
        self._open_seen_for: date | None = None

    def local(self, ts: datetime) -> datetime:
        return ts.astimezone(self.tz)

    def stamp(self, ts: datetime) -> SessionStamp:
        loc = self.local(ts)
        t = loc.time()
        d = loc.date()
        if t >= self.cfg.close:
            # Post-close prints belong to the next session's overnight.
            d = _next_weekday(d)
        elif loc.weekday() >= 5:
            d = _next_weekday(d)
        in_rth = self.cfg.open <= t < self.cfg.close and loc.weekday() < 5
        is_open_bar = in_rth and self._open_seen_for != d
        if is_open_bar:
            self._open_seen_for = d
        self._last_session = d
        return SessionStamp(session_date=d, in_rth=in_rth, is_open_bar=is_open_bar)

    def session_open(self, d: date) -> datetime:
        return datetime.combine(d, self.cfg.open, tzinfo=self.tz)


def _next_weekday(d: date) -> date:
    from datetime import timedelta

    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:
        nd += timedelta(days=1)
    return nd


def minutes_since_open(ts: datetime, cfg: SessionConfig) -> float:
    loc = ts.astimezone(ZoneInfo(cfg.tz))
    o = datetime.combine(loc.date(), cfg.open, tzinfo=loc.tzinfo)
    return (loc - o).total_seconds() / 60.0
