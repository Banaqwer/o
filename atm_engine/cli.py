"""Command line: demo on synthetic data, replay a CSV, summarise a log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from .config import config_for
from .data.schema import load_csv
from .data.synthetic import SyntheticSpec, generate
from .engine.session_log import SessionLog
from .research.backtest import replay
from .research.stats import session_summary, summarize
from .types import RUNG_ORDER


def _print_dashboard(result, instrument: str, tz: str) -> None:
    lad = result.ladders
    ev = result.events
    if lad.empty:
        print("no ladder published (no regular-session bars?)")
        return
    last = lad.iloc[-1]
    ts = lad.index[-1].tz_convert(ZoneInfo(tz))
    print(f"\n{instrument}  {ts:%Y-%m-%d %H:%M:%S} ET   (anchor {last['anchor']:,.2f}  rho {last['rho']:,.2f}  width x{last['width_multiplier']:.2f})")
    for r in RUNG_ORDER:
        key = r.name.lower()
        print(f"  {r.value:<5} {last[key]:>12,.2f}   confluence {last[key + '_confluence']:.2f}  {last[key + '_sources']}")
    if not ev.empty:
        e = ev.iloc[-1]
        ets = e["ts"].tz_convert(ZoneInfo(tz))
        print(f"\n  Last event  {e['rung']}\n  Direction   {e['direction']}\n  Time (ET)   {ets:%H:%M:%S}\n  Price       {e['level_price']:,.2f}\n  Score       {e['score']:.2f}  entry={bool(e['is_entry'])}")


def cmd_demo(args: argparse.Namespace) -> int:
    cfg = config_for(args.instrument)
    spec = SyntheticSpec(sessions=args.sessions, seed=args.seed)
    df = generate(spec, cfg.session)
    print("Synthetic data. Not algorithm output on real markets or a record of trading.")
    res = replay(df, cfg)
    _print_dashboard(res, cfg.instrument, cfg.session.tz)
    _print_stats(res.events)
    return 0


def _print_stats(events: pd.DataFrame) -> None:
    if events.empty:
        print("\nno events")
        return
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print("\nSessions")
    print(session_summary(events).to_string())
    s = summarize(events)
    cols = [c for c in ["group", "horizon", "n", "mfe_sigma", "mae_sigma", "edge_sigma", "edge_ci_lo", "edge_ci_hi", "t_stat", "p_reverted"] if c in s.columns]
    print("\nReaction statistics (sigma units)")
    print(s[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


def cmd_replay(args: argparse.Namespace) -> int:
    cfg = config_for(args.instrument)
    df = load_csv(args.csv)
    log = SessionLog(args.out) if args.out else None
    res = replay(df, cfg, log=log)
    _print_dashboard(res, cfg.instrument, cfg.session.tz)
    _print_stats(res.events)
    if args.out:
        print(f"\nsession log written under {Path(args.out).resolve()}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    log = SessionLog(args.log)
    ev = log.load_events(args.instrument, args.session)
    if ev.empty:
        print("no events in log")
        return 1
    _print_stats(ev)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atm-engine", description="Adaptive mean-reversion ladder and reversal engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="replay seeded synthetic bars")
    d.add_argument("--instrument", default="NQ")
    d.add_argument("--sessions", type=int, default=10)
    d.add_argument("--seed", type=int, default=20241017)
    d.set_defaults(fn=cmd_demo)

    r = sub.add_parser("replay", help="replay a CSV of bars (ts,open,high,low,close,volume[,buy_volume,sell_volume])")
    r.add_argument("csv")
    r.add_argument("--instrument", default="NQ")
    r.add_argument("--out", default=None, help="directory for the per-session log")
    r.set_defaults(fn=cmd_replay)

    s = sub.add_parser("stats", help="summarise a session log")
    s.add_argument("log")
    s.add_argument("--instrument", default="NQ")
    s.add_argument("--session", default=None)
    s.set_defaults(fn=cmd_stats)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
