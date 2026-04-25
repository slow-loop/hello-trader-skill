# Backtest Strategy

任務：把 factor 組合成 strategy，跑回測、調 config、比對 baseline。

## 流程

### 1. 起一個新 experiment 資料夾

命名慣例：`data/experiments/{YYYY-MM-DD}_{strategy_name}_{variant}/`

範例：
- `2026-04-24_momentum_v1/`
- `2026-04-25_momentum_v2_add_earnings/`
- `2026-04-26_meanrev_rsi30/`

資料夾內放 `config.yaml`，格式見下。

### 2. 寫 strategy config.yaml

```yaml
name: momentum           # promote 時會被覆寫，這裡當標記用
version: 0.1.0
description: |
  高動能趨勢跟隨，多因子共振。
factors:
  - id: trend_strength
    weight: 1.0
    min_score: 0.3
    required: true            # 不 firing 直接 skip 這檔
  - id: breakout_20d
    weight: 1.2
    min_score: 0.3
  - id: near_52w_high
    weight: 0.8
    min_score: 0.3
  - id: volume_surge
    weight: 0.5
  - id: rsi_overbought
    weight: 1.0               # 負分會拖累 composite，當警訊
entry:
  composite_score_min: 1.0
  must_include: []           # symbols 一定要包含
  must_exclude: []           # symbols 一定要排除
risk:
  initial_stop_formula: "close - 1.5 * atr_14"
  target_r: 2.0
  max_position_pct: 30.0
  account_risk_pct: 1.0
agent_flow_hint: |
  交給 us-trader：
  1. cli signal 拉當日 top 20 signals
  2. 逐檔讀 firing_factors + IC，判 R:R
  3. regime 由 agent 綜合判斷（VIX / SPX 趨勢 / 消息面），不是程式 gate
```

> **Regime 不是 gate**。Strategy YAML 不帶 `regime_must_be`；us-trader agent
> 拿到所有市場資訊（VIX、SPX trend、消息）後自己綜合判斷要不要進場。
> 回測裡 regime 也不模擬，所以 backtest Sharpe / DD 反映的是「無 regime 濾網」
> 的上限，真實表現會更好（agent 在 risk_off 會少開倉）。

### 3. 跑回測

```bash
uv run lab strategy-bt data/experiments/2026-04-24_momentum_v1 --universe sp500 --start 2020-01-01 --end 2024-12-31
```

輸出：
- `result.json`（Sharpe / DD / turnover / trades）
- `strategy_bt_{name}.md`（markdown 報告）

### 4. 比對 baseline

**第一個實驗**：baseline 就是 buy-and-hold SPY 同期 Sharpe。要顯著超過才有意義。

**迭代**：和前一版 experiment 比 Sharpe / max DD / turnover。改一個因子或參數就記一次，避免一次改太多搞不清哪個有效。

### 5. Walk-forward 驗證（想嚴謹時）

把 2020–2024 切成：
- Train 2020–2022 → 選參數
- Test 2023 → 驗證
- Final 2024 → 絕對不碰，只在最終 promote 前跑一次

如果 train Sharpe 1.5、test Sharpe 0.3 → overfitting，重做。

### 6. 判定

通過標準（建議）：
- Sharpe > 1.0（相對 baseline 至少 +0.3）
- Max DD < 20%
- Turnover 合理（動能策略 monthly 20–40% 是正常範圍）
- Walk-forward 沒明顯退化

通過 → 下一步走 `PROMOTE.md`。沒通過 → 改 config，新開資料夾，重跑。

## 禁忌

- **不要改已經跑過的 experiment 資料夾的 config**。結果會不一致
- **不要跑一次就 promote**。至少兩次不同參數確認不是運氣
- **不要只看 Sharpe**。DD / turnover / trade count 都要看
- **不要在同一期做太多 experiment**。每次只改 1–2 個變數，否則搞不清楚歸因
