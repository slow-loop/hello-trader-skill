# Explore Factor

任務：從一個假設產出新 factor，驗證有沒有 alpha。

## 流程

### 1. 寫下假設

一句話，必含：**資料可得性 + 方向性 + 時間尺度**。

範例：
> 「財報 beat 後隔日跳空 + 三日內守住 50MA → 未來 20 日有 post-earnings drift」
> 資料：yfinance earnings、日線 OHLC；方向：long；時間尺度：20 天

不夠具體就停下來，先想清楚。

### 2. 寫 factor 函式

路徑：`libs/market-core/src/market_core/factors/catalog.py`

規格：
- 用 `@register(factor_id, category=..., bias_default=..., confidence_base=..., requires=[...])` 裝飾
- 輸入：feature DataFrame（vectorized）或 Series（single row）
- 輸出：`FactorOutput(triggered, score, bias, confidence, notes)`
- Score 範圍 `-1 ~ +1`，正值多頭、負值空頭
- 需要的 feature column 不在 `features.py` → 先擴充 features.py

寫完 `uv run factor list` 確認 factor 出現在清單。

### 3. 跑單因子 IC

```bash
uv run lab factor-ic <factor_id> --universe sp500 --start 2020-01-01 --end 2024-12-31
```

結果寫入 `data/experiments/factor_ic_{date}_{factor_id}/`。

### 4. 判讀 IC

閾值（保守）：
- |IC| < 0.03：訊號太弱，棄或 merge 進其他 factor
- |IC| 0.03 ~ 0.05：邊緣，需要與其他 factor 共振才用
- |IC| 0.05 ~ 0.10：有 alpha，可獨立計分
- |IC| > 0.10：強訊號，檢查是否 overfitting（多跑幾段年份）

檢查：
- IC 正負號是否和 `bias_default` 一致？反指也要記錄
- Quantile return：Q5 vs Q1 差距明顯？還是只有尾端有用？
- Sample size > 5000？否則統計不穩

### 5. 回填 IC 到 registry

如果通過驗證，在 `@register(...)` 的 `ic={'sp500_daily': 0.08}` 欄位填入。手動改，不自動寫回。

### 6. Journal

在 `data/experiments/factor_ic_{...}/notes.md` 寫：
- 假設原文
- IC 結果摘要
- 判定：採用 / 棄用 / 待組合
- 下一步：進 strategy 組合，或繼續改 factor

## 禁忌

- **不要一次寫 5 個 factor**。一次 1 個，先驗證，再下一個
- **不要用未來函式**：feature 計算只能用當前 bar 之前的資料
- **不要過度擬合單一股票**：universe 至少 50 檔
- **不要偷看 test period**：out-of-sample 留一段絕不碰
