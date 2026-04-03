# Portfolio Manager — Reflect

每次 `PORTFOLIO_MANAGER.md` 的 Step 7 執行時使用。

## 流程

### 1. 回顧

檢視整個決策流程：
- regime 判斷的準確度？和實際市場走勢對比
- 策略選擇是否匹配 regime？
- 資金分配效果如何？太保守？太激進？
- 風控規則是否觸發？觸發後處理是否正確？
- 有沒有錯過重要的市場信號（新聞、鏈上異常、政策）？
- 有沒有重複犯之前 lessons 記錄過的錯誤？

找出所有問題，不限數量。

### 2. 記錄

在 journal 中追加：

```markdown
## Reflection
- At: HH:MM
- Regime accuracy: [correct / partially / wrong]
- Problems:
  - "..."
- Next:
  - "..."
```

### 3. 改善

直接修改檔案，只改有把握的：

- `data/account/lessons_pm.md` — 新的可複用規則
- `data/config/risk_rules.yaml` — **只能收緊，不能放寬**
- `data/config/pairs.yaml` — 交易對調整
- `data/account/state/active_config.yaml` — 配置調整
- `prompts/PORTFOLIO_MANAGER.md` — 流程改善
- `src/` — 工具程式碼

不確定的放到 `Next` 留到下一輪。

### 4. 記錄改變

更新同一個 reflection entry：

```markdown
## Reflection
- At: HH:MM
- Regime accuracy: [correct / partially / wrong]
- Problems:
  - "..."
- Changes:
  - "..."
- Next:
  - "..."
```

**Changes 不能為空。**

### 然後回到 PORTFOLIO_MANAGER.md Step 0。

## 原則

- 先完整回顧，再改
- 如果同樣的錯誤出現過 → 這次必須修
- risk_rules.yaml 只能收緊，**絕對不能放寬**
- 沒有問題 = 寫 "無"，但 Changes 依然不能空
