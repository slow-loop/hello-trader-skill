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
- **同族群部位合計 ≤ 40% 帳戶**（如 ABF、PCB、散熱單一族群）；
  **同主線（如 AI 伺服器）合計 ≤ 60%**。避免單一主線崩跌時帳戶系統性風險。
- 高波動標的的初始停損不能過窄，至少參考 ATR。

## Sizing 紀律（避免「保守偏差」）

- 單筆風險預算 = 帳戶 × 1%。**若 thesis 強 + trigger 全達，sizing 不低於風險預算的 80%**。
  例：1M 帳戶 1% = 10,000 risk；停損距離 33.5 → 允許 298 股；至少買 240 股（80%）。
- **2026-04-21 教訓**：3189 trade thesis 強、trigger 完整，但只買 200 股（67% 預算），
  4/24 達 target 後 PnL 少了 33%。「保守一點」不該等於「執行打折」。
- 30% 單檔上限是 ceiling，不是 target；但若帳戶連續多週只用到 < 15%，需檢視是否 sizing 過嚴。

## 三種 Regime 的進場模式

### Regime A：震盪 / 弱勢（dist_to_sma20 < 5%，ADX < 20）
- 預設模式：**等 A 點回測量縮守穩**（pullback entry）
- 不追突破、不追漲停板
- 嚴守相對強弱規則

### Regime B：強勢趨勢（dist_to_sma20 5-8%，ADX 20-25，部分族群共振）
- A 點 pullback 仍為主，但允許「次日開盤量縮確認」作為替代 trigger
- Sizing 維持 normal（1% risk）

### Regime C：Momentum Melt-up（dist_to_sma20 > +6% AND ADX > 25 AND ≥ 3 族群共振 3 日內）
- **新增「Trend Follow」進場模式**：不等 A 點回測，允許 breakout follow
  - 觸發：標的為 screener triple-resonance 領頭羊 + 量能持續（VR > 1.2x 連兩日）
  - Sizing：normal 的 50%（風險預算 0.5%）—— 為 melt-up 末端反轉預留
  - Stop：1 ATR（比 normal 緊），停損觸發立即出
- **2026-04-21~24 教訓**：那週 TWII dist_to_sma20 從 +5% → +10.26%，2454 三漲停從未回測，
  「等 A 點 2000-2050」的紀律導致 100% 錯失 +16.5% 的 leader。
- Melt-up 末端越延伸風險越高，故 sizing 自動降半 + 停損自動收緊。

## 進場前必看：相對強弱

- 大盤強勢日（漲幅 > 1%），若標的漲幅明顯低於大盤（落差 > 0.5%），視為相對弱勢，不追；等待結構修復後再評估。
- 重大 catalyst 日（法說、財報、重大新聞），若量能未放大（volume_ratio < 1.5x），代表利多已提前 price in，不追。
- 相對強弱是進場前的必要條件，優先於 MACD / RSI 等技術指標。

## 工具可用性

- 每次 skill 執行前先跑 `uv run market quote 2330` 確認 Fugle API 可用性。Fugle 失敗會把原生 exception 冒到 CLI（HTTP 狀態碼 / rate-limit / auth 訊息可見），依訊息排查。
- `cli watchlist` 的 `context_snapshot` 走 market-core 即時 analyze 路徑，等同 `market analysis <symbol>`，可直接作為進場依據（不是靜態快照）。

### Fugle 失效 = skill 暫停（嚴格，no fallback）

market-core 對 TW 個股的 `get_quote` / `get_bars` 強制要求 Fugle，失敗即 raise。
**這是 by design**：yfinance 個股資料 T-1 延遲、成交量不一致、`prev_close` 欄位不可靠，
**「看似有效但內部不一致的資料」比「沒資料」更危險**——前者會默默引導出錯誤決策。

**規則：Fugle 不可用 → skill 整輪 SKIP，等用戶處理。**

