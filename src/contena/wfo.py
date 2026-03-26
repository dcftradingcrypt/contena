from __future__ import annotations

from pathlib import Path

from .backtest import simulate_backtest
from .config import load_config
from .utils import mean, read_ohlcv_csv, write_csv, write_json


def run_wfo(config_path: str | Path) -> dict[str, str]:
    config, base_dir = load_config(config_path)
    data_path = (base_dir / config["data_path"]).resolve()
    artifact_dir = (base_dir / config["artifact_dir"]).resolve()
    bars = read_ohlcv_csv(data_path)
    strategy = config["strategy"]
    wfo_config = config["wfo"]
    candidates = strategy.get("parameter_candidates") or [
        {
            "fast_window": int(strategy["fast_window"]),
            "slow_window": int(strategy["slow_window"]),
        }
    ]
    train_bars = int(wfo_config["train_bars"])
    test_bars = int(wfo_config["test_bars"])
    step_bars = int(wfo_config.get("step_bars", test_bars))
    initial_cash = float(config.get("initial_cash", 10_000.0))
    fee_bps = float(config.get("fee_bps", 5.0))

    rows: list[dict] = []
    test_returns: list[float] = []
    window_index = 0
    start = 0
    while start + train_bars + test_bars <= len(bars):
        train_slice = bars[start : start + train_bars]
        test_slice = bars[start + train_bars : start + train_bars + test_bars]

        best_candidate = None
        best_train_metrics = None
        for candidate in candidates:
            train_metrics, _, _ = simulate_backtest(
                bars=train_slice,
                fast_window=int(candidate["fast_window"]),
                slow_window=int(candidate["slow_window"]),
                initial_cash=initial_cash,
                fee_bps=fee_bps,
            )
            if best_train_metrics is None:
                best_candidate = candidate
                best_train_metrics = train_metrics
                continue
            if (
                train_metrics["return_pct"] > best_train_metrics["return_pct"]
                or (
                    train_metrics["return_pct"] == best_train_metrics["return_pct"]
                    and train_metrics["max_drawdown_pct"] < best_train_metrics["max_drawdown_pct"]
                )
            ):
                best_candidate = candidate
                best_train_metrics = train_metrics

        assert best_candidate is not None
        assert best_train_metrics is not None
        test_metrics, _, _ = simulate_backtest(
            bars=test_slice,
            fast_window=int(best_candidate["fast_window"]),
            slow_window=int(best_candidate["slow_window"]),
            initial_cash=initial_cash,
            fee_bps=fee_bps,
        )
        test_returns.append(float(test_metrics["return_pct"]))
        rows.append(
            {
                "window_index": window_index,
                "train_start": train_slice[0]["timestamp"],
                "train_end": train_slice[-1]["timestamp"],
                "test_start": test_slice[0]["timestamp"],
                "test_end": test_slice[-1]["timestamp"],
                "best_fast_window": int(best_candidate["fast_window"]),
                "best_slow_window": int(best_candidate["slow_window"]),
                "train_return_pct": round(float(best_train_metrics["return_pct"]), 6),
                "test_return_pct": round(float(test_metrics["return_pct"]), 6),
                "test_max_drawdown_pct": round(float(test_metrics["max_drawdown_pct"]), 6),
                "test_trade_count": int(test_metrics["trade_count"]),
            }
        )
        window_index += 1
        start += step_bars

    summary_csv = write_csv(
        artifact_dir / "summary.csv",
        fieldnames=[
            "window_index",
            "train_start",
            "train_end",
            "test_start",
            "test_end",
            "best_fast_window",
            "best_slow_window",
            "train_return_pct",
            "test_return_pct",
            "test_max_drawdown_pct",
            "test_trade_count",
        ],
        rows=rows,
    )
    summary_json = write_json(
        artifact_dir / "summary.json",
        {
            "experiment_id": config["experiment_id"],
            "window_count": len(rows),
            "mean_test_return_pct": round(mean(test_returns), 6),
            "data_path": str(data_path),
        },
    )
    return {
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "artifact_dir": str(artifact_dir),
    }
