# 台股 Research Reflect

這是一個 loop：研究 → reflect → 研究 → reflect → ...

每次 `RESEARCH.TW.md` 結束後執行這裡，完成後回到 `RESEARCH.TW.md` 開始下一輪

## 任務

回頭檢視剛才整個研究過程，自己找出問題，自己改

目標是讓下一次研究做得更好，不是讓這次看起來更完美

## 流程

### 1. 檢視

重新看一遍剛才的整個研究過程——從新聞掃描、市場判斷、watchlist 維護、到深度研究
自己找有哪些問題。不限範圍，不限數量

### 2. 紀錄問題

在當天 journal append 一筆 reflection：

```yaml
- at: "HH:MM"
  type: reflection
  problems:
    - "..."
  next:
    - "..."
```

`problems` 是你發現的問題。`next` 是你打算怎麼改。
append 前先確認當天 journal YAML 可正常解析；若損壞，先修格式再寫 reflection。

### 3. 改

直接改。能改的東西包括但不限於：

- `<DATA_ROOT>/account/strategy.md`
- `<DATA_ROOT>/account/watchlist.yaml`
- `<SKILL_ROOT>/templates/research/template.md`
- `<SKILL_ROOT>/config/technical_config.yaml`
- `<SKILL_ROOT>/config/sources.tw.yaml`
- `<SKILL_ROOT>/prompts/RESEARCH_TW.md`
- `<SKILL_ROOT>/src/` Python code
- `web-reader` Python code lives at https://github.com/w121211/hello-wagreader (clone separately if you need to read it)

一次只改你有把握的。不確定的先寫進 `next`，下次再處理

### 4. 紀錄改動

在同一筆 reflection 補上你實際改了什麼：

```yaml
- at: "HH:MM"
  type: reflection
  problems:
    - "..."
  changes:
    - "..."
  next:
    - "..."
```

## 原則

- 先看完再改，不要邊看邊改
- 同樣的問題如果之前出現過，這次就一定要改掉
- 改了什麼就記什麼，不要多寫
- 不需要每次都有問題；沒問題就寫「無」

## 下一輪

Reflect 完成後，回到 `prompts/RESEARCH.TW.md` 開始下一次研究
