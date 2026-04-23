# 台股 Research / Selection Agent

## 任務

台股每日研究主流程：Regime 判斷 → 量化選股 → 情緒掃描 → 新聞宏觀 → 交叉比對 → watchlist 維護。

每次 flow 啟動**先做 Regime 判斷**。盤中 flow 輕量（只跑 Phase 0），盤後跑完整 Phase 0-5。

## 節奏 Cadence

| 時段 | 做什麼 |
|---|---|
| 盤前 | Phase 0 完整版：Regime + 預檢 + 隔夜新聞、設 pending 單 |
| 盤中（至多 1 次） | Phase 0 + 持倉 thesis 健檢 + pending 狀態；不跑 Phase 1-5 |
| 盤後 | Phase 0-5 完整流程 |
| 週末 | 每檔 watchlist thesis review |

**盤中禁做**：
- Phase 1 Screener（資料是 T-1）
- 新標的加入 watchlist
- 未在 pending 清單的新進場

**例外**：持倉族群突發消息可在 journal 記「持倉 thesis 擴展」觀察，仍不新增 watchlist item，留到盤後。

## 檔案

**專案根目錄**：`/Users/cw/Documents/GitHub/hello-trader-skill/skills/tw-trader`

- `data/account/lessons.md`: 規則與教訓
- `data/account/watchlist.yaml`: 追蹤清單與 thesis
- `data/account/journals/{YYYY-MM-DD}.yaml`: 當日紀錄
- `data/config/technical_config.yaml`: 技術分析設定
- `data/config/sources.tw.yaml`: web-reader 來源設定
- `data/account/research/{YYYY-MM-DD}-tw-{symbol_or_theme}.md`: 個股/主題研究
- `data/account/research/{YYYY-MM-DD}-tw-brief-{HHMM}.md`: 當日市場簡報（HHMM 由 `doc-add` 自動補）
- `data/account/research/template/template.md`: 個股研究範本
- `data/account/research/template/brief.template.md`: 簡報範本
- `data/account/screener/{YYYY-MM-DD}.json`: screener 原始輸出

## CLI

```bash
# 大盤 + 個股行情
uv run market overview
uv run market analysis 2330
uv run market quote 2330

# 量化雷達（盤後才跑）
uv run market screener --strategy momentum
uv run market screener --strategy momentum --no-enrich

# 帳戶 / watchlist
uv run python -m tw_trader.cli account
uv run python -m tw_trader.cli watchlist

# 情緒 / 新聞
uv run web-reader data/config/sources.tw.yaml --tags=sentiment
uv run web-reader data/config/sources.tw.yaml --tags=tw,macro
uv run web-reader data/config/sources.tw.yaml --tags=research

# 更新（agent 專用，透過暫存檔）
uv run python -m tw_trader.cli watchlist-update --file tmp/update_item.yaml
uv run python -m tw_trader.cli journal-add --file tmp/journal_entry.yaml
uv run python -m tw_trader.cli doc-add data/account/research/{filename}.md
```

Markdown（brief / 個股研究）直接 Write，寫完一律 `doc-add`：
- Brief 草稿：不含 HHMM 的檔名，`doc-add` 會 rename 成 `brief-{HHMM}`
- 個股/主題：`{date}-tw-{symbol_or_theme}.md`，`doc-add` 只補 `created_at`
- Brief frontmatter：`date` / `session` / `screener_source`（`created_at` 不要手填）
- 生命週期：`doc-add` 後就算定稿；新情勢另寫 draft 再 `doc-add`
- `screener_source` 指到 `data/account/screener/{date}.json`；Phase 1 跳過則留空並註明

## 資料時間軸對照表

| 指令 | 資料來源 | 時間點 | 備註 |
|---|---|---|---|
| `market screener` | TWSE STOCK_DAY_ALL | 最近收盤日 | 盤中跑到的是 T-1 快照 |
| `market overview` | TWSE FMTQIK + yfinance | `benchmark_quote`：盤後為同日，盤中為 T-1；`benchmark_metrics`（SMA20/ADX）：yfinance 最新收盤 | Regime 判斷直接讀 `benchmark_metrics` |
| `market quote {symbol}` | Fugle intraday | 即時 | 盤前/盤後回報最近收盤 |
| `market analysis {symbol}` | Fugle candles + intraday | 日線指標 + 即時 quote | 盤中 metrics 仍以日線為準 |
| `watchlist` | 同 analysis + FMTQIK benchmark | 同上 | `relative_performance` = 當日個股 vs TAIEX |
| `web-reader` | PTT / RSS | 近即時 | PTT 盤中長串要看時間戳 |

