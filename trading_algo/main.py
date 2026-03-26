"""
Financial Astrology Trading Algorithm
Based on "Secrets of Financial Astrology" by Kenneth Min (27 Lessons)

Main runner: initializes all strategies, generates signals, aggregates them,
and runs a simulated backtest.

Usage:
    python main.py --symbol QQQ --start 2023-01-01 --end 2024-01-01

    Or for intermarket divergence (two symbols):
    python main.py --symbol QQQ --symbol2 SPY --start 2023-01-01 --end 2024-01-01

    Or for Sun-Neptune strategy (stock + sector ETF):
    python main.py --symbol INTC --sector SMH --start 2023-01-01 --end 2024-01-01
"""

import argparse
import sys
from datetime import date, datetime
from typing import Dict, List, Optional

import pandas as pd

# ── Allow running as: python -m trading_algo.main OR python trading_algo/main.py
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

# ── Strategy imports ─────────────────────────────────────────────────────────
from trading_algo.strategies.lunation_duad_quality      import LunationDuadQualityStrategy
from trading_algo.strategies.eighth_way                 import EighthWayStrategy
from trading_algo.strategies.solar_trend_indicator      import SolarTrendIndicator
from trading_algo.strategies.lunar_trend_confirmation   import LunarTrendConfirmation
from trading_algo.strategies.elemental_quality_connection import ElementalQualityConnectionStrategy
from trading_algo.strategies.golden_ratio               import GoldenRatioStrategy
from trading_algo.strategies.sun_neptune                import SunNeptuneStrategy
from trading_algo.strategies.mutable_factor             import MutableFactorStrategy
from trading_algo.strategies.lunar_phase_duad           import LunarPhaseDuadStrategy
from trading_algo.strategies.intermarket_divergence     import IntermarketDivergenceStrategy

# ── Signal infrastructure ────────────────────────────────────────────────────
from trading_algo.signals.signal          import SignalSource, SignalDirection
from trading_algo.signals.aggregator      import SignalAggregator
from trading_algo.signals.position_manager import PositionManager

# ── Utilities ────────────────────────────────────────────────────────────────
from trading_algo.utils.data_loader import load_price_data


