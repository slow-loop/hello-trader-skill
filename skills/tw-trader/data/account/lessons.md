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

## 工具可用性

- 每次 skill 執行前先跑 `uv run market quote 2330` 確認 Fugle API 可用性。若返回 ValueError / failed to fetch，先排查 FUGLE_API_KEY env var（根因：`load_dotenv(override=False)` 不覆蓋空字串，需確保 .env 有效且 market-core 載入 override=True）。API 失效期間不以 watchlist 快照替代 market analysis 作為進場依據。

## 盤中 vs 盤後研究的角色

- 盤中 9:00 呼叫 screener 只能反映 T-1 盤後數據，若前一交易日已跑過盤後研究，本輪 Phase 1 實質資訊不變，應視為延續，不重複挖掘新名單。
- 盤中研究的價值在「驗證盤後結論是否仍有效」：量比是否延續、trigger 價位是否守住、大盤強弱是否反轉；新標的正式納入 watchlist 仍留到盤後。
- Watchlist >10% 強制更新的判斷，盤中應以 `market quote` 的即時價計算，不是用前一日收盤。
