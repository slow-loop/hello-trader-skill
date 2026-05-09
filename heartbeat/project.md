# hello-trader-skill (nano-trader-skills)

## Goal

跑通 Taiwan-stock paper trading agent 的 daily routine。Local-first，所有狀態在 disk（YAML / Markdown）。Agent 醒來 = 推進 `skills/tw-trader`、`libs/market-core`、`frontend-nano` 三者其一可 ship 的工程切片，或處理 daily research routine 的工程任務（CLI、輸出格式）。

對應 skill：**[`skills/tw-trader/`](../skills/tw-trader/)**（dev + routine 主軸）。其餘 skills/ 下的 `us-trader` / `tw-trader-cloud` / `lana-copycat` / `strategy-lab` / `wallstreet-research` 視為旁支，不在當前主軸。

短期重點兩條：

1. **TW Trader daily routine 穩定**：能穩定每天產出 watchlist + research docs，無人值守
2. **OSS split**：把 `tw-trader` 抽成獨立 OSS **新 repo**（見下方「OSS Split 設計」段）

> 排程：launchd / cron 不做（user 偏好顯性自動化觸發；前景 scheduler 模式參考 hello-note 的 `kol-watch`）。

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
2. **Routine 穩定** — 連跑一週每日 journal + watchlist 自動更新（前景 scheduler 模式，參考 hello-note `kol-watch`）
3. **OSS split** — 把 `tw-trader` 抽成新 repo（見下方設計段）

## OSS Split 設計（新 repo）

**目標**：把 `tw-trader` 從 hello-trader-skill 抽成可獨立發布、可自主跑的 OSS repo。

**架構鏡射 hello-trader-skill 現況**（三層）：

| 層 | 來源 | 抽到新 repo |
|---|---|---|
| Skills 殼 | `skills/` | `skills/tw-trader/` |
| TW Trader 核心 | `skills/tw-trader/` | 同上 |
| Market Core 引擎 | `libs/market-core/` | `libs/market-core/` |

新 repo 命名：**TBD**（候選：`nano-trader-tw` / `tw-trader-oss`，user 拍）

**必要條件**：

- **能 auto-run**：自帶 scheduler / runner（前景 Python scheduler 模式，參考 hello-note `kol-watch`），不靠 user 手動觸發
- **License**：MIT 或 Apache 2.0（user 拍）
- **Dependency 隔離**：`pyproject.toml` 列清楚，`market-core` 走 `[tool.uv.workspace]` 或發布到 PyPI
- **README**：getting started + auto-run 啟動範例
- **不帶**：真實 `data/account/` 帳本內容、credentials、`.env`

**待設計細節**：

- 怎麼從 monorepo 抽出歷史：`git subtree split` / `git filter-repo` / 手動 copy（取決於要不要保留 commit history）
- `market-core` 的 dual-maintain：抽出後本 repo 還在用，是 sync / vendoring / 升級成 git submodule、還是內部 package
- Auto-run 啟動接口：`tw-trader-oss daemon` CLI？docker？plist 範本附帶但不自動載入？
- Test fixtures / sample data 怎麼帶（不能含真錢交易紀錄）

**待 user 拍**：
- 新 repo 命名
- License
- 抽出方式（保留 commit history 與否）

當前 phase 與最近 milestone 寫在最新的 `heartbeat/log/` entry。

## Backlog

（暫無）
