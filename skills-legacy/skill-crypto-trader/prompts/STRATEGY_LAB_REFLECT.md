# Strategy Lab — Reflect

每次 `STRATEGY_LAB.md` 的 Step 6 執行時使用。

## 流程

### 1. 回顧

檢視整個策略開發流程：
- 搜尋的策略 idea 品質如何？是否太隨意？
- 生成的策略程式碼品質如何？有沒有常見錯誤？
- 回測結果是否合理？有沒有看起來 too good to be true？
- Hyperopt 是否 overfit？
- Walk-forward 結果和預期差距？
- 有沒有重複犯之前 lessons 記錄過的錯誤？

找出所有問題，不限數量。

### 2. 記錄

在 journal 中追加：

```markdown
## Reflection
- At: HH:MM
- Problems:
  - "..."
- Next:
  - "..."
```

### 3. 改善

直接修改檔案，只改有把握的：

- `data/account/lessons_lab.md` — 新的可複用規則
- `data/strategies/registry.yaml` — 策略 metadata
- `prompts/strategies/*.md` — 策略 idea seeds
- `prompts/STRATEGY_LAB.md` — 流程改善
- `freqtrade_userdata/strategies/*.py` — 策略程式碼
- `src/` — 工具程式碼
- `data/config/risk_rules.yaml` — **只能收緊，不能放寬**

不確定的放到 `Next` 留到下一輪。

### 4. 記錄改變

更新同一個 reflection entry：

```markdown
## Reflection
- At: HH:MM
- Problems:
  - "..."
- Changes:
  - "..."
- Next:
  - "..."
```

**Changes 不能為空。** 即使只是在 lessons 加一句話。

### 然後回到 STRATEGY_LAB.md Step 0。

## 原則

- 先完整回顧，再改
- 如果同樣的錯誤出現過 → 這次必須修
- 只記錄實際做的改變，不要過度記錄
- 沒有問題 = 寫 "無"，但 Changes 依然不能空
