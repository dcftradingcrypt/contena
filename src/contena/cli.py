from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import run_backtest
from .data_seed import generate_sample_ohlcv
from .dryrun import run_dryrun
from .live import run_live_stub
from .wfo import run_wfo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contena", description="contena MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed-data", help="Generate deterministic OHLCV sample data")
    seed_parser.add_argument("--output", required=True, help="Output CSV path")
    seed_parser.add_argument("--rows", type=int, default=480, help="Number of OHLCV rows to generate")
    seed_parser.add_argument("--start", default="2024-01-01T00:00:00+00:00", help="ISO8601 start timestamp")
    seed_parser.add_argument("--interval-minutes", type=int, default=60, help="Bar interval in minutes")

    for command_name, help_text in [
        ("backtest", "Run a deterministic backtest"),
        ("wfo", "Run rolling walk-forward optimization"),
        ("dryrun", "Replay CSV as paper trading"),
        ("live", "Safety stub for live mode"),
    ]:
        command_parser = subparsers.add_parser(command_name, help=help_text)
        command_parser.add_argument("--config", help="YAML config path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "seed-data":
        output_path = generate_sample_ohlcv(
            output_path=Path(args.output).resolve(),
            rows=args.rows,
            start=args.start,
            interval_minutes=args.interval_minutes,
        )
        print(json.dumps({"output_path": str(output_path)}, ensure_ascii=False))
        return 0

    if args.command == "backtest":
        print(json.dumps(run_backtest(args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "wfo":
        print(json.dumps(run_wfo(args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "dryrun":
        print(json.dumps(run_dryrun(args.config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "live":
        return run_live_stub()

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
