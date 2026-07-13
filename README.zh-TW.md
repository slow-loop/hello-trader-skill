# hello-trader-skill

[English](README.md) | **繁體中文**

一個 local-first、由 Claude 驅動的交易與研究 agent monorepo。預設沒有 server、沒有
資料庫——多數 skill 的狀態都是磁碟上的純 YAML 和 Markdown，由 Claude Code 的
`SKILL.md` prompt 驅動。

## 👉 從這裡開始：polymarket-scan

第一次看這個 repo？[`skills/polymarket-scan/`](skills/polymarket-scan) 是最容易
單獨試跑的 skill——一個只讀掃描器，找 Polymarket 上定價落後的單場對戰盤，不需要
任何 API key。設定與 CLI 用法見它的 [README](skills/polymarket-scan/README.zh-TW.md)
（也有[英文版](skills/polymarket-scan/README.md)）。

## 這個 repo 裡的 skill

| Skill | 是什麼 | 狀態 |
|---|---|---|
| [`polymarket-scan`](skills/polymarket-scan) | 只讀掃描器，找 Polymarket 單場對戰盤的定價落後機會 | 運作中，不需 API key |
| [`tw-trader`](skills/tw-trader) | 台股紙交易 agent——每日 Research + Trading 例行作業 | 主力 skill |
| [`tw-trader-cloud`](skills/tw-trader-cloud) | 跟 `tw-trader` 一樣，但狀態同步到 cloud backend 而非本地檔案 | 實驗性 |
| [`us-trader`](skills/us-trader) | 美股交易 agent，交易 `strategy-lab` 產出的訊號 | 運作中 |
| [`strategy-lab`](skills/strategy-lab) | 離線 factor 研究、回測，並將策略 promote 給 `us-trader` | 運作中 |
| [`lana-copycat`](skills/lana-copycat) | 加密貨幣合約複製交易 agent（Binance Futures testnet） | 僅測試網 |
| [`wallstreet-research`](skills/wallstreet-research) | 單一個股或主題的深度研究報告產生器 | 運作中 |

每個 skill 都有自己的 README，包含設定與 CLI 細節。各 skill 共用兩個函式庫：

| 資料夾 | 是什麼 |
|---|---|
| [`libs/market-core/`](libs/market-core) | 報價、OHLCV K 棒、技術指標、個股快照 |
| [`frontend-nano/`](frontend-nano) | 極簡 Vite + React viewer，瀏覽 `tw-trader` 的本地 YAML/Markdown 資料 |

[`hello-web-reader`](https://github.com/w121211/hello-web-reader)（非同步 URL → 乾淨文字）是
獨立的依賴，從 GitHub 拉取，被多個 skill 使用（`tw-trader`、`wallstreet-research`）。

## 架構（tw-trader）

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
                          │ market-core  │   │ hello-web-reader      │
                          │ 報價 / 技術指標│   │ URL → 乾淨文字       │
                          └──────────────┘   └──────────────────────┘
```

其他 skill 大致遵循相同模式（由 Claude 透過 `SKILL.md` 驅動、runtime 狀態與 skill
code 分離），但各自維護自己的 `data/` 目錄——各自的結構請見該 skill 的 README。

## 前置需求

- **Python 3.13** + [**uv**](https://docs.astral.sh/uv/)
- **Node 20+**（只有 `frontend-nano` 需要）
- **Claude Code** — 多數 agent 由 Claude 透過 `SKILL.md` prompt 驅動
- API 金鑰依 skill 而異——見根目錄 `.env.example` 與各 skill 的 README
  （`polymarket-scan` 不需要任何金鑰；`tw-trader` 需要 Fugle + FinMind；
  `lana-copycat` 需要 Binance Futures testnet 金鑰）

## 安裝

```bash
git clone https://github.com/<你的帳號>/hello-trader-skill.git
cd hello-trader-skill
cp .env.example .env    # 填入你要跑的 skill 所需的金鑰

cd skills/<skill-name>  # 例如 skills/tw-trader、skills/polymarket-scan
uv sync                 # 有 pyproject.toml 的 skill；polymarket-scan 純 stdlib 不需要
```

接著在 Claude Code 裡開啟該 skill 的 `prompts/SKILL.md`（或 `SKILL.md`）讓 agent
執行，或依該 skill 的 README 直接呼叫它的 CLI / script。

## Repo 結構

```
.
├── skills/
│   ├── polymarket-scan/   Polymarket 對戰盤掃描器（只讀，stdlib）
│   ├── tw-trader/         台股紙交易 agent（prompts + Python CLI）
│   ├── tw-trader-cloud/   tw-trader 的 cloud backend 版本
│   ├── us-trader/         美股交易 agent
│   ├── strategy-lab/      離線 factor 研究 + 回測 + promote
│   ├── lana-copycat/      加密貨幣合約複製交易 agent（testnet）
│   └── wallstreet-research/  單一個股/主題深度研究
├── libs/
│   └── market-core/       行情資料 + 技術分析（共用）
├── frontend-nano/         React viewer（tw-trader 的資料庫）
├── data/                  Runtime 狀態（已加入 .gitignore）
├── .env.example
└── README.md
```

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
