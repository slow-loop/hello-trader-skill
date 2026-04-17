# 台股 Trading Reflect

這通常是作為盤後結算的一部分（批次回顧）。盤中應專注於交易執行，避免因頻繁反思而打斷節奏。

若目前為盤後時段，在 `TRADING.TW.md` 結束後執行這裡，統整近期的交易。完成後結束當日循環。

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

### lessons 更新原則

- 只有在這次反思中發現能改變未來決策的關鍵經驗時，才提煉成規則並更新 `data/account/lessons.md`
- 以下情況特別值得升級為 lessons：
  - 造成實際重大虧損的盲點
  - 提早賣飛或錯過機會的明顯機會成本
  - 跨越多筆交易反覆出現的紀律偏離或失誤
  - 可以總結成下次遇到相同情況時，能直接應用的清晰規則

## 下一輪

Reflect 完成後，回到 `prompts/TRADING.TW.md` 開始下一次交易
