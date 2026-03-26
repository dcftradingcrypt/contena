#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"
python3 -m contena.cli wfo --config configs/wfo.example.yaml
