# Promote Experiment → Production Strategy

任務：把通過驗證的 experiment 出貨到 `us-trader/data/strategies/<name>.yaml`，更新 ACTIVE 指標。

## 命名規則

```
<family>_<Nf>_<train-window>_<stage><iter>
```

| 欄位 | 說明 | 例子 |
|---|---|---|
| family | 策略族 | `mom`, `pead`, `rev` |
| Nf | factor 數 | `2f`, `3f` |
| train-window | IC 訓練窗口 | `2021-2024` |
| stage+iter | 生命週期階段 | `r1`=research, `p1`=paper, `l1`=live |

例：`mom_2f_2021-2024_r1` → `mom_2f_2021-2024_p1` → `mom_2f_2021-2024_l1`

## 生命週期

```
research (r)  →  paper (p)  →  live (l)
     IC 驗證完        forward 30d       實盤上線
```

## 流程

### 1. 挑候選 experiment

```bash
uv run lab list-experiments
```

### 2. Checklist（缺一項 → 停，寫回 BACKTEST 流程）

**research → paper：**
- [ ] IC(5D) > 0.03，t-stat > 2.0，at least 200 samples
- [ ] Backtest Sharpe > 0.5（含 2022 bear period）
- [ ] Factor 有語意解釋，不是 curve-fit
- [ ] `reflection.known_issues` 已填寫

**paper → live：**
- [ ] 30+ 天 paper trade，signal log 存在 journal
- [ ] OOS IC（未見過的 period）不 decay > 50%
- [ ] Walk-forward train vs test Sharpe 差 < 0.5
- [ ] Max DD < 20%（production 含 ATR stops）
- [ ] 和前任 live 版對比過

### 3. Promote

```bash
uv run lab promote \
  data/experiments/2026-04-24_momentum_v2 \
  --name mom_2f_2021-2024_r1 \
  --stage research \
  --approved-by human
```

這會：
- 寫 `us-trader/data/strategies/mom_2f_2021-2024_r1.yaml`
- 補上 `promoted_at`, `promoted_from`, `approved_by`, `backtest_summary`, `stage`
- 更新 `ACTIVE.yaml`

### 4. 填 reflection

Promote 後手動在 YAML 補充或更新 `reflection` block：

```yaml
reflection:
  known_issues:
    - <具體問題，下次開發者看得懂>
  next_before_paper:
    - <paper 之前要做什麼>
  next_before_live:
    - <live 之前要做什麼>
```

### 5. 交棒

Promote 完結束。us-trader 下次喚醒自動讀到新 ACTIVE。

## 禁忌

- 不要直接編輯 `us-trader/data/strategies/*.yaml`，要改就回 experiment 流程
- 不要 promote 同名策略兩次（CLI 會擋）
- 不要跳過 reflection block，這是給下次開發者的 model card
