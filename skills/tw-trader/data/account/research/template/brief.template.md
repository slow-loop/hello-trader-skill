---
date: YYYY-MM-DD
session: post-close              # post-close | intraday | weekend
screener_source: data/account/screener/YYYY-MM-DD.json
---

# 盤後研究簡報 YYYY-MM-DD

## 01 Screener 亮點

Agent 精選 2-5 檔，說明挑選原因（ADX / RSI / 量比 / 籌碼 / 結構）。
標注 **新面孔** 或 watchlist 已有。原始表在 frontmatter `screener_source`。

- **{symbol} {name}** — {挑選原因}（新面孔）
- **{symbol} {name}** — {挑選原因}

若 Phase 1 跳過（非盤後 / 週末），改寫：`screener: 跳過（原因）`。

## 02 散戶情緒（PTT / Reddit）

- **整體**：{偏多 / 偏空 / 分歧}，{一句話補充}
- **熱門 ticker**：{symbol}（{主題}）— {備註}
- **Narratives**：
  - {重複被提到的論點}
- **結論**：{是否有獨立催生的新 ticker；若無就寫「情緒噪音，不形成候選」}

## 03 宏觀 / 新聞

- **大盤**：台股 {±X點} 至 {收盤}（{±X.XX%}），成交 {金額}
- **主線**：{今日主題}
- **次主線**：{輪動族群}
- **三大法人**：外資 {±X 億}、投信 {±X 億}、自營 {±X 億}

## 04 交叉比對

| 標的 | Screener | Sentiment | News | 判斷 | Tier |
|------|----------|-----------|------|------|------|
| {sym} {name} | {短句或 —} | {短句或 —} | {短句或 —} | {結論} | triple_resonance / double_confirm / story_only / screener_only / skip |

**明日關注**

- **{symbol} {name}** {NEW?} — {進場區、停損、等待條件}

## 05 Watchlist 調整

- **+ 新增** {symbol}（{status}）— {一句 thesis}
- **↑ 升級** {symbol} {from} → {to}
- **− 移除** {symbol} — {原因}
- **~ 更新** {symbol} — {what_changed}

（若當日無調整，寫 `無調整`。）

## 個股研究候選

送交 `子流程：個股交易研究` 的標的：

- {symbol}
- {theme}
