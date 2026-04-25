# strategy-lab

你是一個量化研究 agent。任務：

1. 探索新 factor（`EXPLORE_FACTOR.md`）
2. 跑 strategy 回測迭代（`BACKTEST.md`）
3. 審核後 promote 到 production（`PROMOTE.md`）

**這個 skill 不交易**。所有產出都是 artifact（factor code、experiment 資料夾、promoted strategy yaml），由 `us-trader` 消費。

## 檔案

**skill 根目錄**：`skills/strategy-lab`

- `data/experiments/{YYYY-MM-DD_name}/`
  - `config.yaml`：strategy config（factor list + 閾值 + risk）
  - `result.json`：回測 metrics
  - `strategy_bt_{name}.md` / `factor_ic_{id}.md`：markdown 報告
- `../../libs/market-core/src/market_core/factors/catalog.py`：factor 定義

**產出位置**：`../us-trader/data/strategies/{name}.v{version}.yaml`（只能用 `lab promote` 寫入）

## CLI

```bash
# 列出所有 factor
uv run factor list

# 單因子 IC
uv run lab factor-ic trend_strength --universe sp500 --start 2020-01-01 --end 2024-12-31

# 策略回測
uv run lab strategy-bt data/experiments/2026-04-24_momentum_v1 --universe sp500

# Promote 到 us-trader
uv run lab promote data/experiments/2026-04-24_momentum_v1 --name momentum --version 1.0.0

# 列出 experiments
uv run lab list-experiments
```

## 規則

1. **Factor 只在 `libs/market-core/src/market_core/factors/catalog.py` 寫**，用 `@register` 註冊。寫完跑 `uv run factor list` 驗證註冊成功
2. **Experiment 資料夾不可修改**，要改就新建一個。resul.json 是 immutable artifact
3. **Promote 前必看 checklist**（見 `PROMOTE.md`）
4. **一次不 promote 兩個版本**——舊的還沒驗證就別疊新的
