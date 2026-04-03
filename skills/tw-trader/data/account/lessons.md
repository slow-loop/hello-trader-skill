# 台股交易教訓

這份檔案是 local-first workspace 的共用上下文。
後續由 agent / CLI / backend API 共同維護，但 source of truth 仍是這個檔案。

## Watchlist 原則

- thesis 只寫核心催化與主要技術判斷，不寫流水帳。
- trigger 要能執行，最好帶價位、量能或結構條件。
- invalidation 必須明確，避免只寫模糊敘述。

## 目前策略紀律

- 大盤偏弱時，不主動追高，只做最強主線與最乾淨結構。
- 單一標的部位不超過總資金 30%。
- 高波動標的的初始停損不能過窄，至少參考 ATR。
