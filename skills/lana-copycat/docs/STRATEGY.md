# Lana-copycat 策略與設計

這份檔案記錄 `lana-copycat` skill 的交易策略、管道拆分邏輯、autonomous loop 的設計，以及推導過程中的關鍵決策。

## 0. 起點：Lana 原版策略

複製自 [@lanaaielsa](https://x.com/lanaaielsa)。核心三訊號交集：

1. **Binance Square 散戶討論熱度** —— 散戶集中地，MM 拉盤前會在這裡打窩
2. **OI 大漲但價格沒動** —— 資金偷偷進場，尚未反映在價格上
3. **漲幅榜異動** —— 確認勢頭已啟動

風險規則（硬性不可違反）：

- **固定金額止損 200 USDT**（不管倉位大小）
- **只做 LONG**（單方向）
- **每次只開 1 個倉位**（不分散）
- **止盈由 AI 判斷，分批賣出**（不設固定止盈價）

Lana 自己說「90% 運氣 + 特定行情」。熊市 / 沒 MM 打窩時會連續止損，這不是穩定印鈔機。

## 1. 為什麼拆兩套管道？

原本打算把 cattrade gsheet 訊號**合併**進 Square scoring。後來決定**完全分開**，兩個不互相過濾：

| 面向 | Square 管道 | Cattrade 管道 |
|---|---|---|
| 資料 | 爬蟲抓散文 + OI + gainers | gsheet 11 個結構化排行榜 |
| 雜訊 | 高（垃圾幣種、灌水、假熱度） | 低（已經量化打過分） |
| Agent 加值 | **高** —— 過濾垃圾、判熱度真假 | **零** —— 全數字，agent 判讀沒加值 |
| Alpha 來源 | 散戶情緒尚未反映在盤面 | 大戶結構訊號（Pattern B）早於 gainers 榜 |
| 執行方式 | Agent 每次喚醒手動跑 | **cron 純程式自動 loop** |

**關鍵 insight**：cattrade 候選通常還沒出現在 Binance 24h gainers 榜上 —— 這正是它的 alpha。兩套都命中的幣訊號最強，但單套命中也可進場。

### 為什麼 cattrade 不需要 agent？

使用者原話：「用分數直接算 score 跟 agent 判 conviction 沒差別」。

推導過程：
1. cattrade sheet 的每個欄位都是結構化數字（量排名、結構強度、大戶集中度、量 Z 分數…）
2. Pattern B/C/D/E 判定完全是硬 rule（結構形態 + 強度 + veto）
3. Conviction = current_score / entry_score 也是純公式
4. 結論：agent 在 loop 內只是把純函數 wrap 一層 natural language —— 浪費 token、引入隨機性、且無法高頻跑

Agent 在 cattrade 管道的**真正價值**在 loop 外：
- 看 journal 離線調參（`min_entry_score`、`max_close_pct_per_run` …）
- 外部訊號介入（Square 有反訊號、新聞 FUD → `lana close --pct`）

## 2. Cattrade Pattern 分類

來自 cattrade sheet 的「结构分歧榜」：

| Pattern | 含義 | 處理 |
|---|---|---|
| **A** | Early momentum（15m/1h 異動 + multi_volume 同向上） | +20 score |
| **B** | **大户领先做多** —— structure 形態 + 強度 > 10 | **主要進場訊號**（+40 base + strength） |
| **C** | 假突破（5m 衝高但 1h 沒跟上 + 短時衝擊佔比高） | **Veto**（不進場） |
| **D** | 大户领先做空 / 主动买领先空 | **立即全倉平**（持倉期間出現） |
| **E** | Pumped —— 1d + 1w 都在前 3 名 | **Veto**（不進場） / 持倉期間出現 → **全倉平** |

Pattern B 加成：
- `concentration > 2` → +10（大戶集中度高 = 倉位乾淨）
- `direction = 同向上 / 上拐` → +15（量價同向）
- `direction = 同向下 / 下拐` → −10（量價背離）
- 量 Z 分數在 sweet spot [1.5, 3.0] → +10；> 5.0 → −15（過熱）

Veto 條件：
- Pattern C：`5m rank <= 3` 且 1h 沒跟上 且 short_impact > 1.0
- Pattern E：`1d rank <= 3` 且 `1w rank <= 3`

## 3. Autonomous loop（`lana cattrade run`）設計

**目標**：cron 每 5 分鐘跑一次，無 agent 介入，完成選幣 / 開倉 / 減倉 / 平倉全流程。

### 每次 tick 流程

```
1. 抓 cattrade gsheet → pick_cattrade() → 排序候選
2. 查 Binance futures 持倉
3. 分支：
   A. 無持倉
      - top candidate score >= min_entry_score (40) → 開 LONG + 200U stop
      - journal 寫 open event（附 entry score / strength / concentration / patterns / oi）
      - 否則 skip
   B. 有持倉（必須 journal 找得到 open event，否則標記 unmanaged 跳過）
      對每個持倉：
      - current 從 cand_map 查（若消失 → 全倉平）
      - Pattern D 出現 → 全倉平
      - Pattern E 出現 → 全倉平
      - conviction = current.score / entry.score
        * >= 0.95 → hold
        * < 0.95:
           target_qty = entry.qty × conviction
           delta = current_qty - target_qty
           n_pct = min(delta / current_qty, 0.10)  # 單次 10% 上限
           若 n_pct < 0.02 → skip（不夠 cover fee）
           否則 partial close n_pct
4. 所有決策寫 journal
```

### 為什麼 conviction = current/entry？

推導過程，刪掉了幾個不好的做法：

**❌ 原始提案：PnL × signal_health 16 格 lookup table**
使用者：「你這樣不就其實可以直接寫 code 了？」
問題：過度工程，本質是在用表格模擬一個連續函數。

**❌ 中間提案：agent 每 tick 判 conviction 分**
使用者：「跟直接看來源資料算 score 有啥區別？」
問題：agent 判讀一個純數字會議題，只是徒增 latency 和隨機性。

**✅ 最終：conviction = current_score / entry_score**

理由：
- 訊號強度是 entry 的多少倍，就該持有 entry 部位的多少倍 —— 線性、無魔法數字
- 不管進場時 score 是 50 還是 100，healthy 都是比值 >= 0.95
- Partial close 數量自動隨劣化速度縮放：score 腰斬就減一半（上限 10%）

### 關鍵常數

| Knob | 預設值 | 意義 |
|---|---|---|
| `min_entry_score` | 40 | 低於就不進場（Pattern B base 就是 40，等於要求至少命中 B 或多管道加總） |
| `min_conviction_healthy` | 0.95 | 這之上不動作 |
| `max_close_pct_per_run` | 0.10 | 單次 tick 最多砍 10%（防止 gsheet 抖動造成雪崩賣出） |
| `min_close_pct` | 0.02 | 低於 2% 跳過（手續費） |

### 為什麼單次 10% 上限？

- gsheet 資料偶爾會跳（例如 cattrade sheet 更新有 lag）
- 10% 給容錯空間：連續 3 tick 仍可減 27%，夠快
- 避免「一個 bad data point 直接清倉」

### 為什麼要 journal？

conviction 公式需要 **entry score**，Binance API 不會記這個。journal 是 audit trail + 狀態儲存：

- `open` event：記 cattrade 分數 + patterns + oi + entry_price + qty
- `partial_close` event：記 close qty + mark price + conviction + reason
- `close` event：全倉平的理由（Pattern D/E/signal disappeared）

**Manual trades（`lana trade <SYM>`）不寫 journal** —— 這樣 cattrade run 看到「持倉沒 journal 紀錄」就標記 `skip_unmanaged`，不會去碰手動開的倉位。兩套管道自然隔離。

## 4. 命令總覽

**Square 管道（agent 驅動 / 手動）**
- `lana scan` —— Square + OI + gainers 綜合（60 min cache）
- `lana square` / `lana signals` / `lana trending` —— 子訊號 debug
- `lana trade <SYM>` —— 手動開 LONG + 200U 止損
- `lana close <SYM> --pct N` —— 手動平 N% 倉位

**Cattrade 管道（cron 純程式）**
- `lana cattrade scan` —— 看候選（read-only）
- `lana cattrade run` —— 一輪 tick（cron 用）
- `lana cattrade journal` —— 查進出場紀錄

**共用**
- `lana positions` —— 查當前持倉

## 5. Cron 設定

```cron
*/5 * * * * cd /path/to/lana-copycat && uv run lana cattrade run --no-dry-run >> logs/cron.log 2>&1
```

或 daemon 模式：

```bash
uv run lana cattrade daemon --interval 300 --no-dry-run
```

`run` 與 `daemon` 預設 `--dry-run=True`（防呆）—— 只 log 決策不下單。要真跑要顯式 `--no-dry-run`。

### 為什麼是 5 分鐘，不是 3 分鐘？

| 面向 | 3 min | 5 min |
|---|---|---|
| gsheet refresh cadence | 常撈到同一份資料 | 基本對齊來源 |
| Partial close 反應速度 | 連續 3 tick → 減 27%（9min） | 連續 3 tick → 減 27%（15min）—— 仍夠快 |
| Rate limit | 無壓力 | 無壓力 |
| Agent 加工機會 | 更細但無 alpha | 正好 |

除非未來加了分鐘級的價格 breakdown 訊號，否則 5 min 是合理起點。

## 6. 部署現況

**目前：100% Binance Futures testnet**（`config.yaml` → `binance.testnet: true`）
- API keys：testnet（測試網獨立申請，production key 無法用）
- 所有下單走 `https://testnet.binancefuture.com/fapi`
- 不碰真實資金，journal 裡的 entry/exit 都是 paper trade

**上 live 流程**（未來）：
1. `config.yaml` → `binance.testnet: false`
2. `.env` 換成 production Binance Futures API keys
3. 先用最小倉位（`position_size_pct: 0.01`）跑一兩週
4. 觀察 journal & PnL → 再放大

## 7. 已知侷限 / TODO

- **Stop-loss 是 ExchangeSide stop-market**，不是 trailing stop。進場後 price 不會調整 —— 如果倉位 green 了，應該考慮上移 stop。
- **沒接 Square 訊號介入 cattrade 管道**。理論上 Square 出現反訊號（討論熱度崩了）該觸發 partial close，但目前是兩套完全獨立。
- **journal 沒 rollover**：長期跑下來 JSONL 會越來越大。可考慮按月切檔。
- **沒 backtest**：純看 journal live 結果判斷 knob 值。理想狀況是把 cattrade sheet 歷史資料回放跑一遍。
- **Pattern A 沒進入 loop**：目前 Pattern A（early momentum）只加 score，但如果手上沒部位且 top 是 A-only（沒 B），也會進場 —— 這是否太激進可以再看。

## 8. 決策歷史（避免重蹈覆轍）

1. **合併訊號 → 拆成兩套**：一開始想把 cattrade scores 乘以權重塞進 Square scoring 的第四個維度。拆開之後清爽非常多，且避免「因為 cattrade 分高所以 Square 沒熱度也進場」這種奇怪交集。
2. **Agent driven loop → cron 純程式**：最初想做 agent 每 N 分鐘喚醒判 conviction。砍掉是因為資料純結構化，agent 沒加值。
3. **PnL lookup table → conviction 比值**：16 格 if/else 被砍成一個 `/` 運算。
4. **「tick」/「rebalance」→「run」**：命名被使用者拒了兩輪，最後 `run` 通過。
5. **closePosition=True 的 algoId 陷阱**：Binance 條件單回傳 `algoId` 不是 `orderId`，直接 `.get("orderId")` 會 KeyError。
6. **quantityPrecision**：`_calc_quantity` 寫死 round(qty, 3) 會被 ATUSDT（精度 0）踩爆。現在從 `futures_exchange_info()` 查+cache。
