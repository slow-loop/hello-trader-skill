# polymarket-scan

[English](README.md) | **繁體中文**

一個只讀的 Polymarket 掃描 agent，專找單場對戰盤裡的一種特定機會：強隊 vs 弱隊、
但盤價還沒反映過來——不是真硬幣局，是**滯後修正**的機會。

**只做發現，絕不下單。** 找到機會後交給交易 skill。

不需要 API key——掃描器是純 Python stdlib，自帶 DNS-over-HTTPS 解析，就算本機 ISP
污染了 Polymarket 的 DNS 也能跑。

## 運作方式：三層漏斗（便宜的先砍，貴的留最後）

```
1. 機械廣撈   scripts/polymarket_scan.py     → 上百個市場   便宜
2. 直覺篩     「這兩邊強弱一眼懸殊嗎？」      → 幾個         便宜（秒級，不上網）
3. 查證       只對倖存者查戰績/條款/新聞      → 0-1 個       貴（才值得花）
```

多數天會掃不到東西，這是正常的。Agent 被要求在第 2 步（便宜）寧可放寬多留幾個，
只有通過第 3 步（對真實戰績、民調、結算條款查證）才會下判斷。

## CLI

```bash
# 運動：跨全部運動，掃自某日起新開的單場對戰盤
python3 scripts/polymarket_scan.py moneyline --since 2026-07-01

# 選舉：用 /events + tag_slug 引擎（moneyline 不涵蓋政治類）
python3 scripts/polymarket_scan.py tagged --mode fresh --tags elections,world-elections
```

`tagged` 的 mode：`early`（單場對戰、近中段價位）、`fresh`（剛開盤、有真實訂單簿）、
`band`（有成交但還在中段價格帶）、`raw`（不過濾全倒出）。完整參數說明見
[`prompts/SKILL.md`](prompts/SKILL.md)。

## 輸出

每次執行都會產出完整兩輪報告——掃了什麼、留下什麼、丟掉什麼及原因，接著是每個
倖存者的查證過程與結論——寫到 `data/journals/{YYYY-MM-DD}.md`。

## Agent 操作說明

給 Claude agent 讀的操作邏輯（心態、漏斗規則、報告格式）在
[`prompts/SKILL.md`](prompts/SKILL.md)，以繁體中文撰寫。這份 README 是給人看的
「這是什麼／怎麼跑」文件；`SKILL.md` 才是 Claude 實際遵循的 prompt。

## 屬於 hello-trader-skill

這個 skill 是 [hello-trader-skill](../../README.zh-TW.md) monorepo 的一部分——完整
的交易/研究 skill 清單與共用元件（`libs/market-core`、`hello-web-reader`）見根目錄
README。
