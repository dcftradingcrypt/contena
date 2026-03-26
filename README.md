# contena

システムトレードの検証パイプラインを、Docker ベースの最小 MVP として試せる repo です。deterministic な OHLCV 生成、Backtest、WFO、DryRun（Paper Trading）、そして安全な Live stub までをひと通り揃えています。

- [記事: システムトレードの検証パイプラインを Docker でコンテナ化する理由](./docs/articles/system-trading-containerization.md)

## MVP の構成

- `market-data`: deterministic なサンプル OHLCV を生成します
- `strategy-research`: Backtest と WFO の入口です
- `strategy-executor-paper`: DryRun（Paper Trading）の入口です
- `strategy-executor-live`: 安全のため実発注を拒否する stub です
- `redis`: executor 系 service の依存先として置いた最小補助 service です

主要ファイル:

- `compose.yaml`
- `docker/research.Dockerfile`
- `docker/executor.Dockerfile`
- `docker/market-data.Dockerfile`
- `configs/*.yaml`
- `src/contena/`

## Quickstart

### Local Python

最小確認は install なしでも実行できます。

```bash
PYTHONPATH=src python3 -m contena.cli seed-data --output data/market/example_ohlcv.csv --rows 480
PYTHONPATH=src python3 -m contena.cli backtest --config configs/backtest.example.yaml
PYTHONPATH=src python3 -m contena.cli wfo --config configs/wfo.example.yaml
PYTHONPATH=src python3 -m contena.cli dryrun --config configs/dryrun.example.yaml
PYTHONPATH=src python3 -m contena.cli live --config configs/dryrun.example.yaml
```

主な出力先は次の通りです。

- `seed-data`: `data/market/example_ohlcv.csv`
- `backtest`: `artifacts/backtests/example_backtest/`
- `wfo`: `artifacts/wfo/example_wfo/`
- `dryrun`: `artifacts/dryrun/example_dryrun/`
- `live`: 実発注はせず、stub として拒否メッセージを返します

editable install を使いたい場合は、`pip` が利用できる環境で次を実行します。

```bash
python3 -m pip install -e .
python3 -m contena.cli seed-data --output data/market/example_ohlcv.csv
python3 -m contena.cli backtest --config configs/backtest.example.yaml
python3 -m contena.cli wfo --config configs/wfo.example.yaml
python3 -m contena.cli dryrun --config configs/dryrun.example.yaml
python3 -m contena.cli live --config configs/dryrun.example.yaml
```

補助 wrapper も用意しています。

```bash
./scripts/run_backtest.sh
./scripts/run_wfo.sh
./scripts/run_dryrun.sh
```

### Docker Compose

Docker CLI 自体は current verification session では未確認ですが、`compose.yaml` に合わせた想定コマンドは次の通りです。

```bash
docker compose --profile research run --rm market-data
docker compose --profile research run --rm strategy-research
docker compose --profile research run --rm strategy-research python -m contena.cli wfo --config configs/wfo.example.yaml
docker compose --profile paper run --rm strategy-executor-paper
docker compose --profile live run --rm strategy-executor-live
```

`market-data` は sample OHLCV の生成、`strategy-research` は既定で Backtest、command override で WFO、`strategy-executor-paper` は DryRun、`strategy-executor-live` は live stub を実行します。

## Safety note

`strategy-executor-live` は MVP では実発注を実装していません。安全のため、`live` subcommand は明示的に拒否し、実運用は行いません。

`data/market/*.csv`、`artifacts/` 配下の生成成果物、`logs/` 配下の実行ログは実行時に作られる前提であり、repo には commit しません。
