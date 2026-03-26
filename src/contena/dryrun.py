from __future__ import annotations

from pathlib import Path

from .backtest import build_signals
from .config import load_config
from .utils import max_drawdown_pct, mean, read_ohlcv_csv, write_csv, write_json


def run_dryrun(config_path: str | Path) -> dict[str, str]:
    config, base_dir = load_config(config_path)
    data_path = (base_dir / config["data_path"]).resolve()
    artifact_dir = (base_dir / config["artifact_dir"]).resolve()
    bars = read_ohlcv_csv(data_path)
    strategy = config["strategy"]
    dryrun_config = config["dryrun"]
    initial_cash = float(config.get("initial_cash", 10_000.0))
    fee_bps = float(config.get("fee_bps", 5.0))
    slippage_bps = float(dryrun_config.get("slippage_bps", 8.0))
    latency_bars = int(dryrun_config.get("latency_bars", 1))

    signals = build_signals(
        bars,
        fast_window=int(strategy["fast_window"]),
        slow_window=int(strategy["slow_window"]),
    )

    cash = initial_cash
    units = 0.0
    equity_curve: list[float] = []
    execution_rows: list[dict] = []
    closed_trade_returns: list[float] = []
    pending_order: dict | None = None
    open_trade_cost = 0.0

    for index, bar in enumerate(bars):
        timestamp = bar["timestamp"]
        open_price = float(bar["open"])
        close_price = float(bar["close"])

        if pending_order and pending_order["fill_index"] == index:
            side = pending_order["side"]
            if side == "buy":
                fill_price = open_price * (1.0 + slippage_bps / 10_000.0)
                quantity = cash / (fill_price * (1.0 + fee_bps / 10_000.0))
                gross = quantity * fill_price
                fee = gross * fee_bps / 10_000.0
                cash -= gross + fee
                units = quantity
                open_trade_cost = gross + fee
            else:
                fill_price = open_price * (1.0 - slippage_bps / 10_000.0)
                gross = units * fill_price
                fee = gross * fee_bps / 10_000.0
                cash += gross - fee
                if open_trade_cost > 0:
                    closed_trade_returns.append((gross - fee - open_trade_cost) / open_trade_cost)
                units = 0.0
                open_trade_cost = 0.0

            execution_rows.append(
                {
                    "timestamp": timestamp,
                    "event": "order_filled",
                    "side": side,
                    "desired_position": 1 if side == "buy" else 0,
                    "price": round(fill_price, 6),
                    "quantity": round(quantity if side == "buy" else gross / fill_price if fill_price else 0.0, 8),
                    "fee": round(fee, 6),
                    "cash_after": round(cash, 6),
                    "equity_after": round(cash + units * close_price, 6),
                    "latency_bars": latency_bars,
                    "note": pending_order["note"],
                }
            )
            pending_order = None

        desired_position = signals[index]
        current_position = 1 if units > 0 else 0
        if pending_order is None and desired_position != current_position:
            side = "buy" if desired_position == 1 else "sell"
            pending_order = {
                "side": side,
                "fill_index": index + latency_bars,
                "note": "sma_replay_signal",
            }
            execution_rows.append(
                {
                    "timestamp": timestamp,
                    "event": "order_submitted",
                    "side": side,
                    "desired_position": desired_position,
                    "price": round(close_price, 6),
                    "quantity": "",
                    "fee": "",
                    "cash_after": round(cash, 6),
                    "equity_after": round(cash + units * close_price, 6),
                    "latency_bars": latency_bars,
                    "note": "queued_for_future_fill",
                }
            )

        equity_curve.append(cash + units * close_price)

    if pending_order is not None:
        execution_rows.append(
            {
                "timestamp": bars[-1]["timestamp"],
                "event": "order_dropped",
                "side": pending_order["side"],
                "desired_position": 1 if pending_order["side"] == "buy" else 0,
                "price": round(float(bars[-1]["close"]), 6),
                "quantity": "",
                "fee": "",
                "cash_after": round(cash, 6),
                "equity_after": round(cash + units * float(bars[-1]["close"]), 6),
                "latency_bars": latency_bars,
                "note": "replay_finished_before_fill",
            }
        )

    if units > 0:
        final_price = float(bars[-1]["close"]) * (1.0 - slippage_bps / 10_000.0)
        gross = units * final_price
        fee = gross * fee_bps / 10_000.0
        cash += gross - fee
        if open_trade_cost > 0:
            closed_trade_returns.append((gross - fee - open_trade_cost) / open_trade_cost)
        execution_rows.append(
            {
                "timestamp": bars[-1]["timestamp"],
                "event": "forced_close",
                "side": "sell",
                "desired_position": 0,
                "price": round(final_price, 6),
                "quantity": round(units, 8),
                "fee": round(fee, 6),
                "cash_after": round(cash, 6),
                "equity_after": round(cash, 6),
                "latency_bars": latency_bars,
                "note": "close_open_position_at_end",
            }
        )
        units = 0.0

    final_equity = cash
    metrics = {
        "experiment_id": config["experiment_id"],
        "data_path": str(data_path),
        "initial_cash": round(initial_cash, 6),
        "final_equity": round(final_equity, 6),
        "return_pct": round(((final_equity / initial_cash) - 1.0) * 100.0, 6),
        "max_drawdown_pct": round(max_drawdown_pct(equity_curve if equity_curve else [initial_cash]), 6),
        "submitted_order_count": sum(1 for row in execution_rows if row["event"] == "order_submitted"),
        "filled_order_count": sum(1 for row in execution_rows if row["event"] == "order_filled"),
        "win_rate_pct": round((sum(1 for value in closed_trade_returns if value > 0) / len(closed_trade_returns) * 100.0) if closed_trade_returns else 0.0, 6),
        "avg_trade_return_pct": round(mean(closed_trade_returns) * 100.0, 6),
        "latency_bars": latency_bars,
        "slippage_bps": slippage_bps,
        "fee_bps": fee_bps,
    }

    execution_log_path = write_csv(
        artifact_dir / "execution_log.csv",
        fieldnames=[
            "timestamp",
            "event",
            "side",
            "desired_position",
            "price",
            "quantity",
            "fee",
            "cash_after",
            "equity_after",
            "latency_bars",
            "note",
        ],
        rows=execution_rows,
    )
    metrics_path = write_json(artifact_dir / "metrics.json", metrics)
    return {
        "execution_log_path": str(execution_log_path),
        "metrics_path": str(metrics_path),
        "artifact_dir": str(artifact_dir),
    }
