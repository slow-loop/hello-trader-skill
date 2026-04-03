---
name: xstocks-trader
description: AI-driven tokenized stock (RWA) trading on Hyperliquid DEX. Agent makes trading decisions based on SPY/QQQ macro regime and individual stock technical analysis. Supports paper trading via CLI. Freqtrade available offline for strategy backtesting.
---

# X-Stocks Trader

AI 驅動的代幣化股票 (Tokenized Stocks / RWA) 交易系統。

## 架構

**tw-trader 架構的美股移植版**。Agent 根據總經盤勢 (SPY/QQQ) 與個股技術分析，主動決定交易。

- 資料來源：**CCXT → Hyperliquid DEX**（即時報價）
- 技術分析：**pandas-ta**（60+ 指標與觸發器）
- 下單引擎：**Paper Trading**（自管 Ledger）
- 離線回測：**Freqtrade**（Yahoo Finance 歷史資料）

## When To Use

使用此 skill 當使用者想要：
- 在 24/7 市場環境測試 Agent 交易決策能力
- 分析美股代幣化資產（AAPL, TSLA, NVDA）的技術面
- 判斷 SPY/QQQ 宏觀牛熊狀態
- 執行 paper trading（模擬交易）
- 離線回測新策略想法

## Workflow

### 初始化

```bash
uv run python -m skill_xstocks_trader.cli init --cash 10000
```

### 交易流程

當使用者想交易或看盤時，執行 `prompts/TRADING.md`。

### 快速指令

```bash
# 總經盤勢
uv run python -m skill_xstocks_trader.cli regime

# 個股分析
uv run python -m skill_xstocks_trader.cli market AAPL/USDC TSLA/USDC

# 帳戶
uv run python -m skill_xstocks_trader.cli account

# 交易
uv run python -m skill_xstocks_trader.cli buy TSLA/USDC --qty 1 --strategy momentum --reason "RSI超賣"
uv run python -m skill_xstocks_trader.cli sell TSLA/USDC --qty 1 --price 270 --reason "止盈"

# 歷史
uv run python -m skill_xstocks_trader.cli history
```

### 離線回測

```bash
# 下載歷史資料（Yahoo Finance → Freqtrade JSON）
uv run --with yfinance python scripts/download_yfinance.py --symbols AAPL TSLA --timeframe 1d --period 5y
```

## Data Files

- `data/config/pairs.yaml` — 交易對與總經追蹤對
- `data/config/technical_config.yaml` — 技術分析設定
- `data/account/watchlist.yaml` — 追蹤中的標的
- `data/account/lessons.md` — 學習記錄
- `data/account/journals/` — 每日交易紀錄
- `data/account/state/ledger.json` — 帳戶狀態
- `data/account/state/equity.json` — 資產快照

## Safety

- Paper trading (模擬交易) 是預設模式
- 24/7 市場不代表要 24/7 交易；美股盤後流動性差
- 每筆交易必須有明確的出場計畫（SL + TP）
