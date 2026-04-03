# Convergent Strategy

> Status: 目前不是 v2 已接線的 production profile。
> 這份文件暫時保留作為 research strategy，不能假設有對應的 `markets --profile convergent` 可直接使用。

## 任務

尋找強弱懸殊、機率會向合理區間收斂的市場，賺的是中間價差，不是最終結算。

## 這個 strategy 在做什麼

- 尋找市場現在太低估強方的情況
- 核心是機率收斂，不是押最後結果
- 這是一個有明確出場計畫的短中期策略

## 市場選擇

**優先：**

- 強弱差距很大的體育賽事
- 一面倒的政治事件
- 其他你能合理判斷「市場機率會先收斂」的事件

**排除：**

- 五五波市場
- 無法預估收斂時點的市場
- 流動性差、spread 太寬的市場

## 執行方式

1. 先從現有 working set 中人工挑出可能適合做收斂交易的市場，來源通常是：
   - `uv run python -m skill_poly_trader_v2 markets --profile sports --limit 50`
   - `uv run python -m skill_poly_trader_v2 markets --profile geo --limit 60`
2. 對有興趣的市場，再跑 `uv run python -m skill_poly_trader_v2 market --slug <slug>`
3. 做 WebSearch，確認實力差距、最新資訊、時間點與是否有明確催化
4. 形成 chosen outcome 的 probability
5. 如果市場明顯低估強方，才考慮進場
6. 先寫好目標出場價格或最晚出場時間，再決定要不要交易

## Edge 原則

- 價差通常至少要有 `5-10%`
- 沒有足夠價差，就不做
- 如果不能明確描述為什麼機率會在事件前收斂，就不做

## 持有與風控

- 絕對不要持有到開賽、開票或事件真正發生
- 價格接近合理值時可以提早出場
- 進場前先確認流動性與 spread；spread `> 5%` 原則上跳過

## Journal

- 這筆交易標註 `[convergent]`
- 把調查筆記寫在 `Research`
- 把結論寫在 `Analysis`
- 寫明目標出場價格或最晚出場時間
