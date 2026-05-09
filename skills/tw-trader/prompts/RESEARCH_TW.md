# 台股 Research / Selection Agent

## 任務

台股每日研究主流程：Regime 判斷 → 量化選股 → 情緒掃描 → 新聞宏觀 → 交叉比對 → watchlist 維護。

每次 flow 啟動**先做 Regime 判斷**。

## 節奏 Cadence

| 時段 | 做什麼 |
|---|---|
| 盤前 | Phase 0 + **2 + 3**（+ 必要時 4/5）：Regime + 預檢 + 隔夜情緒/新聞 + 設 pending 單。**唯一跳過的是 Phase 1 Screener**（資料 T-1，盤前無意義） |
| 盤中（至多 1 次） | Phase 0 + 持倉 thesis 健檢 + pending 狀態；不跑 Phase 1-5 |
| 盤後 | Phase 0-5 完整流程 |
| 週末 | 每檔 watchlist thesis review |

**盤前限制**：
- Phase 1 Screener 跳過（T-1 資料，重跑等於昨晚結果）
- 不加入**全新**標的（來不及完整研究）；已有標的的 thesis 更新可做
- 未在 watchlist 的新進場不執行（等盤後完整研究後再判斷）

**盤中禁做**：
- Phase 1 Screener（資料是 T-1）
- 新標的加入 watchlist
- 未在 pending 清單的新進場

**例外**：持倉族群突發消息可在 journal 記「持倉 thesis 擴展」觀察，仍不新增 watchlist item，留到盤後。

## 檔案

`<SKILL_ROOT>` / `<DATA_ROOT>` 定義見 SKILL.md「工作目錄」。

Runtime（讀寫頻繁，存於 `<DATA_ROOT>`）：

- `<DATA_ROOT>/account/strategy.md`: 規則與教訓
- `<DATA_ROOT>/account/watchlist.yaml`: 追蹤清單與 thesis
- `<DATA_ROOT>/account/journals/{YYYY-MM-DD}.yaml`: 當日紀錄
- `<DATA_ROOT>/account/research/{YYYY-MM-DD}-tw-{symbol_or_theme}.md`: 個股/主題研究
- `<DATA_ROOT>/account/research/{YYYY-MM-DD}-tw-brief-{HHMM}.md`: 當日市場簡報（HHMM 由 `doc-add` 自動補）
- `<DATA_ROOT>/account/screener/{YYYY-MM-DD}.json`: screener 原始輸出

Static（只讀，存於 `<SKILL_ROOT>`）：

- `<SKILL_ROOT>/config/technical_config.yaml`: 技術分析設定
- `<SKILL_ROOT>/config/sources.tw.yaml`: web-reader 來源設定
- `<SKILL_ROOT>/templates/research/template.md`: 個股研究範本
- `<SKILL_ROOT>/templates/research/brief.template.md`: 簡報範本

## CLI

所有指令前綴 `cd <SKILL_ROOT> &&`（見 SKILL.md「工作目錄」）。範例省略前綴以保持可讀，實際執行時必須加上。

```bash
# 大盤 + 個股行情
uv run market overview
uv run market analysis 2330
uv run market quote 2330

# K 線圖（個股研究 / thesis 重評時用）
uv run market chart 2330 --bars 60          # PNG，預設含 BB + RSI + MACD + ADX，Read 路徑後直接看圖
uv run market chart 2330 --bars 60 --indicators none  # 只看乾淨 K 棒
uv run market candles 2330 --bars 60        # OHLC JSON，需要算具體數值時用

# 量化雷達（盤後才跑）
uv run market screener --strategy momentum
uv run market screener --strategy momentum --no-enrich

# 帳戶 / watchlist
uv run python -m tw_trader.cli account
uv run python -m tw_trader.cli watchlist

# 情緒 / 新聞（config 路徑相對於 <SKILL_ROOT>，cd 後可省略）
uv run web-reader config/sources.tw.yaml --tags=sentiment
uv run web-reader config/sources.tw.yaml --tags=tw,macro
uv run web-reader config/sources.tw.yaml --tags=research

# 更新（agent 專用，透過暫存檔）
uv run python -m tw_trader.cli watchlist-update --file tmp/update_item.yaml
uv run python -m tw_trader.cli journal-add --file tmp/journal_entry.yaml
uv run python -m tw_trader.cli doc-add <DATA_ROOT>/account/research/{filename}.md
```

