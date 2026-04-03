---
name: crypto-trader
description: AI-driven crypto trading with freqtrade. Two agents work together — Strategy Lab develops and tests strategies via backtesting, Portfolio Manager allocates capital and controls risk based on market regime. Supports backtesting, dry-run, and live trading on Bybit.
---

# Crypto Trader

AI 驅動的加密貨幣交易系統，基於 freqtrade 執行引擎。

## 架構

兩個 AI agent 各自負責不同層面：

- **Strategy Lab** (`prompts/STRATEGY_LAB.md`) — 策略研發、回測驗證、衰退監控
- **Portfolio Manager** (`prompts/PORTFOLIO_MANAGER.md`) — 盤勢判斷、策略選擇、資金分配、風控

兩個 agent 透過檔案溝通（registry.yaml, market_regime.yaml, active_config.yaml）。

## When To Use

使用此 skill 當使用者想要：
- 開發或回測 crypto 交易策略
- 分析 crypto 市場盤勢
- 管理策略池（新增、退役、檢查衰退）
- 配置交易組合（選策略、分配資金）
- 執行 paper trading 或 live trading
- 查看系統狀態

## Workflow

### 初始化

```bash
uv run python -m skill_crypto_trader init
```

### Strategy Lab 流程

當使用者想開發策略、回測、或改善策略池時，執行 `prompts/STRATEGY_LAB.md`。

### Portfolio Manager 流程

當使用者想評估市場、配置組合、或管理風險時，執行 `prompts/PORTFOLIO_MANAGER.md`。

### 快速指令

```bash
# 市場數據
uv run python -m skill_crypto_trader regime
uv run python -m skill_crypto_trader funding BTCUSDT

# 策略管理
uv run python -m skill_crypto_trader strategy list
uv run python -m skill_crypto_trader strategy show <name>
uv run python -m skill_crypto_trader strategy backtest <name> --timerange 20240101-20250101

# 狀態
uv run python -m skill_crypto_trader status
uv run python -m skill_crypto_trader portfolio candidates --lookback-bars 96
```

## Data Files

- `data/strategies/registry.yaml` — 策略池
- `data/config/risk_rules.yaml` — 風控規則
- `data/config/pairs.yaml` — 交易對
- `data/account/lessons_lab.md` — Lab 學習記錄
- `data/account/lessons_pm.md` — PM 學習記錄
- `data/account/journals/lab/` — Lab 循環記錄
- `data/account/journals/pm/` — PM 循環記錄
- `data/account/state/market_regime.yaml` — 盤勢判斷
- `data/account/state/active_config.yaml` — 啟用策略配置

## Safety

- Paper trading (dry-run) 是預設模式
- Live trading 需要明確設定 Bybit API keys
- 風控規則不可違反
- max_leverage = 1（MVP 不用槓桿）
