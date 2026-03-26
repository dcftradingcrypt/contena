from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from contena.backtest import run_backtest
from contena.data_seed import generate_sample_ohlcv
from contena.dryrun import run_dryrun
from contena.wfo import run_wfo


def write_yaml(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    return path


def test_seed_data_creates_csv(tmp_path: Path) -> None:
    output_path = tmp_path / "market" / "sample.csv"
    generate_sample_ohlcv(output_path, rows=32)
    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "timestamp,open,high,low,close,volume"
    assert len(lines) == 33


def test_backtest_creates_metrics_and_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data" / "sample.csv"
    generate_sample_ohlcv(data_path, rows=180)

    strategy_path = write_yaml(
        tmp_path / "configs" / "strategies" / "sma.yaml",
        {
            "name": "sma_crossover",
            "fast_window": 6,
            "slow_window": 18,
            "parameter_candidates": [
                {"fast_window": 6, "slow_window": 18},
                {"fast_window": 8, "slow_window": 24},
            ],
        },
    )
    config_path = write_yaml(
        tmp_path / "configs" / "backtest.yaml",
        {
            "experiment_id": "test_backtest",
            "data_path": "../data/sample.csv",
            "artifact_dir": "../artifacts/backtests/test_backtest",
            "strategy_config": "strategies/sma.yaml",
            "initial_cash": 10_000,
            "fee_bps": 5,
            "slippage_bps": 0,
        },
    )

    result = run_backtest(config_path)
    metrics = json.loads(Path(result["metrics_path"]).read_text(encoding="utf-8"))
    assert strategy_path.exists()
    assert Path(result["trades_path"]).exists()
    assert metrics["experiment_id"] == "test_backtest"
    assert "return_pct" in metrics


def test_wfo_and_dryrun_create_artifacts(tmp_path: Path) -> None:
    data_path = tmp_path / "data" / "sample.csv"
    generate_sample_ohlcv(data_path, rows=360)

    write_yaml(
        tmp_path / "configs" / "strategies" / "sma.yaml",
        {
            "name": "sma_crossover",
            "fast_window": 8,
            "slow_window": 24,
            "parameter_candidates": [
                {"fast_window": 8, "slow_window": 24},
                {"fast_window": 10, "slow_window": 30},
            ],
        },
    )
    wfo_config = write_yaml(
        tmp_path / "configs" / "wfo.yaml",
        {
            "experiment_id": "test_wfo",
            "data_path": "../data/sample.csv",
            "artifact_dir": "../artifacts/wfo/test_wfo",
            "strategy_config": "strategies/sma.yaml",
            "initial_cash": 10_000,
            "fee_bps": 5,
            "wfo": {"train_bars": 180, "test_bars": 60, "step_bars": 60},
        },
    )
    dryrun_config = write_yaml(
        tmp_path / "configs" / "dryrun.yaml",
        {
            "experiment_id": "test_dryrun",
            "data_path": "../data/sample.csv",
            "artifact_dir": "../artifacts/dryrun/test_dryrun",
            "strategy_config": "strategies/sma.yaml",
            "initial_cash": 10_000,
            "fee_bps": 5,
            "dryrun": {"latency_bars": 1, "slippage_bps": 10},
        },
    )

    wfo_result = run_wfo(wfo_config)
    dryrun_result = run_dryrun(dryrun_config)

    assert Path(wfo_result["summary_csv"]).exists()
    assert Path(wfo_result["summary_json"]).exists()
    assert Path(dryrun_result["execution_log_path"]).exists()
    assert Path(dryrun_result["metrics_path"]).exists()
