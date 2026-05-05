---
name: pm
description: Project work tracker for hello-trader-skill. On each run, reads pm/ and git, picks the next backlog item, writes journal. Use when invoked manually or by schedule.
---

# pm

## 流程

1. **讀**
   - `pm/backlog.md`
   - `pm/journals/<today>.md`（沒有就用模板新建）
   - `git log --since=midnight --oneline` + `git status -sb`

2. **做**
   - 從 backlog `Doing` / `Open` 挑下一件能做的就動手
   - 做不了（需要 user / 外部資源 / 超出單 session）→ 跳過，在 report 說明

3. **寫**
   - 今天 journal 「做了什麼」append delta
   - 今天 journal 「現況 / 下一步」overwrite

4. **回報**（輸出給 user，不寫進檔案）
   - 這次做了什麼
   - 現在在哪
   - 下一步建議
   - flags：blocker、stale

## Journal 模板

```markdown
# YYYY-MM-DD

## 做了什麼
-

## 現況 / 下一步
- in-flight:
- blocker:
- next:
```
