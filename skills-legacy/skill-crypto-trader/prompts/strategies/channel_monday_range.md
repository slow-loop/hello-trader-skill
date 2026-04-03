# Strategy Idea: Channel Monday Range Reversion

## 適用 Regime
ranging

## 核心概念
只在明確區間盤做多下緣反彈，不預測突破方向。
用本週一的 early range 當錨點，價格回踩週初低點或 rolling channel 下緣時進場，
只吃快速回補到區間中線的小段。

## 進場條件
- 市場為區間盤：
  - ADX < 25
  - 價格仍在 rolling channel 內，未向上或向下有效突破
- 價格接近以下任一支撐：
  - Monday range low
  - rolling channel lower band
- RSI < 40
- Volume > 0

## 出場條件
- 價格回到 channel mid
- 或價格回到 Monday range midpoint
- 或固定小 ROI 快速止盈

## 風控
- Stoploss: -2% to -3%
- ROI: fast take profit, avoid long holding
- 如果價格有效跌破 channel low / Monday low，不加碼、不攤平

## 備註
- MVP 先做 BTC/USDT
- MVP 先用 1h 判斷 range，15m 找進場
- 核心不是抄底，而是只交易已確認區間內的下緣反彈
- 一旦 breakout confirmed，就停止均值回歸邏輯
