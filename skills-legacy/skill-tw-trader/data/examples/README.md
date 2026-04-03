# Examples

這裡放的是給人看、給 agent 參考資料形狀用的 sample data，不是執行中的真實資料。

## 內容

- `account/watchlist.yaml`
  真實版 watchlist 範例，含 thesis / trigger / invalidation。
- `account/lessons.md`
  交易規則與教訓整理範例。
- `account/state/ledger.json`
  帳戶真實狀態 sample。
- `account/state/equity.json`
  每日資產快照 sample。
- `account/journals/*.yaml`
  journal 範例，使用 append list 形式。
- `account/research/*.md`
  深度研究範例，含單一股票與主題研究。
- `account/market_snapshots/*.yaml`
  `cli market` 產出的快照範例。
- `config/technical_config.yaml`
  技術分析設定 sample。
- `posts/*.yaml`
  social post 範例。

## 用法

- 想理解資料結構時，先看這裡。
- 想新增 prompt 或工具時，可直接用這裡的 sample 當 fixture。
- 真實執行資料請看 `data/account/`、`data/config/`、`data/market/`。