Markdown（brief / 個股研究）直接 Write，寫完一律 `doc-add`：
- Brief 草稿：不含 HHMM 的檔名，`doc-add` 會 rename 成 `brief-{HHMM}`
- 個股/主題：`{date}-tw-{symbol_or_theme}.md`，`doc-add` 只補 `created_at`
- Brief frontmatter：`date` / `session` / `screener_source`（`created_at` 不要手填）
- 生命週期：`doc-add` 後就算定稿；新情勢另寫 draft 再 `doc-add`
- `screener_source` 指到 `<DATA_ROOT>/account/screener/{date}.json`；Phase 1 跳過則留空並註明

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
- **不設 A 點，不寫進場訊號**：本 skill 是動量交易，進場是 TRADING 端 agent judgment，整合 thesis / regime / catalyst / 相對強弱 / 集中度當下做決策，不預先寫死訊號。
- **Research 只寫 thesis + invalidation_signals + stop**：thesis 描述「為什麼是這檔」與催化劑日曆；invalidation_signals 寫具體可執行的死亡條件（自動觸發出場）；stop 是風控價位。其他都交給 TRADING agent 在當下判斷。
- **嚴禁直接讀寫結構化 YAML**：`watchlist.yaml` / `journals/*.yaml` 必須透過 `tmp/` + CLI；markdown 可直接 Write，寫完 re-read 確認可解析

## 主流程

### Phase 0：讀上下文 + Regime + 預檢

**讀**：`strategy.md`、`watchlist.yaml`、近 3 日 journal、`cli account`、`cli watchlist`（同時讀 `brief.template.md` 作為 Phase 5 參考）

**Regime 判斷**：跑 `uv run market overview`。

`benchmark_quote` 提供今日 TWII 收盤價與漲跌幅（盤後為同日資料，盤中為 T-1）。
`benchmark_metrics` 提供：
- `sma_20`：TWII 20 日均線
- `adx_14`：趨勢強度
- `dist_to_sma20_pct`：今日收盤距 20MA 的百分比（正 = 站上，負 = 跌破）

寫入 journal.notes：
- TWII 現價、`dist_to_sma20_pct`、`adx_14`、當日漲跌幅
- Regime 判定（`range` / `uptrend` / `melt_up`，依 strategy.md Regime 表）+ 一句話描述（例：「`melt_up`，站上 20MA +8.9%，ADX 26，連三日強勢多頭」）
- 與前一輪比較：變化 / 無變化 / 明顯惡化（自由敘述）

**預檢**：對每個 watchlist 標的：
- 現價相對 thesis 寫入時的基準價 >10% → 強制重跑個股研究（thesis 已 stale）
- `evaluation.invalidation_active=true` **且為盤後** → 本輪移除
- `evaluation.invalidation_active=true` **但為盤中** → 標記「待盤後確認」，**不移除**
- 其他狀況交棒 Trading 做整合 judgment（沒有預計算的進場 gate）

**盤中分支**：盤中 flow 到此結束，寫 journal（簡短 entry 記 regime + 預檢），交棒 `TRADING_TW.md`。

以下 Phase 1-5 僅在盤後或 regime 明顯惡化時執行。

### Phase 1：量化雷達（盤後）

跑 `uv run python -m tw_trader.cli screener-snapshot --strategy momentum`（CLI 自動寫入 `<DATA_ROOT>/account/screener/{today}.json`，stdout 印出絕對路徑與完整結果；盤後補拍可加 `--suffix postclose`）

Screener 自帶技術指標（RSI, ADX, 量比）+ 籌碼（外資/投信連買、融資）：
- 原始輸出固定寫入 `screener/{date}.json`，brief 只引用 `source` 與 `highlights`
- 記錄上榜名單，標注 watchlist 已有 vs 新面孔
- 優先關注：ADX > 20 + 外資或投信連買 ≥ 3 日的新面孔
- **名單鎖定**：Phase 1 固定後，後續 Phase 不得追加

### Phase 2：散戶情緒

跑 `uv run web-reader config/sources.tw.yaml --tags=sentiment`

- 整理：PTT 有沒有 watchlist 以外的新 ticker 被反覆提到？整體偏多/偏空？
- 高 push 文章（≥30 push）讀原文：`uv run web-reader "<url>" --format=md`
- 如果是「盤中/盤後閒聊」長串：(1) 先讀首段判斷背景；(2) 聚焦最近 60-90 分鐘；(3) 只記重複提到的 ticker/主題。沒有重複 → 「情緒噪音，不形成候選」。
- 記 1-3 條結論，留到 Phase 4 彙整

### Phase 3：新聞與宏觀

