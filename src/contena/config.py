from __future__ import annotations

from pathlib import Path

import yaml

from .utils import resolve_path


def load_config(config_path: str | Path) -> tuple[dict, Path]:
    path = Path(config_path).resolve()
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    if "strategy_config" in config:
        strategy_path = resolve_path(path.parent, config["strategy_config"])
        with strategy_path.open("r", encoding="utf-8") as handle:
            strategy_config = yaml.safe_load(handle) or {}
        merged_strategy = dict(strategy_config)
        merged_strategy.update(config.get("strategy", {}))
        config["strategy"] = merged_strategy
        config["_strategy_config_path"] = str(strategy_path)

    config["_config_path"] = str(path)
    return config, path.parent
