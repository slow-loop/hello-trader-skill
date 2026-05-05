# Backlog

## 焦點（週級 review）

- **主目標**：定時自動跑 tw-trader skill（每日 RESEARCH + TRADING 輪次自動觸發）
- **為什麼**：skill 本身已可手動跑一輪，但需要排程機制才能真正自主運作
- **不做（這 stretch 明確排除）**:
  - 新 skill 開發（strategy-lab、lana-copycat 等先擱置）
  - frontend-nano 改版

## Doing

-

## Open（依優先序）

### 近期推進
- (P0) 設定每日定時排程觸發 tw-trader skill（交易日 09:00 前、盤中、收盤後各一次）
- (P0) 確認 tw-trader CLI 可在排程環境正常跑（env、uv、API keys）
- (P1) 設定 screener-snapshot 每日定時快照
- (P1) 建立簡單的 run log，讓 global PM 可以讀到今日有無成功跑

### Ship 後再評估
- (P2) 排程失敗通知機制
- (P2) wallstreet-research skill 定期研究報告
- (P3) us-trader skill 評估

## Blocked

-

## Done（最近 7 天）

- 2026-05-06 建立 local PM
