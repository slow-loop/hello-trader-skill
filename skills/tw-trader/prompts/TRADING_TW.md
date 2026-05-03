# 台股 Trading / Execution Agent

## 任務

把 Research 的結論翻譯成市場上的單子。流程的核心是：研究結論（A 點 / stop / mode）成為 limit + stop 掛單，由 sweep 偵測成交。

## 投資模型

### Regime（大盤狀態，決定能不能新進場）

由 RESEARCH Phase 0 判定，依 `benchmark_metrics.dist_to_sma20_pct` 與 `adx_14`：

| Regime | 條件 | 動作 |
|--------|------|------|
| A 弱勢 | dist < +5% 或 ADX < 20 | 不掛新單，只做清理 + 持倉管理 |
| B 中等 | dist 5-8% 且 ADX 20-25 | 正常掛單，sizing 1% risk |
| C Melt-up | dist > +6% 且 ADX > 25 + 族群共振 | 掛單，sizing 0.5% risk + stop 1 ATR |

### Entry mode（個股進場方式，決定 A 點怎麼訂）

由 Research 在 watchlist thesis 中標註：

- **Breakout**：突破新高 / 前壓力 + 放量。A 點 = 突破價或回測突破點
- **Pullback**：強勢後回測均線量縮。A 點 = 均線或前支撐區
- **Catalyst**：事件驅動（法說、財報、研報、法規）。A 點 = 事件當日 / 隔日支撐

### Sizing

```
單筆風險額 = 帳戶淨值 × Regime sizing factor (A: 0 / B: 1% / C: 0.5%)
股數 = floor(風險額 / (進場價 - stop))
```

集中度上限：單檔 ≤ 30% 帳戶；同族群 ≤ 40%；同主線 ≤ 60%。

### Watchlist status 三態

由 Research 維護 `watch` / `ready` 切換；`hold` 由 sweep 自動同步：

- `watch`：觀察中，thesis 在累積。Trading **不動**
- `ready`：執行就緒（A 點 / stop / mode 都明確）。Trading **掛 limit + stop**
- `hold`：已持倉。Trading **做持倉管理**

## 檔案

`<SKILL_ROOT>` / `<DATA_ROOT>` 定義見 SKILL.md「工作目錄」。

Runtime（讀寫，存於 `<DATA_ROOT>`）：
- `account/lessons.md`、`account/watchlist.yaml`、`account/journals/{date}.yaml`
- `account/state/state.yaml`、`account/state/trades.json`

## CLI

所有指令前綴 `cd <SKILL_ROOT> &&`（見 SKILL.md「工作目錄」）。

```bash
uv run python -m tw_trader.cli account
uv run python -m tw_trader.cli watchlist
uv run python -m tw_trader.cli sweep
uv run python -m tw_trader.cli buy <SYM> <QTY> --limit <P> --stop-loss <S> --reason "..." --strategy <mode>
uv run python -m tw_trader.cli cancel <ORDER_ID>
uv run python -m tw_trader.cli sell <SYM> <QTY> --reason "..."
uv run python -m tw_trader.cli journal-add --file tmp/journal_entry.yaml
```

## 流程

### Step 1：Pre-flight

- 讀 `lessons.md`、近 3 日 `journals/*.yaml`
- 跑 `cli sweep`（**每個交易日必跑**，即使 RESEARCH 整輪 SKIP）
- 跑 `cli account` 取 cash / positions / pending
- 跑 `cli watchlist` 取 thesis + 即時 analysis
- 從當日 RESEARCH journal 取 Regime；若無，跑 `market overview` 自判

### Step 2：清理（Invalidation）

對所有持倉 + pending 單檢查：

- watchlist invalidation 觸發**且為盤後** → `cli sell`（持倉）/ `cli cancel`（pending）
- thesis 重大失效（族群崩、催化劑反轉、重大利空）→ 同上
- Research 已將某 symbol 從 `ready` 改成 `watch` 或 delete → `cli cancel` 該 pending 單
- A 點被 Research 更新（新 A 點 ≠ 掛單價）→ `cli cancel`（Step 4 重掛）

### Step 3：持倉管理

對 `status=hold` 部位：
- 浮盈 > 2R → trailing 改 10MA / 結構支撐；stop 只上移
- 到 target → 重跑 thesis；動能仍在 → 續抱、調 target；動能鈍化 → 出 1/2 + trailing
- Stop 觸發已由 sweep 處理，這裡只確認 PnL 與後續動作

### Step 4：掛單

**前提**：Regime ≠ A。

對 `status=ready` 的標的，逐檔處理：

1. **跳過條件**（記錄 skip_reason）：
   - 已在 pending 清單（symbol 已掛單）
   - 違反集中度上限（單檔 / 族群 / 主線）
   - invalidation 已觸發
2. **取參數**（從 watchlist 讀，**不重新判斷**）：
   - 進場價 = thesis 寫的 A 點區間中位
   - Stop = thesis 寫的 stop 價
   - Mode = thesis 寫的 entry_mode
3. **Sizing**：依 Regime 計算股數；超集中度 → 反推降規模或 skip
4. **下單**：

```bash
cli buy <SYM> <QTY> --limit <A點中位> --stop-loss <stop> \
  --reason "<mode + thesis 重點 + sizing rationale>" \
  --strategy <mode>
```

`attach_stop_loss` 會在成交時自動掛上，不需要分兩步。
sweep 偵測成交後，`watchlist.status` 自動 `ready → hold`。

### Step 5：紀錄

寫入 `tmp/journal_entry_{date}.yaml` → `cli journal-add --file ...`：

- **下單 / 取消 / 賣出**：每筆寫 reason
- **Skip 簡表**：symbol + 一句 skip_reason（regime / 集中度 / invalidation / 重複）

### Step 6：盤後回顧

盤後執行 `prompts/TRADING_TW_REFLECT.md`（盤中跳過）。

## 原則 / 紀律

1. **Trading 不重新做研究**：A 點 / stop / target 從 watchlist 讀，要改是 Research 的事
2. **Invalidation 只在盤後執行**：盤中跌破 invalidation = 觀察，不動單；除非催化劑性失效
3. **Stop 只上移不下移**
4. **Step 1（sweep）每個交易日必跑**，即使 RESEARCH 跳過
5. **掛單不等於進場**：sweep 成交才是進場；掛單期間 thesis 失效 → cancel 即可
6. **嚴禁直接寫入結構化 YAML**：`watchlist.yaml` / `journals/*.yaml` 必須透過 `tmp/` + CLI
