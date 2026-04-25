# strategy-lab

Offline research skill: factor IC analysis, strategy backtest, promote.

Workflow:

1. **Explore a factor** — write a factor function in `libs/market-core/src/market_core/factors/catalog.py`, register with `@register`.
2. **Single-factor IC** — `lab factor-ic <factor_id>` to measure predictive power on historical panel.
3. **Strategy backtest** — edit `experiments/<date>_<name>/config.yaml`, then `lab strategy-bt <path>`.
4. **Promote** — `lab promote <experiment_dir>` to produce a versioned strategy yaml under `us-trader/data/strategies/`.

Experiments are immutable artifacts with git commit hash. Never edit a promoted
strategy yaml directly — start a new experiment and promote.
