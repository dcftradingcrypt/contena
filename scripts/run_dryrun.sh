#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
python3 -m contena.cli dryrun --config configs/dryrun.example.yaml
