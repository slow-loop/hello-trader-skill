# Strategy Idea: ICT Liquidity Sweep Reversion

## 適用 Regime
reversal, ranging

## 核心概念
只做可由 OHLCV 驗證的 liquidity sweep，不引入 block trade / iceberg 敘事。
價格先掃掉前低流動性，再快速收回前低上方，視為 stop hunt 後的反轉訊號。

## 進場條件
- 辨識最近 swing low
- 當前 candle：
  - low 跌破 swing low
  - close 收回 swing low 上方
- RSI < 45
- Volume > 20-period 平均
- 可加一個簡單 regime filter：
  - ADX < 30
  - 或 close >= EMA 50

## 出場條件
- 價格回到最近區間中線
- 或 RSI > 60
- 或 close 跌回 EMA 50 下方

## 風控
- Stoploss: -3% to -4%
- ROI: quick mean-reversion exit, not trend holding
- 不做加碼，不做複雜多段目標

## 備註
- MVP 只做 bullish sweep
- MVP 不做 order block / FVG / CHOCH 疊加
- MVP 不碰真正 block trade，因為目前資料只有 OHLCV
- 先確認這個基本 sweep 定義是否有樣本與 edge，再決定要不要加其他 ICT 元件
