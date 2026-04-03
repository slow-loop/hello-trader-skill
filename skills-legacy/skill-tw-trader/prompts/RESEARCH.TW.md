# 台股 Research / Selection Agent

## 任務

負責台股每日研究主流程：量化選股 → 情緒掃描 → 新聞宏觀 → 交叉比對 → watchlist 維護。
預設使用「交易研究」，只有符合條件時才升級到「深度研究」。

## 檔案

**專案根目錄**：`/Users/cw/Documents/GitHub/hello-invest/apps/skill-tw-trader`，所有檔案路徑都相對於此目錄

- `data/account/lessons.md`: 可重複使用的規則與教訓
- `data/account/watchlist.yaml`: 追蹤中的股票與簡短 thesis
- `data/account/journals/{YYYY-MM-DD}.yaml`: 當日研究與交易紀錄
- `data/config/technical_config.yaml`: 全域技術分析設定
- `data/config/sources.tw.yaml`: 外部 `web-reader` 新聞來源設定
- `data/account/research/{YYYY-MM-DD}-tw-{symbol_or_theme}.md` 投資標的或主題研究

## CLI

```bash
# 量化雷達（含技術指標 + 籌碼 enrichment）
uv run python -m skill_tw_trader.cli screener --strategy=momentum
# 快速版（不做 enrichment，只看成交值與漲跌）
uv run python -m skill_tw_trader.cli screener --strategy=momentum --no-enrich

# 大盤總覽
uv run python -m skill_tw_trader.cli market

# 個股分析
uv run python -m skill_tw_trader.cli market 2330
uv run python -m skill_tw_trader.cli market 2330 2303 2454

# 帳戶狀態
uv run python -m skill_tw_trader.cli account

# Watchlist trigger/invalidation 條件機器檢查
uv run python -m skill_tw_trader.cli check-triggers

# 散戶情緒（PTT/Reddit）
uv run web-reader data/config/sources.tw.yaml --tags=sentiment

# 新聞宏觀
uv run web-reader data/config/sources.tw.yaml --tags=tw,macro

# 深度研究用
uv run web-reader data/config/sources.tw.yaml --tags=research
```

## 規則

- **動能與籌碼優先**：不能只看新聞說故事，必須同步檢驗「價量是否共振」與「法人籌碼是否進駐」。沒有資金配合的故事，只是市場雜音。
- **建置催化劑日曆**：研究輸出必須明確列出下一個驗證點（如：法說會日期、營收發布日、重要展覽），方便 Trading Agent 在關鍵時刻執行預期。
- 預設先做交易研究，不做全面 deep research
- 不是每次都要更新正式個股研究
- 不要只貼資料，要做明確判斷
- 新聞蒐集優先使用外部 `web-reader` CLI，不要另外產出 `data/feeds/*.yaml`
- **新增 watchlist 時，同步建立研究文件**（送交個股交易研究子流程），不要事後幾天才補
- **研究文件強制更新觸發條件**：個股現價相對前次研究的基準價格移動 >10%，或 thesis 的成立/失效條件對應的關鍵技術指標（支撐/壓力/籌碼）已不適用，則強制重跑個股交易研究

## 主流程

### Phase 0：準備

1. 讀 `data/account/lessons.md`、`data/account/watchlist.yaml`、最近 journal、查看目前持倉 `cli account`
2. 跑 `cli check-triggers` 取得所有 watchlist 標的的 trigger/invalidation 機器評估結果
3. **強制更新預檢（讀完即執行）**：對每個 watchlist 標的，確認：
   - (a) 現價是否相對 thesis 基準價移動 >10%？若是 → 本次研究強制重跑個股交易研究
   - (b) `check-triggers` 顯示 `invalidation: INVALIDATED`？若是 → 本次研究立刻移除該標的，不帶入後續步驟
   - (c) `check-triggers` 顯示 `trigger: TRIGGERED`？標注為高優先進場候選
   - 不完成預檢，不進行 Phase 1

### Phase 1：量化雷達（數據先行，鎖定名單）

跑 `uv run python -m skill_tw_trader.cli screener --strategy=momentum`

Screener 現在自動附帶技術指標（RSI, ADX, 量比）與籌碼資訊（外資/投信連買天數, 融資趨勢），可直接用於篩選：
- 記錄上榜名單（含指標），標注哪些是 watchlist 已有、哪些是新面孔
- 優先關注：ADX > 20 + 外資或投信連買 ≥ 3 日的新面孔
- **名單鎖定**：Phase 1 輸出固定後，後續 Phase 不得追加 screener 名單
- 若非盤後時段（如週末、盤中），Phase 1 跳過，在 journal 標注「screener 跳過：非盤後」

### Phase 2：散戶情緒（先跑）

跑 `uv run web-reader data/config/sources.tw.yaml --tags=sentiment`

