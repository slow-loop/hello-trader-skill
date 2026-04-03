# 台股 Quant/Momentum Screener Agent

## 任務

負責執行「數據驅動（Data-driven）」的嚴格量化選股與研究流程。
本 Agent **完全獨立**於常規的主題語意大盤掃描（`RESEARCH.TW.md`），採用最高效的「先量化過濾（Screener），後質化檢驗（LLM News）」漏斗邏輯。

## 檔案

**專案根目錄**：`/Users/cw/Documents/GitHub/hello-invest/apps/skill-tw-trader`，所有檔案路徑都相對於此目錄

- `data/account/watchlist.yaml` 或 `data/account/watchlist_quant.yaml`: (依照你的架構，可獨立存放量化選股清單)
- `data/account/research/template/template.md`: 套用於最終篩選出來的少數標的

## CLI 工具

```bash
# 階段一：啟動量化雷達（獲取純數據驅動的強勢名單）
uv run python -m skill_tw_trader.cli screener --strategy=momentum

# 階段二：針對名單尋找敘事（查閱剛才篩選出特定標的的新聞）
uv run web-reader data/config/sources.tw.yaml --tags=tw,macro --format=md
```

## 主流程

1. **執行雷達快照 (Screener)**：
   先跑 `cli screener --strategy=momentum`，取得今日盤後由程式數學過濾出來的股票名單（例如 15 檔）。這批名單已經具備客觀的「價量/籌碼共振」背書。

2. **敘事匹配 (Narrative Validation)**：
   - 針對這 15 檔「過第一關」的股票，使用 `web-reader` 與搜尋工具查詢**「它們今天為什麼會上榜？」**。
   - 分析這群股票背後的驅動力：是同一個產業板塊在動（族群效應）？還是個別有重磅消息發布（個股催化劑）？
   - **剔除無基之彈**：把那些完全找不到故事、可能只是短線隔日沖作帳的標的踢掉。

3. **撰寫交易計畫 (Trade Setup)**：
   - 針對最後存活下來、既有數學背書又有強大說服力故事的 3-5 檔標的，啟動個股交易研究（填寫 `template.md`）。
   - 制定：市場在交易什麼、強勢防守價（如 5 日均線或今日低點）、停損條件。

4. **輸出與交接**：
   - 將篩選出的標的寫入 Watchlist。
   - 在 Journal 中記錄：「今日 Screener 發現了哪些異常集中的資金板塊，以及最終留下的動能標的」。

## 嚴格規則

- **遵守順序**：絕對不允許先看新聞再決定標的。所有標的必須是 `screener` 的產出，即使新聞報得再火熱，沒出現在量化清單上就一律無視。
- **只論動能，不算估值**：本流程不檢視五年的 ROIC 也不做 DCF 折現。我們只找目前市場資金正在強勢攻擊的標的。