- **不**用 `yf.download` 抓個股資料當替代——即使「只是研究用」也不行
- **不**從 `market overview.benchmark_quote` 的 `prev_close` / `change_pct` 推算「漲跌」
  （那是 yfinance 內部欄位，可能與真實前一交易日收盤不一致）
- **不**降級到「歷史快照」、「PTT 推測」、「分析師文章倒推」這類 workaround
- 在 journal 寫一條 SKIP：`"Fugle 不可用，本輪整輪 SKIP，待用戶處理 API key / 等下個交易日"`
- 等用戶決定（修 API key、改用其他標的、或接受暫停）

**2026-04-26 教訓**：用 `yf.download` 抓 4/24 個股收盤做 watchlist 複審 + 用 `market overview` 的
yfinance prev_close 推算「TWII 4/25 +2.98%」，結果 prev_close 37,805 ≠ 4/23 真實收盤 37,714，
整個簡報的「4/25」標註全錯（實際是 4/24）。**根因就是繞過 Fugle 用 yfinance**——
不是「沒驗證日期」，後者只是症狀；只要走 Fugle 路徑（拿到準確資料 or 拿到 error），
就不會出現「+2.98% 看起來像今天的數字其實是內部欄位拼湊」這種陷阱。

### 週末 / 休市期間的允許動作（不需要新市場資料）

Fugle 不可用、市場收盤時，skill 仍可做的純靜態 review：

- 讀既有 research docs、journals、watchlist.yaml 文字內容
- 移除已在前一交易日 Fugle-confirmed invalidation 的 watchlist 項目
  （例：2026-04-26 移除 3450 是依據 4/23 Fugle-confirmed 收盤 333.5 < 350，不是依據週末 yfinance）
- 補齊既有 watchlist 項目的 thesis / trigger / invalidation 文字
- 寫 reflection、更新 lessons、整理 research docs

**不可做**：跑 `market overview`、`market analysis <個股>`、`market screener`、
任何依賴即時或最近收盤行情的「Phase 1 量化雷達 / Phase 0 預檢」。
這些一律延到下一個 Fugle 可用的交易日盤前 / 盤後。

> 註：`market overview.benchmark_quote` 內部走 yfinance 取 TWII，本身就是 fallback 路徑——
> 應視為與「個股 yfinance」同等不可信，除非確認其使用 Fugle IX0001 即時 feed。

## Python 環境

- `uv run` 在此 skill 需要 Python 3.13（onnxruntime 1.20.1 只有 cp313 wheel）。
  `.python-version` 已固定為 3.13；若遷移環境需確認此檔案存在。
  若 uv 報 "onnxruntime can't be installed" → 在 skill 根目錄新增 `.python-version = 3.13`。

## 停損 / 目標單的持倉管理

- `STOP_LOSS` 和 `TAKE_PROFIT` pending 單需透過 `sweep` 觸發，而 sweep 需要 Fugle 即時報價。
  Fugle 不可用期間（週末、API key 未設），pending 單**不會自動執行**——這是已知行為。
- Fugle 不可用期間，**不嘗試**用 yfinance 推測「target 是否已達」、「stop 是否已觸發」。
  下一次 Fugle 可用時，自動 sweep 會基於該時點的真實價格做正確判定，不需提前猜測。
- 若懷疑持倉已達 target / stop（從新聞、外部資訊推測），記在 journal「待 Fugle 確認」即可，
  不取消 / 不修改 pending 單，等 Fugle 可用後執行 `sweep` 看實際結果再決定。

## 盤中 vs 盤後研究的角色

- 盤中 9:00 呼叫 screener 只能反映 T-1 盤後數據，若前一交易日已跑過盤後研究，本輪 Phase 1 實質資訊不變，應視為延續，不重複挖掘新名單。
- 盤中研究的價值在「驗證盤後結論是否仍有效」：量比是否延續、trigger 價位是否守住、大盤強弱是否反轉；新標的正式納入 watchlist 仍留到盤後。
- Watchlist >10% 強制更新的判斷，盤中應以 `market quote` 的即時價計算，不是用前一日收盤。
