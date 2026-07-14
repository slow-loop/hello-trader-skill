# 台股完整分析 Agent

## 任務

給定一個台股標的（symbol）或產業主題，產出一份整合四個維度的完整分析報告：**產業鏈與競爭格局、籌碼面、市場輿情、基本面與估值**。

此流程用於「深度個股/主題調查」，與日常動能 Research（`RESEARCH_TW.md`）分離。觸發時機：使用者明確要求「完整分析」「深度調研」，或標的被考慮列為長線核心重倉前。

標的可以是單一個股，也可以是產業/主題（例如「CoWoS 先進封裝」）。各子任務依標的類型自行判斷分析範圍，不強制模式。

## 檔案

`<SKILL_ROOT>` / `<DATA_ROOT>` 定義見 `SKILL.md`「工作目錄」。

- `<SERENITY_SKILL_ROOT>`：serenity-skill 所在路徑（例：`../serenity-skill`，一個獨立 repo），用於任務 A。若找不到，向使用者詢問路徑，或跳過任務 A 並在報告中註明原因。
- `<DATA_ROOT>/account/research/{YYYY-MM-DD}-tw-{symbol_or_theme}-full.md`：整合報告輸出地。
- 各子任務可先各自產出中間檔案（同資料夾，檔名加任務代號後綴），方便追溯，非必要。

## 四個子任務

### 任務 A：產業鏈與競爭格局

交給 **serenity-skill** 執行：讀取 `<SERENITY_SKILL_ROOT>/SKILL.md`，依其方法論對該標的（market=Taiwan）跑一次分析。

不要把 serenity-skill 的內容複製或改寫進本檔案，直接讀取並照做即可——serenity-skill 之後更新，本流程自動跟上，不需要維護兩份方法論。

### 任務 B：籌碼面

用 tw-trader 既有 CLI：

```bash
cd <SKILL_ROOT> && uv run market analysis {symbol}
cd <SKILL_ROOT> && uv run python -m tw_trader.cli watchlist   # 若已在 watchlist
```

重點：外資/投信/自營商買賣超趨勢、融資融券變化、量比。判斷是真金白銀進場，還是量能背離、純題材炒作。

### 任務 C：市場輿情

```bash
cd <SKILL_ROOT> && uv run web-reader config/sources.tw.yaml --tags=sentiment
```

針對該標的過濾，PTT/社群若反覆提及需讀原文。只做「情緒線索」，不單獨構成結論——依 serenity-skill evidence-ladder 的 weak evidence 原則處理，弱證據須有更強來源交叉驗證才能採信。

### 任務 D：基本面與估值

沿用 `RESEARCH_DD_TW.md` 的「財務體質與獲利真實性」與「估值與市場預期差」兩段（原文第 3、4 點）。業務模式與產業鏈段落（原文第 1、2 點）略過——已由任務 A 覆蓋，避免重複。

## 整合報告

四個子任務完成後，寫一份整合 markdown，存到 `<DATA_ROOT>/account/research/{date}-tw-{symbol_or_theme}-full.md`，結構：

1. **結論摘要**：一段話——值不值得繼續研究/建倉，為什麼。
2. **產業鏈與競爭格局**（任務 A 輸出）
3. **籌碼面**（任務 B 輸出）
4. **市場輿情**（任務 C 輸出）
5. **基本面與估值**（任務 D 輸出）
6. **綜合風險與失效條件**：四個任務的風險交叉整理，去重，寫成具體可驗證的條件（不寫空泛的「有風險」）。
7. **下一步追蹤清單**：2-3 季內必須死盯的具體指標與事件（財報日、法說會、月營收公佈日等）。

報告禁止空泛的逐條列點，用具體資料與來源支撐論點，保持專業、直白、去 AI 腔的風格。
