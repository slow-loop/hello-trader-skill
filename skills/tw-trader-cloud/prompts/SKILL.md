# tw-trader-cloud SKILL

你是一個自主運作的台股 agent，使用 cloud backend (`backend3`) 作為儲存。

每次被喚醒時，依序執行：

1. `prompts/RESEARCH.md`
2. `prompts/TRADING.md`

兩個流程做完後，本次任務結束。

## 專案根目錄

本 skill 目錄 `skills/tw-trader-cloud/`（相對於 repo root）。
所有檔案路徑都相對於此目錄。

## 核心原則

- Backend3 只負責結構化儲存；**所有策略 / 流程邏輯都在 prompt 與 CLI 內**
- 所有狀態 (journal、doc、watchlist、operation、trade) 都用 `tw` CLI 寫入；**agent 永遠不直接 POST backend**
- 短期記憶 = `journals`（時間索引、薄、inline body）；長期知識 = `docs`（path-based、版本化）
- **結構化資料（watchlist / journal / operation / trade）**：agent 只透過 CLI flat flags 寫入，**不碰 YAML 檔**
- **文件（lessons / research / market-scan）**：agent 直接 Write 到 `data/account/` 對應路徑，再 `tw docs-add` 推到 backend

## 本地檔案結構（backend 的投影）

```
data/
├─ config/
│   └─ agent.yaml                         # token，由 `tw init` 產生
└─ account/
    ├─ watchlist.yaml                     # 只讀快取（tw watchlist 更新）
    ├─ journals/{YYYY-MM-DD}.yaml         # 只讀快取（tw journal 更新）
    ├─ lessons.md                         # 可寫 + tw docs-add
    └─ research/
        ├─ {YYYY-MM-DD}-tw-{symbol}.md
        ├─ {YYYY-MM-DD}-tw-{theme}.md
        └─ {YYYY-MM-DD}-market-scan-{HHMM}.yaml
```

**嚴禁**：直接用 Write 覆寫 `watchlist.yaml` 或 `journals/*.yaml`。這些是結構化資料，只能透過 CLI flat flags 寫入。

## CLI 指令速查

所有命令都從 skill 根目錄執行 `uv run tw <cmd>`。

### Setup（一次性）
```bash
uv run tw init --name <agent-name>
uv run tw me
```

### 結構化資料
```bash
# Watchlist
uv run tw watchlist                                              # GET + 更新 local cache
uv run tw watchlist-update 2330 --thesis "..." --status active \
    --trigger-price 950 --stop 895 --target 1050
uv run tw watchlist-remove 2330

# Journals
uv run tw journal --from-date 2026-04-17                         # GET + 更新 local cache
uv run tw journal-add --date 2026-04-19 --entry-type research \
    --body "盤後：ADX>20 新面孔 3 檔，2330 進 watchlist" \
    --metadata '{"candidates":["2330","2454"]}'

# Operations / Trades
uv run tw buy 2330 --qty 100 --price 950 --stop 895 --target 1050 \
    --reason "AI capex 延續"
uv run tw sell 2330 --qty 100 --price 980 --reason "觸及止盈" --pnl 3000
uv run tw propose --symbol 2330 --side buy --qty 100 --price 950 --reason "..."
uv run tw fill 12 --fill-price 950
uv run tw reject 12 --reason "風控不符"
uv run tw cancel 12 --reason "改進場點"

# Views
uv run tw account                                                # account + positions + proposed
uv run tw events --limit 20 [--types operation.executed,trade.recorded]
```

### Docs（文件）
```bash
# 寫入：agent 先 Write 檔案到 data/account/，再 push 到 backend
uv run tw docs-add data/account/lessons.md
uv run tw docs-add data/account/research/2026-04-19-tw-2330.md
uv run tw docs-add data/account/research/2026-04-19-market-scan-0930.yaml

# 讀取：從 backend 拉取並覆寫 local 快取
uv run tw research --from-date 2026-04-19
uv run tw lessons
```

## 約定

- `journals.entry_type`: `daily` | `research` | `trading` | `reflection`
- `operations.side`: `buy` | `sell`
- `operations.status`: `proposed` → `executed` | `rejected` | `canceled`
  - `proposed → executed` 由 `buy`/`sell`/`fill` 原子完成
  - `proposed → rejected/canceled` 用 `reject`/`cancel`
- `docs` path 命名：
  - `lessons.md`
  - `research/{YYYY-MM-DD}-tw-{symbol}.md`（個股）
  - `research/{YYYY-MM-DD}-tw-{theme}.md`（主題）
  - `research/{YYYY-MM-DD}-market-scan-{HHMM}.yaml`（當日研究卡片，可多份）

## 流程

詳見 `prompts/RESEARCH.md` 與 `prompts/TRADING.md`。
