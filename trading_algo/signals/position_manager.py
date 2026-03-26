"""
Position Manager.

Simulates trade execution and tracks open/closed positions.
Handles:
  - Entry (market open or specified price)
  - Stop loss
  - Target (single or split target for half/full exits)
  - 5-day max holding rule (for Mutable Factor)
  - Progressive stop updates
  - P&L calculation (using standard 50% stock margin as in the book)
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional, Dict
import pandas as pd

from .signal import TradingSignal, SignalDirection


MARGIN_RATE = 0.50   # 50% margin (standard as referenced in the book)


@dataclass
class Trade:
    """A completed round-trip trade."""
    signal: TradingSignal
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    direction: str
    exit_reason: str      # 'target', 'stop', 'time_limit', 'reversal_exit'
    half_exit_price: Optional[float] = None
    half_exit_date: Optional[date]   = None

    @property
    def gross_pnl(self) -> float:
        if self.direction == "short":
            return self.entry_price - self.exit_price
        else:
            return self.exit_price - self.entry_price

    @property
    def gross_pnl_half(self) -> float:
        if self.half_exit_price is None:
            return 0.0
        if self.direction == "short":
            return self.entry_price - self.half_exit_price
        else:
            return self.half_exit_price - self.entry_price

    @property
    def return_pct(self) -> float:
        """Return on investment (using 50% margin)."""
        if self.entry_price == 0:
            return 0.0
        # On margin: return = (pnl / entry_price) / margin_rate * 100
        return (self.gross_pnl / self.entry_price) / MARGIN_RATE * 100

    @property
    def is_winner(self) -> bool:
        return self.gross_pnl > 0

    def to_dict(self) -> Dict:
        return {
            "source":         self.signal.source.value,
            "direction":      self.direction,
            "entry_date":     str(self.entry_date),
            "entry_price":    round(self.entry_price, 4),
            "exit_date":      str(self.exit_date),
            "exit_price":     round(self.exit_price, 4),
            "exit_reason":    self.exit_reason,
            "gross_pnl":      round(self.gross_pnl, 4),
            "return_pct":     round(self.return_pct, 2),
            "is_winner":      self.is_winner,
        }


@dataclass
class Position:
    """An open position being tracked."""
    signal: TradingSignal
    entry_date: date
    entry_price: float
    current_stop: float
    direction: str
    is_open: bool = True
    half_exited: bool = False
    half_exit_price: Optional[float] = None
    half_exit_date:  Optional[date]  = None
    max_hold_date:   Optional[date]  = None   # for 5-day rule
    completed_trade: Optional[Trade] = None


class PositionManager:
    """
    Manages positions and executes simulated trades against price data.
    """

    def __init__(self, max_concurrent_positions: int = 3):
        self.max_concurrent_positions = max_concurrent_positions
        self.open_positions: List[Position] = []
        self.closed_trades:  List[Trade]    = []

    def _get_date(self, idx) -> date:
        return idx.date() if hasattr(idx, "date") else idx

    def process_signals(
        self,
        signals: List[TradingSignal],
        df: pd.DataFrame,
    ) -> List[Trade]:
        """
        Main loop: walk through price data, open positions on signal dates,
        manage stops, hit targets, apply time limits.

        df: daily OHLCV DataFrame.
        Returns list of all completed trades.
        """
        self.open_positions = []
        self.closed_trades  = []

        signal_map: Dict[date, List[TradingSignal]] = {}
        for sig in signals:
            if sig.signal_date not in signal_map:
                signal_map[sig.signal_date] = []
            signal_map[sig.signal_date].append(sig)

        for i, idx in enumerate(df.index):
            d = self._get_date(idx)
            row = df.iloc[i]

            # --- Manage open positions ---
            for pos in list(self.open_positions):
                if not pos.is_open:
                    continue

                # Check 5-day time limit
                if pos.max_hold_date and d > pos.max_hold_date:
                    exit_price = row["close"]
                    self._close_position(pos, d, exit_price, "time_limit")
                    continue

                if pos.direction == "short":
                    # Check stop hit (buy stop)
                    if row["high"] >= pos.current_stop:
                        self._close_position(pos, d, pos.current_stop, "stop")
                        continue
                    # Check target hit
                    target = pos.signal.target_price
                    target_half = pos.signal.target_price_half
                    if target_half and not pos.half_exited and row["low"] <= target_half:
                        pos.half_exited   = True
                        pos.half_exit_price = target_half
                        pos.half_exit_date  = d
                    if row["low"] <= target:
                        self._close_position(pos, d, target, "target")
                        continue

                else:  # long
                    if row["low"] <= pos.current_stop:
                        self._close_position(pos, d, pos.current_stop, "stop")
                        continue
                    target = pos.signal.target_price
                    target_half = pos.signal.target_price_half
                    if target_half and not pos.half_exited and row["high"] >= target_half:
                        pos.half_exited    = True
                        pos.half_exit_price = target_half
                        pos.half_exit_date  = d
                    if row["high"] >= target:
                        self._close_position(pos, d, target, "target")
                        continue

            # --- Open new positions ---
            if d in signal_map:
                for sig in signal_map[d]:
                    if len([p for p in self.open_positions if p.is_open]) >= self.max_concurrent_positions:
                        break

                    # Determine max hold date from signal if applicable
                    max_hold = getattr(sig.raw_signal, "max_exit_date", None)

                    pos = Position(
                        signal=sig,
                        entry_date=d,
                        entry_price=sig.entry_price,
                        current_stop=sig.stop_price,
                        direction=sig.direction.value,
                        max_hold_date=max_hold,
                    )
                    self.open_positions.append(pos)

        # Close any remaining open positions at last bar
        if len(df) > 0:
            last_row  = df.iloc[-1]
            last_date = self._get_date(df.index[-1])
            for pos in self.open_positions:
                if pos.is_open:
                    self._close_position(pos, last_date, last_row["close"], "end_of_backtest")

        return self.closed_trades

    def _close_position(self, pos: Position, exit_date: date, exit_price: float, reason: str):
        pos.is_open = False
        trade = Trade(
            signal=pos.signal,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            direction=pos.direction,
            exit_reason=reason,
            half_exit_price=pos.half_exit_price,
            half_exit_date=pos.half_exit_date,
        )
        pos.completed_trade = trade
        self.closed_trades.append(trade)

    def summary(self) -> Dict:
        """Return a performance summary dictionary."""
        trades = self.closed_trades
        if not trades:
            return {"total_trades": 0}

        winners = [t for t in trades if t.is_winner]
        losers  = [t for t in trades if not t.is_winner]

        total_return = sum(t.return_pct for t in trades)
        avg_win      = sum(t.return_pct for t in winners) / len(winners) if winners else 0
        avg_loss     = sum(t.return_pct for t in losers)  / len(losers)  if losers  else 0

        return {
            "total_trades":   len(trades),
            "winners":        len(winners),
            "losers":         len(losers),
            "win_rate_pct":   round(len(winners) / len(trades) * 100, 1),
            "total_return_pct": round(total_return, 2),
            "avg_win_pct":    round(avg_win, 2),
            "avg_loss_pct":   round(avg_loss, 2),
            "profit_factor":  round(abs(avg_win / avg_loss), 2) if avg_loss else float("inf"),
        }

    def print_summary(self):
        """Print a formatted performance summary."""
        s = self.summary()
        print("\n" + "="*50)
        print("PERFORMANCE SUMMARY")
        print("="*50)
        print(f"Total Trades:       {s.get('total_trades', 0)}")
        print(f"Winners:            {s.get('winners', 0)} ({s.get('win_rate_pct', 0):.1f}%)")
        print(f"Losers:             {s.get('losers', 0)}")
        print(f"Avg Win:           {s.get('avg_win_pct', 0):+.2f}%")
        print(f"Avg Loss:          {s.get('avg_loss_pct', 0):+.2f}%")
        print(f"Profit Factor:      {s.get('profit_factor', 0):.2f}x")
        print(f"Total Return:      {s.get('total_return_pct', 0):+.2f}%")
        print("="*50 + "\n")

    def print_trades(self):
        """Print a formatted trade log."""
        if not self.closed_trades:
            print("No completed trades.")
            return
        print(f"\n{'='*90}")
        print(f"{'Date In':<12} {'Date Out':<12} {'Dir':<6} {'Entry':>8} {'Exit':>8} "
              f"{'P&L%':>7} {'Reason':<15} {'Source'}")
        print(f"{'='*90}")
        for t in self.closed_trades:
            print(
                f"{str(t.entry_date):<12} "
                f"{str(t.exit_date):<12} "
                f"{t.direction:<6} "
                f"{t.entry_price:>8.2f} "
                f"{t.exit_price:>8.2f} "
                f"{t.return_pct:>+7.2f}% "
                f"{t.exit_reason:<15} "
                f"{t.signal.source.value[:20]}"
            )
        print(f"{'='*90}\n")