# ─────────────────────────────────────────────────────────────────────────────
# Core runner
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(
    symbol: str,
    start_date: date,
    end_date: date,
    symbol2: Optional[str] = None,
    sector_symbol: Optional[str] = None,
    data_source: str = "yfinance",
    min_confidence: int = 1,
    min_rr: float = 1.5,
    use_solar_filter: bool = True,
    verbose: bool = True,
):
    """
    Run the full Financial Astrology trading backtest.

    Parameters
    ----------
    symbol         : Primary trading symbol (e.g., "QQQ")
    start_date     : Backtest start date
    end_date       : Backtest end date
    symbol2        : Second symbol for Intermarket Divergence (e.g., "SPY")
    sector_symbol  : Sector ETF for Sun-Neptune strategy (e.g., "SMH")
    data_source    : "yfinance" or "csv:<path>"
    min_confidence : Minimum number of strategies that must agree for a signal
    min_rr         : Minimum risk:reward ratio to accept a signal
    use_solar_filter : Only take trades in Solar Trend direction
    verbose        : Print progress messages
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f" Financial Astrology Trading Algorithm")
        print(f" Symbol: {symbol}  |  {start_date} → {end_date}")
        print(f"{'='*60}\n")

    # ── 1. Load price data ────────────────────────────────────────────────────
    if verbose:
        print("[1/5] Loading price data...")

    df_daily = load_price_data(symbol, start_date, end_date, interval="1d", source=data_source)
    if df_daily.empty:
        print(f"ERROR: No daily data available for {symbol}.")
        return

    # Normalize index to date only for daily data
    if hasattr(df_daily.index, 'tz') and df_daily.index.tz is not None:
        df_daily.index = df_daily.index.tz_localize(None)
    df_daily.index = pd.to_datetime(df_daily.index).normalize()

    if verbose:
        print(f"  Loaded {len(df_daily)} daily bars for {symbol}")

    df2 = None
    if symbol2:
        df2 = load_price_data(symbol2, start_date, end_date, interval="1d", source=data_source)
        if hasattr(df2.index, 'tz') and df2.index.tz is not None:
            df2.index = df2.index.tz_localize(None)
        df2.index = pd.to_datetime(df2.index).normalize()
        if verbose:
            print(f"  Loaded {len(df2)} daily bars for {symbol2}")

    df_sector = None
    if sector_symbol:
        df_sector = load_price_data(sector_symbol, start_date, end_date, interval="1d", source=data_source)
        if hasattr(df_sector.index, 'tz') and df_sector.index.tz is not None:
            df_sector.index = df_sector.index.tz_localize(None)
        df_sector.index = pd.to_datetime(df_sector.index).normalize()
        if verbose:
            print(f"  Loaded {len(df_sector)} daily bars for {sector_symbol}")

    # ── 2. Initialize Solar Trend Indicator ───────────────────────────────────
    if verbose:
        print("[2/5] Computing Solar Trend Indicator (3-Day Solar Time Windows)...")

    solar = SolarTrendIndicator()
    solar.initialize(start_date, end_date)
    solar_signals, solar_states = solar.compute_trend_states(df_daily, start_date, end_date)

    solar_trend_by_date = {d: state.trend for d, state in solar_states.items()}

    if verbose:
        print(f"  Solar trend signals: {len(solar_signals)}")

    # ── 3. Generate signals from all strategies ───────────────────────────────
    if verbose:
        print("[3/5] Running all strategies...")

    signal_batches: Dict[SignalSource, List] = {}

    # Strategy 1: Lunation Duad Quality
    try:
        s1 = LunationDuadQualityStrategy(symbol=symbol)
        sigs = s1.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.LUNATION_DUAD_QUALITY] = sigs
        if verbose:
            print(f"  Lunation Duad Quality:        {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  Lunation Duad Quality:        ERROR — {e}")
        signal_batches[SignalSource.LUNATION_DUAD_QUALITY] = []

    # Strategy 2: The 8th Way
    try:
        s2 = EighthWayStrategy()
        sigs = s2.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.EIGHTH_WAY] = sigs
        if verbose:
            print(f"  The 8th Way:                  {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  The 8th Way:                  ERROR — {e}")
        signal_batches[SignalSource.EIGHTH_WAY] = []

    # Strategy 3: Solar Trend (already computed above)
    signal_batches[SignalSource.SOLAR_TREND] = solar_signals

    # Strategy 5: Elemental & Quality Connection
    try:
        s5 = ElementalQualityConnectionStrategy()
        s5.initialize(start_date, end_date)
        sigs = s5.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.ELEMENTAL_QUALITY] = sigs
        if verbose:
            print(f"  Elemental/Quality Connection: {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  Elemental/Quality Connection: ERROR — {e}")
        signal_batches[SignalSource.ELEMENTAL_QUALITY] = []

    # Strategy 6: Golden Ratio
    try:
        s6 = GoldenRatioStrategy()
        sigs = s6.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.GOLDEN_RATIO] = sigs
        if verbose:
            print(f"  Golden Ratio:                 {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  Golden Ratio:                 ERROR — {e}")
        signal_batches[SignalSource.GOLDEN_RATIO] = []

    # Strategy 7: Sun-Neptune (requires sector ETF)
    if df_sector is not None:
        try:
            s7 = SunNeptuneStrategy(symbol, sector_symbol)
            s7.initialize(start_date, end_date)
            sigs = s7.generate_signals(df_daily, df_sector, start_date, end_date)
            signal_batches[SignalSource.SUN_NEPTUNE] = sigs
            if verbose:
                print(f"  Sun-Neptune:                  {len(sigs):>4} signals")
        except Exception as e:
            if verbose:
                print(f"  Sun-Neptune:                  ERROR — {e}")
            signal_batches[SignalSource.SUN_NEPTUNE] = []
    else:
        signal_batches[SignalSource.SUN_NEPTUNE] = []

    # Strategy 8: Mutable Factor
    try:
        s8 = MutableFactorStrategy()
        s8.initialize(start_date, end_date)
        sigs = s8.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.MUTABLE_FACTOR] = sigs
        if verbose:
            print(f"  Mutable Factor:               {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  Mutable Factor:               ERROR — {e}")
        signal_batches[SignalSource.MUTABLE_FACTOR] = []

    # Strategy 9: Lunar Phase Duad
    try:
        s9 = LunarPhaseDuadStrategy()
        s9.initialize(start_date, end_date)
        sigs = s9.generate_signals(df_daily, start_date, end_date)
        signal_batches[SignalSource.LUNAR_PHASE_DUAD] = sigs
        if verbose:
            print(f"  Lunar Phase Duad:             {len(sigs):>4} signals")
    except Exception as e:
        if verbose:
            print(f"  Lunar Phase Duad:             ERROR — {e}")
        signal_batches[SignalSource.LUNAR_PHASE_DUAD] = []

    # Strategy 10: Intermarket Divergence (requires second symbol)
    if df2 is not None:
        try:
            s10 = IntermarketDivergenceStrategy(symbol, symbol2)
            sigs = s10.generate_signals(df_daily, df2, start_date, end_date)
            signal_batches[SignalSource.INTERMARKET_DIVERGENCE] = sigs
            if verbose:
                print(f"  Intermarket Divergence:       {len(sigs):>4} signals")
        except Exception as e:
            if verbose:
                print(f"  Intermarket Divergence:       ERROR — {e}")
            signal_batches[SignalSource.INTERMARKET_DIVERGENCE] = []
    else:
        signal_batches[SignalSource.INTERMARKET_DIVERGENCE] = []

    # ── 4. Aggregate and filter signals ──────────────────────────────────────
    if verbose:
        print(f"\n[4/5] Aggregating signals (min_confidence={min_confidence}, "
              f"min_rr={min_rr}, solar_filter={use_solar_filter})...")

    aggregator = SignalAggregator(
        symbol=symbol,
        min_confidence=min_confidence,
        min_risk_reward=min_rr,
        use_solar_filter=use_solar_filter,
    )
    aggregator.set_solar_states(solar_states)

    final_signals = aggregator.aggregate(signal_batches, start_date, end_date)

    if verbose:
        print(f"  Total raw signals: {sum(len(v) for v in signal_batches.values())}")
        print(f"  Final filtered signals: {len(final_signals)}")
        aggregator.print_signals(final_signals)

    # ── 5. Run position manager / backtest ────────────────────────────────────
    if verbose:
        print("[5/5] Running backtest simulation...")

    pm = PositionManager(max_concurrent_positions=3)
    trades = pm.process_signals(final_signals, df_daily)

    if verbose:
        pm.print_trades()
        pm.print_summary()

    return {
        "signals":       final_signals,
        "trades":        trades,
        "summary":       pm.summary(),
        "solar_signals": solar_signals,
        "solar_states":  solar_states,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Financial Astrology Trading Algorithm (Kenneth Min)"
    )
    parser.add_argument("--symbol",   default="QQQ",  help="Primary trading symbol")
    parser.add_argument("--symbol2",  default=None,   help="Second symbol (divergence analysis)")
    parser.add_argument("--sector",   default=None,   help="Sector ETF (Sun-Neptune strategy)")
    parser.add_argument("--start",    default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end",      default="2024-01-01", help="End date (YYYY-MM-DD)")
    parser.add_argument("--source",   default="yfinance",   help="Data source")
    parser.add_argument("--min-conf", default=1, type=int,  help="Min strategy agreement count")
    parser.add_argument("--min-rr",   default=1.5, type=float, help="Min risk:reward ratio")
    parser.add_argument("--no-solar-filter", action="store_true",
                        help="Disable Solar Trend direction filter")
    parser.add_argument("--quiet",    action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end   = datetime.strptime(args.end,   "%Y-%m-%d").date()

    result = run_backtest(
        symbol=args.symbol,
        start_date=start,
        end_date=end,
        symbol2=args.symbol2,
        sector_symbol=args.sector,
        data_source=args.source,
        min_confidence=args.min_conf,
        min_rr=args.min_rr,
        use_solar_filter=not args.no_solar_filter,
        verbose=not args.quiet,
    )

    if result:
        summary = result["summary"]
        print(f"\nFinal result: {summary.get('total_trades',0)} trades, "
              f"{summary.get('win_rate_pct',0):.1f}% win rate, "
              f"{summary.get('total_return_pct',0):+.2f}% total return")


if __name__ == "__main__":
    main()