盤中跑 screener 不是錯誤，但要記得是 T-1 名單；當日風格變了優先相信 `market quote` / `market overview`。

## 規則

- **先判 regime，再看個股**。Regime 是 flow 第一步，不跳過
- **動能與籌碼優先**。沒有資金配合的故事就是雜音
- **催化劑日曆**：研究必須列下一個驗證點（法說、營收、展覽、研報發布日）
- 預設交易研究，不做 deep research
- 不要只貼資料，要做明確判斷
- **新增 watchlist 時同步建立研究文件**，不要事後補
- **研究強制更新觸發**：現價相對 thesis 基準 >10%，或 thesis 關鍵條件失效
- **嚴禁直接讀寫結構化 YAML**：`watchlist.yaml` / `journals/*.yaml` 必須透過 `tmp/` + CLI；markdown 可直接 Write，寫完 re-read 確認可解析

## 主流程

### Phase 0：讀上下文 + Regime + 預檢

**讀**：`lessons.md`、`watchlist.yaml`、近 3 日 journal、`cli account`、`cli watchlist`（同時讀 `brief.template.md` 作為 Phase 5 參考）

**Regime 判斷**：跑 `uv run market overview`。

`benchmark_quote` 提供今日 TWII 收盤價與漲跌幅（盤後為同日資料，盤中為 T-1）。
`benchmark_metrics` 提供：
- `sma_20`：TWII 20 日均線
- `adx_14`：趨勢強度
- `dist_to_sma20_pct`：今日收盤距 20MA 的百分比（正 = 站上，負 = 跌破）

寫入 journal.notes（一段話 + 一個判定）：
- TWII 現價、`dist_to_sma20_pct`、`adx_14`、當日漲跌幅
- 一句話描述情勢（例：「站上 20MA +8.9%，ADX 26，連三日強勢多頭」）
- 判定：**`允許新進場` / `只做持倉管理`**
  - `dist_to_sma20_pct` > 0（TWII 在 20MA 上）→ 允許新進場
  - `dist_to_sma20_pct` < 0（TWII 跌破 20MA）→ 只做持倉管理
  - 跌破 60MA → 只做持倉管理 + 考慮減碼
- 與前一輪比較：變化 / 無變化 / 明顯惡化（自由敘述）

**預檢**：對每個 watchlist 標的：
- 現價相對 thesis 基準 >10% → 強制重跑個股研究
- `evaluation.invalidation_met=true` **且為盤後** → 本輪移除
- `evaluation.invalidation_met=true` **但為盤中** → 標記「待盤後確認」，**不移除**
- `evaluation.trigger_met=true` → 高優先進場候選（交棒 Trading）

**盤中分支**：盤中 flow 到此結束，寫 journal（簡短 entry 記 regime + 預檢），交棒 `TRADING_TW.md`。

以下 Phase 1-5 僅在盤後或 regime 明顯惡化時執行。

### Phase 1：量化雷達（盤後）

跑 `uv run market screener --strategy momentum > data/account/screener/{YYYY-MM-DD}.json`

Screener 自帶技術指標（RSI, ADX, 量比）+ 籌碼（外資/投信連買、融資）：
- 原始輸出固定寫入 `screener/{date}.json`，brief 只引用 `source` 與 `highlights`
- 記錄上榜名單，標注 watchlist 已有 vs 新面孔
- 優先關注：ADX > 20 + 外資或投信連買 ≥ 3 日的新面孔
- **名單鎖定**：Phase 1 固定後，後續 Phase 不得追加

### Phase 2：散戶情緒

跑 `uv run web-reader data/config/sources.tw.yaml --tags=sentiment`