跑 `uv run web-reader config/sources.tw.yaml --tags=tw,macro`

- 整理：市場主線、次主線、重要宏觀催化
- 輔以 `market overview`：驗證新聞敘事是否被真金白銀買單
- 記下結論，不和 Phase 2 混

### Phase 4：交叉比對

三方資料（Phase 1 量化、Phase 2 PTT、Phase 3 新聞）交叉比對：

- **三方共振**（screener + PTT + news）→ 最高優先，做個股研究
- **雙重確認**（screener + news，或 screener + PTT）→ 加 watchlist，視情況做個股研究
- **有故事但動能未到**（news + PTT，screener 未上榜）→ watchlist 觀察
- **screener only** → 可能假訊號，journal 記一筆不加 watchlist
- **單一來源** → 跳過
- **Phase 1 跳過（非盤後）** → 不得僅憑 Phase 2/3 加入 watchlist，最多 journal observation

**若 Phase 0 regime = `range`** → 本輪不新增 watchlist，只做既有 thesis review。

### Phase 5：Watchlist 更新 & 個股研究 & Journal

**Watchlist status 兩態**：
- `watch`：thesis 累積中。Trading 每輪掃整個 watchlist，對每檔做 judgment。
- `hold`：已持倉。狀態由 sweep 自動同步（成交時 watch → hold；出場時 hold → watch）。

沒有 `ready` 狀態，沒有預計算的進場 gate。Trading 端 agent 直接掃所有 watch 標的，整合 analysis report、thesis、regime、相對強弱、集中度等做進場判斷。

1. **更新 Watchlist**：
   - 新增/修改寫入 `tmp/watchlist_update_{symbol}.yaml`，執行 `cli watchlist-update --file ...`
   - 移除直接 `cli watchlist-delete`，並在 journal 記錄原因
   - **`invalidation_signals` 寫作原則**：
     - 必須是具體可執行的數值表達式或 `technical_config.yaml` 已定義的 expression 名稱（如 `close < 2100`、`price_below_sma_50 and macd_histogram_negative`）
     - 任一表達式達 → `invalidation_active=true` → 自動觸發 Trading 端清理
     - 寫的時候問自己：「這個條件達成時，我絕對要殺掉這個 thesis 嗎？」是 yes 才寫
     - 不寫進場訊號——進場是 agent 當下判斷，不是預設規則
   - **降級邏輯**：thesis 動搖 → 改 notes 註明「降級觀察」；thesis 失效 → 直接 delete
2. **個股交易研究**：以下情況派 sub-agent 跑子流程：
   - 新標的加入 watchlist
   - thesis 明顯改變（>10% 強制更新或關鍵條件變化）
   - 持倉出現重大催化或風險
   - 從 `watch` → `hold` 由 sweep 自動處理，**不需要新研究**
3. **市場簡報（Brief）**：
   - Write 到 `<DATA_ROOT>/account/research/{date}-tw-brief-draft.md`，結構照 `<SKILL_ROOT>/templates/research/brief.template.md`
   - frontmatter 必填 `date` / `session` / `screener_source`
   - **Brief 必含 Regime 區塊**（Phase 0 的判斷 + 一句話描述）
   - 跑 `cli doc-add ...`，rename 成 `brief-{HHMM}` 並補 `created_at`
   - `doc-add` 後 re-read 確認可解析
4. **Journal**：
   - 寫入 `tmp/journal_entry_{date}.yaml`，執行 `cli journal-add --file ...`

### 子流程：個股交易研究

1. 讀 `<SKILL_ROOT>/templates/research/template.md`
2. 單一主標的為核心，不重做整體市場掃描
3. 按 template 多輪尋找資料：
   - 新聞：先 `--tags=tw,macro`，再 `--tags=research`（分兩次）
   - 單篇深挖：`uv run web-reader "<url>" --format=md`
   - 優先 1 個月內資料
   - 至少比較 3-5 檔同族群/同題材
   - 主標不是最佳 → 結論指出更值得追蹤的股票
4. **thesis 必含**：核心論述、`invalidation_signals`（thesis 死亡訊號）、stop（風控價位）、催化劑日曆。**不含 A 點，不含進場訊號**——進場由 TRADING agent 整合判斷，當下用市場價執行。
5. 建立研究檔：`{date}-tw-{symbol}.md` 或 `{date}-tw-{theme}.md`
6. 發佈：`cli doc-add ...`

## 下一步

研究流程結束後，執行 `prompts/RESEARCH_TW_REFLECT.md`。
