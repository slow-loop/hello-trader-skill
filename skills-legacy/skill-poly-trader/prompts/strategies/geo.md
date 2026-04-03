# GEO Strategy

## 任務

掃描地緣政治、外交、軍事、央行政策這類有明確 resolution 標準的事件市場，尋找可以長線持有的 edge。

## 這個 strategy 在做什麼

- 尋找資訊不對稱帶來的錯價
- 重點不是短線價格波動，而是真實機率和市場價格的落差
- 通常是持有到市場結算，除非 thesis 改變

## 市場選擇

**優先：**

- 地緣政治 / 外交 / 軍事事件
- 選舉、政策投票、央行決策
- 其他 binary 且 resolution 清楚的事件市場

**排除：**

- 金融價格類（BTC、原油、黃金、股指）
- 體育
- 娛樂 / 頒獎 / 流行文化
- 多選項市場

## 執行方式

1. 先跑 `uv run python -m skill_poly_trader_v2 markets --profile geo --limit 60`
2. 對有興趣的市場，再跑 `uv run python -m skill_poly_trader_v2 market --slug <slug>`
3. 在判斷前先做 WebSearch，確認最新事件背景、時程、政策脈絡、後勤條件或民調訊號
4. 形成具體的 outcome probability
5. 計算 edge，再決定是否交易

## Edge 原則

- YES 方向通常至少要有 `> 1.5%` 的 edge
- NO 方向通常至少要有 `> 3%` 的 edge
- 如果 `NO` 已經到 `0.97+`，原則上視為 edge 太薄直接跳過；只有在極少數特例才值得再研究
- 如果只是模糊覺得市場太高或太低，不算 edge

## 持有與風控

- 預設是長線持有
- 不因價格波動而出場
- 後續風控交給主流程的持倉管理

## Journal

- 這筆交易標註 `[geo]`
- 把調查筆記寫在 `Research`
- 把結論寫在 `Analysis`
- 寫清楚 thesis 與市場錯價在哪裡
