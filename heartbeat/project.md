# hello-trader-skill (nano-trader-skills)

## Goal

跑通 Taiwan-stock paper trading agent 的 daily routine。Local-first，所有狀態在 disk（YAML / Markdown）。Agent 醒來 = 推進 `skills/tw-trader`、`libs/market-core`、`frontend-nano` 三者其一可 ship 的工程切片，或處理 daily research routine 的工程任務（CLI、輸出格式）。

對應 skill：**[`skills/tw-trader/`](../skills/tw-trader/)**（dev + routine 主軸）。其餘 skills/ 下的 `us-trader` / `tw-trader-cloud` / `lana-copycat` / `strategy-lab` / `wallstreet-research` 視為旁支，不在當前主軸。

短期重點兩條：

1. **TW Trader daily routine 穩定**：能穩定每天產出 watchlist + research docs，無人值守
2. **OSS 化**：hello-trader-skill 本身就是公開版本，不另開 repo；把 repo 整理到可直接公開使用的狀態

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

1. **Daily research CLI 完備** — `screener-snapshot` 之外補齊 watchlist update、research doc 生成 ✅
2. **Routine 穩定** — 連跑一週每日 journal + watchlist 自動更新（前景 scheduler 模式，參考 hello-note `kol-watch`）
3. **OSS 化** — hello-trader-skill 本身即公開版，整理到外部使用者能直接 clone + 跑起來的狀態

## OSS 化 清單

hello-trader-skill 本身就是公開版，不另開 repo。以下是讓 repo 達到可公開使用狀態需要處理的事：

**已確認安全（不需處理）**

- `.env` 從未進入 git history — 無需 filter-repo
- `data/account/` 未被 git track — 帳本資料不會公開
- `LICENSE`（MIT）已存在
- `README.md` + `README.zh-TW.md` 已存在

**待處理**

| 項目 | 難度 | 說明 |
|---|---|---|
| `.claude/` 加入 `.gitignore` | 簡單 | worktrees 目錄不該進 repo |
| `uv install` 乾淨環境驗證 | 中 | 確認外部使用者能跑起來；`web-reader` 依賴 GitHub tag 需測試 |
| `.env.example` | 簡單 | 列出所有需要的 env vars，不含真實值 |
| CONTRIBUTING.md | 簡單 | 選項性，若要吸引外部貢獻再補 |

**設計決策（已定）**

- auto-run：前景 Python scheduler 模式（參考 hello-note `kol-watch`），不靠 launchd / cron
- dependency：`pyproject.toml` + `uv`，`market-core` 走 workspace
- 不帶：真實 `data/account/` 帳本、credentials、`.env`

當前 phase 與最近 milestone 寫在最新的 `heartbeat/log/` entry。

## Backlog

（暫無）
