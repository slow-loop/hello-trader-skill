# 台股交易教訓

這份檔案是 local-first workspace 的共用上下文。
後續由 agent / CLI / backend API 共同維護，但 source of truth 仍是這個檔案。

## Watchlist 原則

- thesis 只寫核心催化與主要技術判斷，不寫流水帳。
- trigger 要能執行，最好帶價位、量能或結構條件。
- invalidation 必須明確，避免只寫模糊敘述。
- `trigger_conditions` / `invalidation_conditions` 只能用數值表達式（如 `adx_14 > 25`）或已在 `technical_config.yaml` 定義的 expression 名稱，不能自創名稱，否則 evaluator 會出錯。

## 目前策略紀律

- 大盤偏弱時，不主動追高，只做最強主線與最乾淨結構。
- 單一標的部位不超過總資金 30%。
- 高波動標的的初始停損不能過窄，至少參考 ATR。

## 進場前必看：相對強弱

- 大盤強勢日（漲幅 > 1%），若標的漲幅明顯低於大盤（落差 > 0.5%），視為相對弱勢，不追；等待結構修復後再評估。
- 重大 catalyst 日（法說、財報、重大新聞），若量能未放大（volume_ratio < 1.5x），代表利多已提前 price in，不追。
- 相對強弱是進場前的必要條件，優先於 MACD / RSI 等技術指標。
