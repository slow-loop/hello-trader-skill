# hello-trader-skill (nano-trader-skills)

## Goal

跑通 Taiwan-stock paper trading agent 的 daily routine。Local-first，所有狀態在 disk（YAML / Markdown）。Agent 醒來 = 推進 `skills/tw-trader`、`libs/market-core`、`frontend-nano` 三者其一可 ship 的工程切片，或處理 daily research routine 的工程任務（CLI、輸出格式、排程草稿）。

短期重點：把 daily research 從手動觸發變成可排程（launchd plist 草稿），讓 agent 能無人值守每天產出 watchlist + journal。`launchctl load` 留給 user。

## Scope

| In scope | Out of scope（無 user 明確批准） |
|---|---|
| 改 `skills/tw-trader`、`libs/market-core`、`frontend-nano` | 真錢交易 / 對接 broker API |
| 寫 CLI、launchd plist 範本、journal 格式 | `launchctl load` / 註冊 cron / 開機自啟 |
| 補測試、改 docs、refactor | 改 `data/account/` 真實 paper trading 帳本內容 |
| 用免費 / 公開資料源跑 research | 訂閱付費 data feed |

## Terminology

### Task

一個 task = 一個能 ship 的切片：寫一個 CLI 子命令、補一個 indicator、修一個 screener、寫一個 plist 範本。Size：30–90 分鐘、commit 後 user 跑得起來。

### Checkpoints

不能自主跨越的位置：

- 排程實際生效的最後一步（plist 載入）
- 改 `data/account/` 真實帳本格式
- skill spec（`SKILL.md`）大改方向

### Risk Gates

未經 user 明確批准不執行：

- 任何真錢動作、broker API 串接
- `launchctl load` / 註冊 cron / 開機自啟
- 改 `data/account/` 真實 holdings 內容
- 訂閱付費服務

## Phases

1. **Daily research CLI 完備** — `screener-snapshot` 之外補齊 watchlist update、research doc 生成
2. **排程草稿** — 寫 launchd plist + 跑法 docs，user 自己 load
3. **Routine 穩定** — 連跑一週無人值守，每日 journal + watchlist 自動更新

當前 phase 與最近 milestone 寫在最新的 `heartbeat/log/` entry。

## Backlog

（暫無）
