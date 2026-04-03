# Strategy Idea: Mean Reversion Bollinger Bands

## 適用 Regime
ranging

## 核心概念
價格觸及 Bollinger Band 下軌時買入，觸及上軌時賣出。適合震盪盤。

## 進場條件
- 價格收在 BB 下軌以下
- RSI < 30（超賣確認）
- ADX < 25（非趨勢盤）

## 出場條件
- 價格回到 BB 中軌（SMA 20）
- 或 RSI > 70

## 風控
- Stoploss: -3%（因為均值回歸，止損要緊）
- ROI: 2% @ 60 min, 1% @ 120 min

## 備註
均值回歸在趨勢盤會大虧，ADX 過濾非常重要。
可以結合 volume profile 或 support/resistance 確認。
BB 參數可調：(20,2) 標準，(20,1.5) 更敏感。
