# Strategy Idea: Trend EMA Cross

## 適用 Regime
trending_up, trending_down

## 核心概念
用 EMA 9/21 交叉捕捉趨勢轉折，ADX 過濾確認趨勢強度。

## 進場條件
- EMA 9 上穿 EMA 21（做多）
- ADX > 25（趨勢夠強）
- Volume > 20-period 平均（有量確認）

## 出場條件
- EMA 9 下穿 EMA 21
- 或 trailing stop

## 風控
- Stoploss: -5%
- Trailing stop: 2% positive, 4% offset

## 備註
最經典的趨勢策略之一。在震盪盤會反覆假突破，需要 ADX 過濾。
可以嘗試不同 EMA 週期組合（5/13, 8/21, 13/34）。
