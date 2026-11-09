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
from .research.stats import session_summary, summarize, summarize_by
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
    from .research.context import DailyContext

    cfg = config_for(args.instrument)
    df = load_csv(args.csv)
    log = SessionLog(args.out) if args.out else None
    ctx = DailyContext.from_csv(args.context) if args.context else None
    res = replay(df, cfg, log=log, context=ctx)
    _print_dashboard(res, cfg.instrument, cfg.session.tz)
    _print_stats(res.events)
    if ctx is not None and not res.events.empty:
        by = summarize_by(res.events, "ctx_vix_z")
        if not by.empty:
            cols = [c for c in ["group", "horizon", "n", "edge_sigma", "edge_ci_lo", "edge_ci_hi", "t_stat", "p_reverted"] if c in by.columns]
            print("\nReaction by previous-close VIX regime")
            print(by[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    if args.out:
        print(f"\nsession log written under {Path(args.out).resolve()}")
    return 0


def cmd_fetch_lse(args: argparse.Namespace) -> int:
    from .data.sources.lse import LSEClient, LSEError

    try:
        if args.api == "vault" or (args.api == "auto" and _is_vault_key(args.key)):
            return _fetch_vault(args)
        client = LSEClient(api_key=args.key)
        if args.usage:
            import json

            print(json.dumps(client.usage(), indent=2))
            return 0
        if args.search:
            page = client.pairs(args.market, q=args.search, limit=25)
            for p in page.get("pairs", []):
                print(f"{p.get('symbol'):<16} {p.get('name', '')}  pair_id={p.get('pair_id')}")
            return 0
        if args.preview:
            print(client.preview(args.market, args.symbol, args.timeframe).to_string())
            return 0
        est = client.estimate(args.market, args.symbol, args.timeframe, args.start, args.end)
        print(f"estimate: {est.get('rows')} rows, ~{est.get('estimated_bytes', 0) / 1e6:.1f} MB, mode {est.get('mode')}")
        if est.get("download"):
            d = est["download"]
            print(f"download would be refused: {d.get('code')} {d.get('message')} {d.get('required_plan') or ''}")
            return 2
        df = client.candles(args.market, args.symbol, args.timeframe, args.start, args.end)
        df.to_csv(args.out, index_label="ts")
        print(f"{len(df)} bars -> {args.out}")
        return 0
    except LSEError as e:
        print(f"LSE refused: {e}")
        if e.required_plan:
            print(f"required plan: {e.required_plan}")
        return 1


def _is_vault_key(key) -> bool:
    """A Terminal/Databank key is unknown to LSE Data 3.0 but answers on /vault."""
    from .data.sources.lse import LSEClient, LSEError

    try:
        LSEClient(api_key=key).usage()
        return False
    except LSEError as e:
        return e.code in ("key-unknown",)


def _fetch_vault(args: argparse.Namespace) -> int:
    import json

    from .data.sources.lse import LSEError
    from .data.sources.lse_vault import VAULT_SYMBOLS, VaultClient

    try:
        client = VaultClient(api_key=args.key)
        if args.usage:
            print(json.dumps(client.usage(), indent=2))
            return 0
        if args.search:
            cat = client.catalog()
            hit = cat[cat["symbol"].str.contains(args.search, case=False) | cat["name"].str.contains(args.search, case=False)]
            for _, r in hit.head(40).iterrows():
                print(f"{r['symbol']:<16} {r['dataset']:<10} {str(r['name'])[:40]:<40} {str(r['first_tick'])[:10]}..{str(r['last_tick'])[:10]}")
            return 0
        symbol, dataset = args.symbol, args.market
        if args.symbol.upper() in VAULT_SYMBOLS:
            symbol, dataset = VAULT_SYMBOLS[args.symbol.upper()]
        if args.preview:
            cat = client.catalog()
            row = cat[cat["symbol"] == symbol]
            last = pd.Timestamp(row["last_tick"].iloc[0]) if not row.empty else pd.Timestamp.utcnow().tz_localize(None)
            rows = client.candles_page(symbol, dataset, args.timeframe, (last - pd.Timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), (last + pd.Timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"), limit=10)
            print(pd.DataFrame(rows).to_string())
            return 0
        if not (args.start and args.end):
            print("--start and --end are required")
            return 2

        def progress(n, last):
            print(f"  {n:>8} bars .. {last}", end="\r", flush=True)

        df = client.candles(symbol, dataset, args.timeframe, args.start, args.end, progress=progress)
        print()
        df.to_csv(args.out, index_label="ts")
        print(f"{len(df)} bars of {symbol} ({dataset}, {args.timeframe}) -> {args.out}")
        return 0
    except LSEError as e:
        print(f"LSE vault refused: {e}")
        return 1


def cmd_context(args: argparse.Namespace) -> int:
    from .data.sources.http import HttpClient
    from .research.context import DailyContext

    http = HttpClient(cache_dir=args.cache) if args.cache else HttpClient()
    ctx = DailyContext.fetch(start=args.start, index_id=args.index, http=http, with_factors=not args.no_factors)
    ctx.to_csv(args.out)
    f = ctx.frame.dropna(subset=["vix"])
    print(f"{len(f)} days {f.index[0].date()} .. {f.index[-1].date()} -> {args.out}")
    print(f.tail(5).to_string(float_format=lambda x: f"{x:.3f}"))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    log = SessionLog(args.log)
    ev = log.load_events(args.instrument, args.session)
    if ev.empty:
        print("no events in log")
        return 1
    _print_stats(ev)
    return 0


def cmd_protocol(args: argparse.Namespace) -> int:
    from .research import protocol

    argv = [args.phase, "--hist", args.hist, "--out", args.out, "--instruments", args.instruments]
    if args.context:
        argv += ["--context", args.context]
    return protocol.main(argv)


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
    r.add_argument("--context", default=None, help="daily context CSV from `atm-engine context`")
    r.set_defaults(fn=cmd_replay)

    f = sub.add_parser("fetch-lse", help="download candles from London Strategic Edge (LSE Data 3.0; key in LSE_API_KEY)")
    f.add_argument("--market", default="futures", help="v3: futures | indices | commodities | us_stocks | cme (paid); vault: the dataset, e.g. futures | commodity | index")
    f.add_argument("--symbol", default="SP500", help="v3 symbol (SP500), vault symbol (NASDAQ100.F) or an engine instrument (NQ, GC) mapped to the vault symbol")
    f.add_argument("--timeframe", default="1m")
    f.add_argument("--start", default=None, help="YYYY-MM-DD")
    f.add_argument("--end", default=None, help="YYYY-MM-DD")
    f.add_argument("--out", default="bars.csv")
    f.add_argument("--key", default=None, help="API key (else LSE_API_KEY)")
    f.add_argument("--usage", action="store_true", help="print the key's plan and allowances")
    f.add_argument("--search", default=None, help="search instruments in the market")
    f.add_argument("--preview", action="store_true", help="print the newest ten candles")
    f.add_argument("--api", choices=["auto", "v3", "vault"], default="auto", help="LSE Data 3.0 (/v3) or the Terminal's /vault calls; auto probes the key")
    f.set_defaults(fn=cmd_fetch_lse)

    c = sub.add_parser("context", help="build the daily FRED + French context CSV")
    c.add_argument("--start", default="2010-01-01")
    c.add_argument("--index", default="NASDAQ100", help="FRED index series: NASDAQ100 | SP500 | DJIA")
    c.add_argument("--out", default="context.csv")
    c.add_argument("--cache", default=None, help="directory to cache downloads")
    c.add_argument("--no-factors", action="store_true", help="skip the French library")
    c.set_defaults(fn=cmd_context)

    s = sub.add_parser("stats", help="summarise a session log")
    s.add_argument("log")
    s.add_argument("--instrument", default="NQ")
    s.add_argument("--session", default=None)
    s.set_defaults(fn=cmd_stats)
    pr = sub.add_parser("protocol", help="run a phase of the pre-registered research protocol (docs/protocol.md)")
    pr.add_argument("phase", choices=["dev", "val", "holdout"])
    pr.add_argument("--hist", required=True, help="directory of <INST>_<YEAR>.csv one-minute files")
    pr.add_argument("--out", required=True, help="directory for tables, fitted weights and chosen cell")
    pr.add_argument("--context", default=None)
    pr.add_argument("--instruments", default="NQ,ES,GC")
    pr.set_defaults(fn=cmd_protocol)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