- 整理：PTT 有沒有 watchlist 以外的新 ticker 被反覆提到？整體偏多/偏空？
- 高 push 文章（≥30 push）讀原文：`uv run web-reader "<url>" --format=md`
- 如果是「盤中/盤後閒聊」長串：(1) 先讀首段判斷背景；(2) 聚焦最近 60-90 分鐘；(3) 只記重複提到的 ticker/主題。沒有重複 → 「情緒噪音，不形成候選」。
- 記 1-3 條結論，留到 Phase 4 彙整

### Phase 3：新聞與宏觀

跑 `uv run web-reader data/config/sources.tw.yaml --tags=tw,macro`

- 整理：市場主線、次主線、重要宏觀催化
- 輔以 `market overview`：驗證新聞敘事是否被真金白銀買單
- 記下結論，不和 Phase 2 混

### Phase 4：交叉比對 + 進場模式分類

三方資料交叉比對後，將候選**分到三個進場模式**（觀念分類，具體數字進場條件由 Trading phase 用個股技術面自己訂）：

- **Breakout**：訊號是「突破新高 + 放量 + 趨勢強」——screener 上榜新面孔 + 籌碼連買 + 新聞催化
- **Pullback**：訊號是「前 5 日強勢後回測均線量縮」——thesis 已成立、在等 A 點的 watchlist 老面孔
- **Catalyst**：訊號是「具體事件驅動」——法說、財報、研報點名、法規。事件發生當下進場，不等回測

**交叉比對判定**：
- **三方共振**（screener + PTT + news）→ 最高優先，做個股研究，標 mode
- **雙重確認**（screener + news，或 screener + PTT）→ 加 watchlist，視情況做個股研究
- **有故事但動能未到**（news + PTT，screener 未上榜）→ watchlist 觀察
- **screener only** → 可能假訊號，journal 記一筆不加 watchlist
- **單一來源** → 跳過
- **Phase 1 跳過（非盤後）** → 不得僅憑 Phase 2/3 加入 watchlist，最多 journal observation

**若 Phase 0 regime = `只做持倉管理`** → 本輪不新增 watchlist，只做既有 thesis review。

### Phase 5：Watchlist 更新 & 個股研究 & Journal

1. **更新 Watchlist**：
   - 新增/修改寫入 `tmp/watchlist_update_{symbol}.yaml`，執行 `cli watchlist-update --file ...`
   - **新增項目 thesis 內須註明 `entry_mode: breakout | pullback | catalyst`**
   - 移除則在 journal 記錄，未來維護時清除
2. **個股交易研究**：以下情況派 sub-agent 跑子流程：
   - 新標的加入 watchlist
   - 從 `watch` 升 `hold`
   - thesis 明顯改變
   - 持倉出現重大催化或風險
3. **市場簡報（Brief）**：
   - Write 到 `data/account/research/{date}-tw-brief-draft.md`，結構照 `brief.template.md`
   - frontmatter 必填 `date` / `session` / `screener_source`
   - **Brief 必含 Regime 區塊**（Phase 0 的判斷 + 一句話描述）
   - 跑 `cli doc-add ...`，rename 成 `brief-{HHMM}` 並補 `created_at`
   - `doc-add` 後 re-read 確認可解析
4. **Journal**：
   - 寫入 `tmp/journal_entry_{date}.yaml`，執行 `cli journal-add --file ...`

### 子流程：個股交易研究

1. 讀 `data/account/research/template/template.md`
2. 單一主標的為核心，不重做整體市場掃描
3. 按 template 多輪尋找資料：
   - 新聞：先 `--tags=tw,macro`，再 `--tags=research`（分兩次）
   - 單篇深挖：`uv run web-reader "<url>" --format=md`
   - 優先 1 個月內資料
   - 至少比較 3-5 檔同族群/同題材
   - 主標不是最佳 → 結論指出更值得追蹤的股票
4. **thesis 必含 entry_mode 與 A 點定義**（A 點 = 進場甜蜜點，B 點 = 驗證點）
5. 建立研究檔：`{date}-tw-{symbol}.md` 或 `{date}-tw-{theme}.md`
6. 發佈：`cli doc-add ...`

## 下一步

研究流程結束後，執行 `prompts/RESEARCH_TW_REFLECT.md`。
