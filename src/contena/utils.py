from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Iterable


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(base_dir: Path, raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def read_ohlcv_csv(path: Path) -> list[dict[str, float | str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, float | str]] = []
        for row in reader:
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> Path:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_json(path: Path, payload: dict) -> Path:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[float | None] = []
    window_sum = 0.0
    for index, value in enumerate(values):
        window_sum += value
        if index >= window:
            window_sum -= values[index - window]
        if index + 1 < window:
            result.append(None)
        else:
            result.append(window_sum / window)
    return result


def max_drawdown_pct(equity_curve: list[float]) -> float:
    peak = -math.inf
    max_drawdown = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown * 100.0


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)
