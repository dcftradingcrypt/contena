from __future__ import annotations

from pathlib import Path

from .config import load_config
from .utils import max_drawdown_pct, mean, read_ohlcv_csv, rolling_mean, stddev, write_csv, write_json


def build_signals(bars: list[dict[str, float | str]], fast_window: int, slow_window: int) -> list[int]:
    if fast_window >= slow_window:
        raise ValueError("fast_window must be smaller than slow_window")
    closes = [float(bar["close"]) for bar in bars]
    fast_series = rolling_mean(closes, fast_window)
    slow_series = rolling_mean(closes, slow_window)
    signals: list[int] = []
    for fast_value, slow_value in zip(fast_series, slow_series):
        if fast_value is None or slow_value is None:
            signals.append(0)
        else:
            signals.append(1 if fast_value > slow_value else 0)
    return signals


def simulate_backtest(
    bars: list[dict[str, float | str]],
    fast_window: int,
    slow_window: int,
    initial_cash: float,
    fee_bps: float,
    slippage_bps: float = 0.0,
) -> tuple[dict, list[dict], list[dict]]:
    signals = build_signals(bars, fast_window, slow_window)
    cash = initial_cash
    units = 0.0
    trades: list[dict] = []
    equity_rows: list[dict] = []
    closed_trade_returns: list[float] = []
    open_trade_cost = 0.0
    entry_fill_price = 0.0

    def execute_buy(index: int, reason: str) -> None:
        nonlocal cash, units, open_trade_cost, entry_fill_price
        close_price = float(bars[index]["close"])
        fill_price = close_price * (1.0 + slippage_bps / 10_000.0)
        quantity = cash / (fill_price * (1.0 + fee_bps / 10_000.0))
        gross = quantity * fill_price
        fee = gross * fee_bps / 10_000.0
        cash -= gross + fee
        units = quantity
        open_trade_cost = gross + fee
        entry_fill_price = fill_price
        trades.append(
            {
                "timestamp": bars[index]["timestamp"],
                "side": "buy",
                "price": round(fill_price, 6),
                "quantity": round(quantity, 8),
                "fee": round(fee, 6),
                "reason": reason,
                "cash_after": round(cash, 6),
            }
        )

    def execute_sell(index: int, reason: str) -> None:
        nonlocal cash, units, open_trade_cost, entry_fill_price
        close_price = float(bars[index]["close"])
        fill_price = close_price * (1.0 - slippage_bps / 10_000.0)
        gross = units * fill_price
        fee = gross * fee_bps / 10_000.0
        cash += gross - fee
        if open_trade_cost > 0:
            closed_trade_returns.append((gross - fee - open_trade_cost) / open_trade_cost)
        trades.append(
            {
                "timestamp": bars[index]["timestamp"],
                "side": "sell",
                "price": round(fill_price, 6),
                "quantity": round(units, 8),
                "fee": round(fee, 6),
                "reason": reason,
                "cash_after": round(cash, 6),
                "entry_price": round(entry_fill_price, 6),
            }
        )
        units = 0.0
        open_trade_cost = 0.0
        entry_fill_price = 0.0

    for index, bar in enumerate(bars):
        signal = signals[index]
        position = 1 if units > 0 else 0
        if position == 0 and signal == 1:
            execute_buy(index, "sma_cross_up")
        elif position == 1 and signal == 0:
            execute_sell(index, "sma_cross_down")

        close_price = float(bar["close"])
        equity = cash + units * close_price
        equity_rows.append(
            {
                "timestamp": bar["timestamp"],
                "close": round(close_price, 6),
                "signal": signal,
                "equity": round(equity, 6),
                "position_units": round(units, 8),
            }
        )

    if units > 0:
        execute_sell(len(bars) - 1, "finalize")
        final_close = float(bars[-1]["close"])
        final_equity = cash + units * final_close
        equity_rows[-1]["equity"] = round(final_equity, 6)
        equity_rows[-1]["position_units"] = round(units, 8)

    equity_curve = [float(row["equity"]) for row in equity_rows]
    final_equity = equity_curve[-1] if equity_curve else initial_cash
    returns = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous > 0:
            returns.append((current - previous) / previous)

    metrics = {
        "initial_cash": round(initial_cash, 6),
        "final_equity": round(final_equity, 6),
        "net_profit": round(final_equity - initial_cash, 6),
        "return_pct": round(((final_equity / initial_cash) - 1.0) * 100.0, 6),
        "max_drawdown_pct": round(max_drawdown_pct(equity_curve), 6),
        "trade_count": len(trades),
        "closed_trade_count": len(closed_trade_returns),
        "win_rate_pct": round((sum(1 for value in closed_trade_returns if value > 0) / len(closed_trade_returns) * 100.0) if closed_trade_returns else 0.0, 6),
        "avg_trade_return_pct": round(mean(closed_trade_returns) * 100.0, 6),
        "sharpe_like": round((mean(returns) / stddev(returns)) * (len(returns) ** 0.5) if returns and stddev(returns) > 0 else 0.0, 6),
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "fast_window": fast_window,
        "slow_window": slow_window,
    }
    return metrics, trades, equity_rows


def run_backtest(config_path: str | Path) -> dict[str, str]:
    config, base_dir = load_config(config_path)
    data_path = (base_dir / config["data_path"]).resolve()
    artifact_dir = (base_dir / config["artifact_dir"]).resolve()
    strategy = config["strategy"]
    bars = read_ohlcv_csv(data_path)
    metrics, trades, equity = simulate_backtest(
        bars=bars,
        fast_window=int(strategy["fast_window"]),
        slow_window=int(strategy["slow_window"]),
        initial_cash=float(config.get("initial_cash", 10_000.0)),
        fee_bps=float(config.get("fee_bps", 5.0)),
        slippage_bps=float(config.get("slippage_bps", 0.0)),
    )

    metrics_path = write_json(
        artifact_dir / "metrics.json",
        {
            "experiment_id": config["experiment_id"],
            "data_path": str(data_path),
            **metrics,
        },
    )
    trades_path = write_csv(
        artifact_dir / "trades.csv",
        fieldnames=["timestamp", "side", "price", "quantity", "fee", "reason", "cash_after", "entry_price"],
        rows=trades,
    )
    write_csv(
        artifact_dir / "equity_curve.csv",
        fieldnames=["timestamp", "close", "signal", "equity", "position_units"],
        rows=equity,
    )
    return {
        "metrics_path": str(metrics_path),
        "trades_path": str(trades_path),
        "artifact_dir": str(artifact_dir),
    }