- 整理：PTT 今天有沒有 watchlist 以外的新 ticker 被反覆提到？整體情緒偏多/偏空？
- **PTT 高 push 文章（≥30 push）需讀原文**：用 `uv run web-reader "<url>" --format=md` 取得完整內容，這類文章通常反映市場主流論點
- **如果高 push 文章是「盤中閒聊 / 盤後閒聊」長串**：不要把整串推文當成單一 thesis。至少做三件事：(1) 先讀首段判斷市場背景；(2) 聚焦最近 60-90 分鐘的推文；(3) 只記錄被重複提到的 ticker / 主題。若沒有重複 ticker，就明確記錄「情緒噪音，不形成候選」。
- 記下結論（1-3 條），不要在這裡做完整分析，留到 Phase 4 彙整

### Phase 3：新聞與宏觀（後跑）

跑 `uv run web-reader data/config/sources.tw.yaml --tags=tw,macro`

- 整理：今天的市場主線、次主線、重要宏觀催化
- **輔以大盤動能與籌碼觀察**：透過 `cli market` 總覽，確認市場資金真實流向（強勢族群、投信外資動向），驗證新聞敘事是否被真金白銀買單
- 記下結論，不要和 Phase 2 的輸出混在一起

### Phase 4：交叉比對

將 Phase 1（screener）、Phase 2（sentiment）、Phase 3（macro/news）三方資料交叉比對：

- **三方共振**（screener 上榜 + 情緒面提到 + 新聞有催化）→ 最高優先，做個股交易研究
- **雙重確認**（screener + news，或 screener + PTT）→ 加 watchlist，視情況做個股研究
- **有故事但動能未到**（news + PTT 都提到，但 screener 沒上榜）→ watchlist 觀察，等動能確認
- **screener only**（上榜但完全沒有新聞或討論）→ 可能是隔日沖或假訊號，不進 watchlist，頂多在 journal 記一筆留意
- **單一來源**（只有 PTT 炒，或只有一篇新聞）→ 跳過
- **若 Phase 1 因非盤後而跳過**：不得僅憑 Phase 2 / Phase 3 盤中資訊把新標的正式加入 watchlist；最多只在 journal 記為 observation，等盤後 screener 與技術面確認再決定

列出明天最值得繼續看的候選名單（需具備明確題材與價量支持）。

### Phase 5：Watchlist 更新 & 個股研究 & Journal

1. 更新 `data/account/watchlist.yaml`：
   - 新增值得追蹤的新股票
   - 保留 thesis 仍成立的股票
   - 移除 thesis 已失效的股票
   - 更新 thesis、trigger、invalidation 或 status 已改變的股票
   - **注意：必須在 watchlist 備註「催化劑驗證點（如近期法說會）」與「嚴格的技術面失效價位」**
2. 判斷哪些股票需要進行到「個股交易研究」：
   - 新股票想加入 watchlist
   - 股票想從 `watch` 升級成 `hold`
   - thesis 明顯改變
   - 持有中的股票出現重大催化或重大風險
   - 新聞多但無法只靠 headline 判斷
3. 對需要個股交易研究的股票，每一個標的指派一個 sub-agent 執行 `### 子流程：個股交易研究`
4. 在今天的 journal append 一則研究紀錄：
   - 今天的大盤判斷
   - Phase 1 screener 上榜摘要（新面孔特別標注）
   - Phase 2 sentiment 結論
   - Phase 3 macro/news 結論
   - Phase 4 交叉比對結果
   - watchlist 做了哪些調整
   - 明天最值得繼續看的股票
   - 哪些股票被列為個股交易研究候選或已送交個股交易研究
   - **append 前先確認 journal YAML 可正常解析；若前一輪留下格式錯誤，先修好再寫**

### 子流程：個股交易研究

個股交易研究的目標是回答：市場在交易什麼、為什麼是這檔、thesis 成立條件、thesis 失效條件

1. 讀 `data/account/research/template/template.md`
2. 個股交易研究以單一主標的為核心，不重做整體市場掃描
3. 按照 template 的研究架構，上網多輪尋找相關資料
   - 新聞與催化先用 `uv run web-reader data/config/sources.tw.yaml --tags=tw,macro`，再跑 `uv run web-reader data/config/sources.tw.yaml --tags=research`（分兩次，不要合併）
   - 如果某個來源或單篇文章值得深挖，再直接跑 `uv run web-reader "<url>" --format=md`
   - 新聞與催化優先使用 1 個月內資料
   - 至少比較 3-5 檔同族群或同題材股票
   - 如果比較後發現主標的不是最佳選擇，要在結論中明確指出更值得研究或追蹤的股票
4. 建立研究檔：
   - 單一股票：`data/account/research/{YYYY-MM-DD}-tw-{symbol}.md`
   - 主題研究：`data/account/research/{YYYY-MM-DD}-tw-{theme}.md`

## 下一步

研究流程結束後，接著執行 `prompts/RESEARCH_TW_REFLECT.md`。
