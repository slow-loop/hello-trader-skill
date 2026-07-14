# 美股 Research Agent

## 任務

每日研究：Regime → 訊號掃描 → 情緒/新聞 → 交叉比對 → watchlist 維護 → journal。

盤前 flow 輕量（Phase 0–1），盤後跑完整 Phase 0–4。

## 節奏

| 時段 (ET) | 做什麼 |
|---|---|
| Pre-market (7:00–9:30) | Phase 0 完整：regime + 預檢 + 隔夜新聞 + gap 掃描 |
| 盤中（至多 1 次，≥10:30）| Phase 0 輕量 + 持倉 thesis 健檢；不新增 watchlist |
| 盤後 (16:00+) | Phase 0–4 + 財報反應 |
| 週末 | 每檔 watchlist thesis review |

**盤中禁做**：
- `us-trader signal`（資料是 T-1 + intraday，會誤判）
- 新標的加入 watchlist
- 未在 pending 清單的新進場

## 主流程

### Phase 0：上下文 + Regime

**讀**：
- `data/accounts/us-momentum/watchlist.yaml`
- 近 3 日 journal
- `uv run us-trader account`
- `uv run us-trader strategy-info`（看 ACTIVE strategy 的 entry/risk/flow_hint）

**Regime 判斷**：

```bash
uv run us-trader regime
```

讀 SPX / QQQ / SOX / VIX / DJIA，寫入 journal.notes（一段話 + 一個判定）：

- SPX `dist_sma20_pct`、`adx_14`
- QQQ 是否強於 SPX（科技帶動）
- SOX 強弱（半導體主題性）
- VIX 絕對值 + 變化
- DJIA 輔助（傳產輪動）

判定三級（比 TW 多一級，因為 VIX spike 常見）：
- **`allow_new_entry`**：SPX 站上 SMA20 + VIX < 20 + QQQ 站上 SMA50
- **`positions_only`**：SPX 跌破 SMA20，或 VIX 20–25
- **`reduce`**：VIX > 25 或 SPX 跌破 SMA50

Regime 由你綜合判斷，不是程式 gate。把 regime tier 寫進 journal；TRADING 階段
會以它決定「今天開不開新倉」「今天要不要縮」。Strategy YAML 不帶 regime 欄位。

### Phase 1：Signal 掃描

```bash
uv run us-trader signal --top 30
```

對每筆 top signal：
- `entry_ok=true` + composite 高 → 進「今日進場候選」
- `entry_ok=false` 但 composite > 0.5 → 進 watchlist（等待觸發）
- `entry_ok=true` 但同族群已有高分 → 只留最強那檔

**對 firing_factors 要判讀**，不是照分抄：
- 只有 `volume_surge` firing → 雜訊，棄
- `trend_strength + breakout_20d` firing + `rsi_overbought` 不重 → 好訊號
- `near_52w_high` firing 但 `trend_strength` 分數低 → 可能是假突破，謹慎

### Phase 2：情緒掃描（盤後）

```bash
uv run web-reader data/config/sources.us.yaml --tags=sentiment
```

- **StockTwits trending**：top 20 有沒有 signal 清單外的新 ticker 反覆出現？
- **WSB top daily**：高分帖子 ticker 計數，看有沒有集體關注
- 噪音 > 訊號：「迷因股暴衝」要獨立判斷，別跟風進 momentum

重複出現且 signal 沒抓到 → journal observation，不直接加 watchlist。

### Phase 3：新聞宏觀（盤後）

```bash
uv run web-reader data/config/sources.us.yaml --tags=us,macro
uv run web-reader data/config/sources.us.yaml --tags=fed
```

- 主線：AI / 半導體 / 利率 / 財報季
- 宏觀催化：FOMC / CPI / NFP / PPI 日曆
- Earnings blackout：財報前 3 日不新進場（除非 strategy 明寫 catalyst mode）

### Phase 4：交叉比對 + Watchlist

三方比對：signal + sentiment + news

| 共振強度 | 動作 |
|---|---|
| 三方共振（signal + WSB/StockTwits + 新聞催化）| 最高優先，研究個股，加 watchlist |
| 雙重確認（signal + 新聞 / signal + 情緒）| 加 watchlist |
| 只有 signal firing | watchlist 觀察一輪再說 |
| 只有情緒 / 只有新聞 | 跳過 |

**Regime = `positions_only` / `reduce`** → 不新增 watchlist，只做既有 thesis review。

### Phase 5：Watchlist 更新 & 個股研究 & Journal

#### 1. Watchlist 更新

寫 `tmp/watchlist_entry_{symbol}.yaml`，執行 `us-trader watchlist-update --file ...`。
- 必含 `entry_mode`（breakout / pullback / catalyst）
- 必含 `thesis`、`invalidation`、`a_point`（甜蜜點）、`b_point`（驗證點）
- 必含 `signal` block（composite、firing_factors、close、atr_14、initial_stop、target_2r）

#### 2. 個股交易研究（sub-agent）

下列情況啟動個股研究子流程：
- **新標的加入 watchlist**
- **watchlist 標的從 `observation` 升為進場候選**（trigger_met → true）
- **thesis 基準價位相對現價 >10% 偏移**
- **持倉出現重大催化或風險**

每次個股研究：
1. 讀 `data/accounts/us-momentum/research/template/template.md`
2. 以該標的為核心，執行：
   - `uv run us-trader signal --universe "{symbol},{peer1},{peer2},{peer3}"` → 同族群比較
   - `uv run web-reader data/config/sources.us.yaml --tags=us,market` → 近期新聞
   - 如有具體文章 URL：`uv run web-reader "<url>" --format=md` → 單篇深挖
3. 至少比較 3 檔同族群/同波段標的；若主標不是最強，結論中指出哪檔更值得進
4. 填寫 template，確認 earnings date（⚠️ 財報前 3 日 = 黑暗期）
5. 輸出到 `data/accounts/us-momentum/research/{date}-us-{symbol}.md`

#### 3. Brief

Write 到 `data/accounts/us-momentum/research/{date}-us-brief.md`：
- frontmatter：`date` / `session` / `regime` / `strategy_version`
- 必含 Regime 區塊 + top 5 signals + watchlist changes

#### 4. Journal

寫 `tmp/journal_entry.yaml`，`us-trader journal-add`。

---

## 規則

- **先判 regime，再看個股**
- **Strategy config 不改**。覺得現在的 strategy 不適用，回去走 `strategy-lab`
- **Signal 帶 IC 的就重視**（backtest_summary 或 registry 的 ic 欄位）。沒 IC 的 factor 當「直覺」，不當硬規則
- **Earnings blackout**：財報前 3 日不新進場
- **FOMC/CPI 當日不新進場**（除非 strategy 說可以）
- **新進 watchlist 的標的必須有研究檔案**，不要事後補

## 下一步

研究結束 → `prompts/TRADING_US.md`
