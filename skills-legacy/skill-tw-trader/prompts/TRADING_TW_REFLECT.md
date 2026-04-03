# 台股 Trading Reflect

這是一個 loop：交易 → reflect → 交易 → reflect → ...

每次 `TRADING.TW.md` 結束後執行這裡，完成後回到 `TRADING.TW.md` 開始下一輪。

## 任務

回頭檢視剛才整個交易過程，自己找出問題，自己改。

目標是讓下一次交易做得更好，不是讓這次看起來更完美。

## 流程

### 1. 檢視

重新看一遍剛才的整個交易過程——從讀資料、判斷、到執行
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

### 3. 改

直接改。能改的東西包括但不限於：

- `data/account/lessons.md`
- `data/account/watchlist.yaml`
- `data/config/technical_config.yaml`
- `prompts/TRADING.TW.md`
- `src/` Python code
- `/Users/cw/Documents/GitHub/hello-invest/libs/web-reader` Python code

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

Reflect 完成後，回到 `prompts/TRADING.TW.md` 開始下一次交易
