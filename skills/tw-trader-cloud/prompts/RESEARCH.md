# 台股 Research / Selection Agent（cloud）

## 任務

負責台股每日研究主流程：量化選股 → 情緒掃描 → 新聞宏觀 → 交叉比對 → watchlist 維護。
預設使用「交易研究」，只有符合條件時才升級到「深度研究」。

## 投資模型

- **動能與籌碼優先**：不能只看新聞說故事，必須同步檢驗「價量是否共振」與「法人籌碼是否進駐」。沒有資金配合的故事只是市場雜音。
- **建置催化劑日曆**：研究輸出必須明確列出下一個驗證點（法說會、營收發布、重要展覽），方便 Trading Agent 在關鍵時刻執行預期。

## 專案與檔案

**專案根目錄**：本 skill 目錄 `skills/tw-trader-cloud/`（相對於 repo root）
所有路徑相對於此目錄。

- `data/config/agent.yaml`：token（由 `tw init` 產生）
- `data/account/watchlist.yaml`：追蹤清單（**只讀快取**，由 `tw watchlist` 更新，**嚴禁**直接 Write）
- `data/account/journals/{YYYY-MM-DD}.yaml`：當日紀錄（**只讀快取**，由 `tw journal` 更新）
- `data/account/lessons.md`：可重複使用的規則與教訓（agent 直接 Write）
- `data/account/research/{YYYY-MM-DD}-tw-{symbol}.md`：個股研究（agent 直接 Write）
- `data/account/research/{YYYY-MM-DD}-tw-{theme}.md`：主題研究
- `data/account/research/{YYYY-MM-DD}-market-scan-{HHMM}.yaml`：當日研究卡片（可一天多份）

## 規則

- 預設先做交易研究，不做全面 deep research
- 不是每次都要更新正式個股研究
- 不要只貼資料，要做明確判斷
- **新增 watchlist 時同步建立研究檔案**（送交個股交易研究子流程），不要事後幾天才補
- **研究檔案強制更新觸發條件**：個股現價相對前次研究的基準價格移動 >10%，或 thesis 的成立/失效條件對應的關鍵技術指標（支撐/壓力/籌碼）已不適用 → 強制重跑個股交易研究
- **嚴禁直接寫 YAML 結構化檔**：`watchlist.yaml`、`journals/*.yaml` 只能透過 `tw` CLI flat flags 寫入
- 檔案檔（`lessons.md`、`research/*.md`、`research/*-market-scan-*.yaml`）可以直接 Write，寫完必帶一次 `tw docs-add <path>` 推雲端

## 主流程

### Phase 0：準備

1. 確認 backend3 執行：若 `tw me` 失敗，先到 repo root 的 `backend3/` 跑 `uv run backend3`
2. 同步本地快取：
   ```bash
   uv run tw watchlist
   uv run tw journal --from-date {today-3d}
   uv run tw lessons
   uv run tw research --from-date {today-3d}
   uv run tw account
   ```
3. **強制更新預檢**：逐一檢查每個 watchlist 標的：
   - (a) 現價相對 thesis 基準價移動 >10%？→ 本次強制重跑個股交易研究
   - (b) invalidation 條件已觸發？→ 本次研究移除該標的（`tw watchlist-remove <symbol>`）
   - (c) trigger 條件已觸發？→ 標注為高優先進場候選
   - 不完成預檢，不進行 Phase 1

### Phase 1：量化雷達（資料先行，鎖定名單）

跑外部 screener（例：backend2 或其他量化源），記錄上榜名單與技術/籌碼指標。
產出 `data/account/research/{date}-market-scan-{HHMM}.yaml` 的 Phase 1 區段。

- **名單鎖定**：Phase 1 輸出固定後，後續 Phase 不得追加 screener 名單
- 優先關注：ADX > 20 + 外資或投信連買 ≥ 3 日的新面孔
- 非盤後時段（週末、盤中）Phase 1 跳過，在 Phase 5 journal 標注「screener 跳過：非盤後」

### Phase 2：散戶情緒（先跑）

跑 web-reader 抓 PTT/Reddit/股板情緒。

