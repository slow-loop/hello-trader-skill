# nano-trader-skills

[English](README.md) | **繁體中文**

用 Claude 跑自動化台股交易 agent 的 local-first 工具包。沒有 server、沒有資料庫——所有東西都是磁碟上的 YAML 跟 Markdown。

三個鬆耦合元件：

| 資料夾 | 是什麼 |
|---|---|
| [`skills/tw-trader/`](skills/tw-trader) | Claude skill：SKILL.md prompts + Python CLI，做紙交易、日誌、監察清單、研究文件 |
| [`libs/market-core/`](libs/market-core) | 報價、OHLCV K 棒、技術指標、個股快照（[README](libs/market-core/README.md)） |
| [`frontend-nano/`](frontend-nano) | 極簡 Vite + React viewer，瀏覽 trader 的本地 YAML/Markdown |

`web-reader`（非同步 URL → 乾淨文字，被 skills 引用）獨立放在 [w121211/web-reader](https://github.com/w121211/web-reader)。

## 架構

```
┌──────────────────┐  讀取 YAML   ┌──────────────────────┐
│  frontend-nano   │ ───────────► │  data/account/*      │
│  (Vite + React)  │              │  （runtime state）   │
└──────────────────┘              └──────────▲───────────┘
                                             │ 寫入
                                  ┌──────────┴──────────┐
                                  │  skills/tw-trader   │
                                  │  prompts + CLI      │
                                  └──────────┬──────────┘
                                             │ 依賴
                                  ┌──────────┴──────────┐
                                  ▼                     ▼
                          ┌──────────────┐      ┌──────────────────────┐
                          │ market-core  │      │ web-reader (github)  │
                          │ 報價 / 技術指標 │      │ URL → 文字           │
                          └──────────────┘      └──────────────────────┘
```

Runtime 狀態（帳戶、日誌、研究）放在 repo 根目錄的 [`data/`](data)，跟 skill code 分離——skill 維持唯讀，未來同一個 repo 也能放多個 skill 共用同個 data 目錄。

## 快速開始

需要 **Python 3.13**、[**uv**](https://docs.astral.sh/uv/)、**Node 20+**。

```bash
git clone https://github.com/<you>/nano-trader-skills.git
cd nano-trader-skills

cp .env.example .env             # 填入 FUGLE_API_KEY、FINMIND_API_KEY 等
cd skills/tw-trader && uv sync   # 一次裝齊 tw-trader + market-core（web-reader 從 GitHub 拉）

uv run tw-trader account         # 看紙交易帳戶
uv run tw-trader watchlist       # 看監察清單
```

啟動前端 viewer：

```bash
cd frontend-nano
npm install && npm run dev      # http://localhost:5173
```

在 Claude Code 裡把 [`skills/tw-trader/prompts/SKILL.md`](skills/tw-trader/prompts/SKILL.md) 餵給 Claude，就能驅動 agent。每輪做一次 Research、一次 Trading。

## tw-trader CLI

```bash
uv run tw-trader account                       # 帳戶狀態
uv run tw-trader buy 2330 1000 --limit 600     # 紙交易買單
uv run tw-trader sell 2330 1000                # 紙交易賣單（市價）
uv run tw-trader sweep                         # 用最新報價撮合掛單
uv run tw-trader journal                       # 今日日誌
uv run tw-trader doc-add data/account/research/2026-04-26-tw-2330.md
```

狀態都放在 repo 根目錄的 `data/account/`：

```
data/account/
├── state/         # 帳戶、部位、委託、成交
├── journals/      # 每日 YAML 日誌
├── research/      # 每檔個股的 Markdown 研究文件
├── screener/      # 每日選股快照
├── watchlist.yaml
└── lessons.md
```

新研究文件 / 交易卡片的範本放在 `data/account/*/template/`。要換 data 位置可以設 `TW_TRADER_DATA_ROOT=/your/path`。

## 單獨使用 libs

`market-core` 不綁定台股，可以單獨拿出來用：

```bash
python -c "from market_core import analyze_symbol, MarketRuntimeConfig, MarketConfig; \
  print(analyze_symbol('AAPL', MarketRuntimeConfig(market=MarketConfig(profile='us_equity'))).quote.price)"
```

`web-reader` 已獨立成自己的 repo，詳見 [github.com/w121211/web-reader](https://github.com/w121211/web-reader)。

## Repo 結構

```
.
├── skills/tw-trader/      交易 skill（prompts + Python CLI）
├── libs/
│   └── market-core/       行情數據 + 技術分析
├── frontend-nano/         React viewer
├── data/                  Runtime 狀態（account, journals, posts）
├── .env.example           整個 monorepo 共用的單一 env 檔
└── README.md
```

## 授權

MIT — 詳見 [LICENSE](LICENSE)。
