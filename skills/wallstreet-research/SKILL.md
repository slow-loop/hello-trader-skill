---
name: wallstreet-research
description: "個股或題材深度研究技能，整合華爾街投研標準與實時網路抓取能力"
---

## 任務

負責針對單一「個股」或「主題（題材）」，自主進行多輪資料查證，並產出符合「華爾街投研標準」的深度基本面與交易研究報告

## MCP Tools

- `mcp_web_reader_read_url_content`:
  - 讀取單一 URL 或 pseudo-URL
  - 支援網站與格式：
  - Standard Web: `https://example.com/news/article-1`
  - Google News (`gnews://`): `gnews://NVDA?period=30d&max=10`
  - Substack: `https://investmenttalk.substack.com/p/market-update`
  - Reddit: `https://www.reddit.com/r/stocks/comments/abc/nvda_analysis`
  - PTT: `https://www.ptt.cc/bbs/Stock/M.123456789.A.ABC.html`
  - CNYES: `https://news.cnyes.com/news/id/54321`
  - RSS / Atom / JSON: `https://example.com/feed.xml`
  - YouTube: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`

## 規則

1. **多輪查證，但要在時限內收斂**：先用 config 或 gnews 快速掃描，再挑最重要的文章深入閱讀。不要無限制開新輪搜尋。
2. **數據具體**：優先使用近 1~3 個月的資料。不確定的財務或營收數字請標註「資料未詳述」，嚴禁腦補發明數據或產品名稱。
3. **拒絕只看表面故事**：必須透過尋找多方來源的交叉比對，找出這家公司的「基本面是否印證」。估值永遠是最後一步。
4. **來源標註**：每個具體事實（數字、事件、指引）後方，必須附加上來源網址（Source URL）。
5. **來源數夠用即可開始寫**：目標是 6 則以上直接相關來源；若時間受限，至少要有 4 則高相關來源，且涵蓋公司/產業、宏觀/市場、情緒/交易三類。
6. **先完成報告，再補缺口**：先產出完整但保守的報告，不要把時間耗在 v1/v2/qa 多輪文件流程。

## 執行流程 (Steps)

### Step 1: 讀取研究框架 (Framework Alignment)
讀取 `references/wall-street-framework.md`

### Step 2: 資料收集 (Data Gathering)
進行有限輪次的搜尋與深度閱讀，收集足夠資訊後就開始撰寫：
1. 若需要先確認環境，呼叫 `web_reader_server_info`
2. 先呼叫 `read_url_content("gnews://{symbol_or_topic}?period=30d&max=8")`，快速取得近期相關新聞
3. 若主題適合台股或半導體供應鏈脈絡，呼叫 `read_config` 讀取 `/Users/cw/Documents/GitHub/hello-trader-skill/skills/tw-trader/data/config/sources.tw.yaml`
4. 從摘要中挑 3 到 6 個最關鍵的 URL，再用 `read_url_content` 讀全文，而不是只看摘要
5. 最多追加 1 輪更細的 query 或 URL 閱讀；若資訊仍不完整，就在報告中明說缺口，而不是無限搜索

### Step 3: 撰寫研究報告 (Drafting)
根據收集到的數據，依照 `wall-street-framework.md` 的架構，直接回覆 Markdown 報告