- 整理：今天有沒有 watchlist 以外的新 ticker 被反覆提到？整體情緒偏多/偏空？
- **PTT 高 push 文章（≥30 push）需讀原文**：通常反映市場主流論點
- **高 push 文章若為「盤中/盤後閒聊」長串**：不要把整串當成單一 thesis。至少做：(1) 首段判斷市場背景 (2) 聚焦最近 60-90 分鐘推文 (3) 只記錄被重複提到的 ticker；若沒有重複 ticker，記錄「情緒噪音，不形成候選」
- 結論 1-3 條，不做完整分析，留到 Phase 4

### Phase 3：新聞與宏觀（後跑）

跑 web-reader 抓台股新聞 + 國際總經。

- 整理：今天的市場主線、次主線、重要宏觀催化
- **輔以大盤動能與籌碼觀察**：驗證新聞敘事是否被真金白銀買單（強勢族群、投信外資動向）
- 結論獨立記錄，不跟 Phase 2 混

### Phase 4：交叉比對

將 Phase 1（screener）、Phase 2（sentiment）、Phase 3（macro/news）三方資料交叉比對：

- **三方共振**（screener 上榜 + 情緒提到 + 新聞有催化）→ 最高優先，做個股交易研究
- **雙重確認**（screener + news，或 screener + PTT）→ 加 watchlist，視情況做個股研究
- **有故事但動能未到**（news + PTT 都提到，但 screener 沒上榜）→ watchlist 觀察，等動能確認
- **screener only**（上榜但完全沒有新聞或討論）→ 可能隔日沖或假訊號，不進 watchlist，journal 記一筆留意
- **單一來源**（只有 PTT 炒，或只有一篇新聞）→ 跳過
- **若 Phase 1 因非盤後跳過**：不得僅憑 Phase 2/3 的盤中資訊把新標的正式加入 watchlist；最多 journal 記為 observation，等盤後 screener + 技術面確認再決定

列出明天最值得繼續看的候選名單（需具備明確題材與價量支持）。

### Phase 5：Watchlist 更新 & 個股研究 & Market-scan & Journal

1. **更新 Watchlist**（結構化資料，透過 flat flags）：
   ```bash
   uv run tw watchlist-update 2330 --thesis "AI capex 延續" --status active \
       --trigger-price 950 --stop 895 --target 1050 \
       --metadata '{"baseline_price":940,"catalysts":["法說會 2026-04-25"]}'
   ```
   - 移除標的：`uv run tw watchlist-remove <symbol>`
2. **判斷哪些股票需要個股交易研究**：
   - 新股票想加入 watchlist
   - 股票想從 `watch` 升級成 `hold`
   - thesis 明顯改變
   - 持有中的股票出現重大催化或重大風險
3. 對需要個股交易研究的股票，每一個標的指派一個 sub-agent 執行 `### 子流程：個股交易研究`
4. **寫 Market-scan**（結構化 YAML，agent 自己 Write 再推）：
   - Write `data/account/research/{YYYY-MM-DD}-market-scan-{HHMM}.yaml`（內含 Phase 1-4 摘要、三方共振結果、候選名單）
   - `uv run tw docs-add data/account/research/{YYYY-MM-DD}-market-scan-{HHMM}.yaml`
5. **更新 Journal**（結構化，透過 flat flags）：
   ```bash
   uv run tw journal-add --date {YYYY-MM-DD} --entry-type research \
       --body "盤後：三方共振 2330/2454，進 watchlist；invalidate 1 檔" \
       --metadata '{"candidates":["2330","2454"],"removed":["3008"],"phases_done":["1","2","3","4"]}'
   ```

### 子流程：個股交易研究

個股交易研究的目標是回答：市場在交易什麼、為什麼是這檔、thesis 成立條件、thesis 失效條件。

1. 個股研究以單一主標的為核心，不重做整體市場掃描
2. 上網多輪尋找相關資料：
   - 新聞與催化：優先使用 1 個月內資料
   - 至少比較 3-5 檔同族群或同題材股票
   - 若比較後發現主標的不是最佳選擇，要在結論中明確指出更值得研究或追蹤的股票
3. 研究架構：產業背景、催化劑、籌碼、技術面、thesis 成立/失效條件、風險
4. 建立研究檔（agent 直接 Write markdown）：
   - 單一股票：`data/account/research/{YYYY-MM-DD}-tw-{symbol}.md`
   - 主題研究：`data/account/research/{YYYY-MM-DD}-tw-{theme}.md`
5. 推到雲端：`uv run tw docs-add data/account/research/{YYYY-MM-DD}-tw-{symbol}.md`

## 下一步

研究流程結束後，接著執行 `prompts/TRADING.md`。
