from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .utils import ensure_directory


def generate_sample_ohlcv(
    output_path: Path,
    rows: int = 480,
    start: str = "2024-01-01T00:00:00+00:00",
    interval_minutes: int = 60,
) -> Path:
    ensure_directory(output_path.parent)
    start_dt = datetime.fromisoformat(start)
    previous_close = 100.0

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
        )
        writer.writeheader()

        for index in range(rows):
            timestamp = start_dt + timedelta(minutes=index * interval_minutes)
            base = 100.0 + index * 0.08
            seasonal = math.sin(index / 7.0) * 2.4 + math.cos(index / 17.0) * 1.3
            close = round(base + seasonal, 4)
            open_price = round(previous_close, 4)
            spread = 0.9 + abs(math.sin(index / 5.0)) * 0.7
            high = round(max(open_price, close) + spread, 4)
            low = round(min(open_price, close) - spread, 4)
            volume = round(1000 + 120 * math.sin(index / 3.0) + 90 * math.cos(index / 11.0) + index * 2.5, 4)
            writer.writerow(
                {
                    "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
            previous_close = close

    return output_path
