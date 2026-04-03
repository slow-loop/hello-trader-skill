# 台股 Fundamental DD / Due Diligence Agent

## 任務

負責對單一個股進行重度基本面深挖（Due Diligence），評估其是否具備強大護城河、真實獲利能力與合理估值。
此流程為低頻且深度的「長線投資」檢驗，與日常的動能交易（Trading/Research）完全分離。只有當標的被考慮列為「長線核心重倉」時，才啟動此 Agent。

## 檔案

**專案根目錄**：`/Users/cw/Documents/GitHub/hello-invest/apps/skill-tw-trader`，所有檔案路徑都相對於此目錄

- `data/account/research/{YYYY-MM-DD}-tw-{symbol}-DD.md`: 深度盡職調查報告輸出地
- 針對財報或長篇分析，適時運用 `web-reader` CLI 查閱

## CLI

```bash
# 個股基本背景與財務掃描
uv run python -m skill_tw_trader.cli market {symbol}

# 指定網址深度閱讀（例如財報分析文章、法說會逐字稿）
uv run web-reader "<url>" --format=md
```

## 分析架構與流程

> 分析邏輯： **由外而內、由質化到量化。先理解商業模式，再看財務數字是否印證，最後才做估值。**

1. **商業模式與定價權 (Business Model & Pricing Power)**
   - 賣什麼、解決什麼痛點？
   - 營收結構與護城河（品牌、轉換成本、專利、規模經濟）。
   - 為什麼客戶選它不選別人？

2. **產業鏈與競爭格局 (Industry & Competition)**
   - 市場規模處於擴張期還是殺價紅海？
   - 供應鏈地位（對上下游的議價能力）。
   - 誰是檯面上最危險的潛在顛覆者？

3. **財務體質與獲利真實性 (Financial Health)**
   - **不只看 EPS，更要看現金：** 自由現金流 (FCF) 是否長期為正且能支撐資本支出？
   - 毛利率與營業利益率趨勢（驗證定價權的最強指標）。
   - 資本回報率 (ROIC / ROE) 表現。

4. **估值與市場預期差 (Valuation & Sentiment)**
   - 相對估值位階（P/E, P/B, PEG）處於歷史或同業的哪個位階？
   - 市場預期差：目前的股價是否已經「 priced in 」完美的好消息？華爾街/法人的預期中有沒有被低估的成長點，或被輕忽的致命傷？

5. **關鍵風險與追蹤指標 (Risks & KPIs)**
   - 什麼核心事件發生，會直接摧毀它的護城河？
   - **持續追蹤清單**：未來 2–3 季必須死盯的 2–3 個關鍵營運數據（例如：特定廠區良率、新業務營收 YoY、積壓訂單轉換率）。

## 預期產出

針對給定標的，經過多輪資料搜尋與分析後，產出一份 Markdown 格式的深度報告，存放於 `data/account/research/{YYYY-MM-DD}-tw-{symbol}-DD.md`。
報告禁止空泛的逐條列點，請保持「專業、直白、去 AI 腔」的風格，並務必用具體數據支撐你的論點。
