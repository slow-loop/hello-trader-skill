# hello-trader-skill

[English](README.md) | **繁體中文**

用 Claude 驅動的台股自主交易 agent，local-first 架構。沒有 server、沒有資料庫——所有狀態都是磁碟上的 YAML 和 Markdown。

## 它做什麼

AI agent 每天跑一輪 **Research + Trading** 例行作業：

1. **Research** — 抓行情、讀新聞、更新監察清單、產出個股研究文件
2. **Trading** — 檢視現有部位、評估監察清單、掛單或調整委託

所有東西存在 `data/account/` 裡，純文字可以直接讀。前端 viewer 讓你不碰 CLI 就能瀏覽帳戶狀態。

## 三個鬆耦合元件

| 資料夾 | 是什麼 |
|---|---|
| [`skills/tw-trader/`](skills/tw-trader) | Agent 本體：`SKILL.md` prompts + Python CLI，負責紙交易、日誌、監察清單、研究文件 |
| [`libs/market-core/`](libs/market-core) | 報價、OHLCV K 棒、技術指標、個股快照 |
| [`frontend-nano/`](frontend-nano) | 極簡 Vite + React viewer，瀏覽本地 YAML/Markdown |

[`web-reader`](https://github.com/w121211/web-reader)（非同步 URL → 乾淨文字）是獨立的依賴，從 GitHub 拉取。

## 架構

```
┌──────────────────┐  讀取 YAML   ┌──────────────────────┐
│  frontend-nano   │ ───────────► │  data/account/*      │
│  (Vite + React)  │              │  （runtime 狀態）     │
└──────────────────┘              └──────────▲───────────┘
                                             │ 寫入
                                  ┌──────────┴──────────┐
                                  │  skills/tw-trader   │
                                  │  prompts + CLI      │
                                  └──────────┬──────────┘
                                             │ 依賴
                                  ┌──────────┴──────────┐
                                  ▼                     ▼
                          ┌──────────────┐   ┌──────────────────────┐
                          │ market-core  │   │ web-reader (GitHub)  │
                          │ 報價 / 技術指標│   │ URL → 乾淨文字       │
                          └──────────────┘   └──────────────────────┘
```

Runtime 狀態（帳戶、日誌、研究文件）放在 `data/` 下，與 skill code 分離——skill 維持唯讀，多個 skill 也能共用同一個 data 目錄。

## 前置需求

- **Python 3.13** + [**uv**](https://docs.astral.sh/uv/)
- **Node 20+**（前端才需要）
- **Claude Code** — agent 由 Claude 透過 `SKILL.md` 驅動
- API 金鑰：Fugle（台股報價）、FinMind（歷史資料）；其他選用——詳見 `.env.example`

## 安裝

```bash
git clone https://github.com/<你的帳號>/hello-trader-skill.git
cd hello-trader-skill

cp .env.example .env          # 至少填入 FUGLE_API_KEY、FINMIND_API_KEY
cd skills/tw-trader
uv sync                       # 一次安裝 tw-trader + market-core + web-reader
```

確認安裝成功：

```bash
uv run tw-trader account      # 應該顯示空的紙交易帳戶
uv run market overview        # 應該顯示大盤快照
```

## 跑每日例行作業

在 Claude Code 裡開啟 [`skills/tw-trader/prompts/SKILL.md`](skills/tw-trader/prompts/SKILL.md)，讓 agent 執行。一次 session = 一輪 Research + 一輪 Trading。

如果要每天自動執行，使用前景 scheduler（參考 [hello-note](https://github.com/w121211/hello-note) 的 `kol-watch` 模式）——不需要 cron 或 launchd。

## CLI 指令

```bash
# 帳戶
uv run tw-trader account                        # 部位 + 現金摘要
uv run tw-trader journal                        # 今日日誌

# 委託（紙交易）
uv run tw-trader buy  2330 1000 --limit 600     # 限價買單
uv run tw-trader sell 2330 500                  # 市價賣單
uv run tw-trader sweep                          # 用最新報價撮合掛單

# 研究
uv run tw-trader watchlist                      # 看監察清單
uv run tw-trader screener-snapshot              # 跑選股器，存快照

# 行情（market-core）
uv run market overview                          # 大盤趨勢快照
uv run market quote 2330                        # 單股報價
uv run market chart 2330 --period 3mo           # OHLCV K 棒圖
```

覆蓋資料目錄：

```bash
TW_TRADER_DATA_ROOT=/your/path uv run tw-trader account
```

## 資料目錄結構

```
data/account/
├── state/          # 帳戶、部位、委託、成交（YAML）
├── journals/       # 每日日誌（YAML）
├── research/       # 個股 Markdown 研究文件
├── screener/       # 每日選股快照
├── watchlist.yaml
└── strategy.md
```

新文件的範本放在 `data/account/*/template/`。

## 前端 viewer

```bash
cd frontend-nano
npm install && npm run dev    # http://localhost:5173
```

## Repo 結構

```
.
├── skills/
│   └── tw-trader/        交易 agent（prompts + Python CLI）
├── libs/
│   └── market-core/      行情資料 + 技術分析
├── frontend-nano/        React viewer
├── data/                 Runtime 狀態（已加入 .gitignore）
├── .env.example
└── README.md
```

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
