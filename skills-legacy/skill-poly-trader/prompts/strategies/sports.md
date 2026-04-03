# Sports Strategy

## 任務

掃描單場體育市場，尋找在賽前仍未完全反映最新資訊的錯價。

這不是一般事件型 strategy。
重點不是「最後誰會贏」的抽象直覺，而是：

- 傷病
- 先發 / 輪休
- 賽程密度
- 主客場與旅行
- 天氣
- 臨場資訊

這些資訊是否還沒有被市場完全吃掉。

## 這個 strategy 在做什麼

- 從較大的 sports working set 裡先拿 coverage
- working set 應優先保留三種新鮮度訊號：最近更新、最近建立、以及近結算但仍值得看的市場
- 再把所有符合條件的市場放進 shortlist
- 依優先順序對 shortlist 逐一做 WebSearch
- 如果 research 後仍沒有明確 edge，就直接 `NO_TRADE`

## 市場選擇

**優先：**

- 單場對戰
- 交易量高
- 距離結算近
- 盤面結構簡單、問題敘述清楚

**排除：**

- 你沒有足夠背景可判斷的賽事
- 只是因為快開賽或成交量高，但你沒有任何可研究的新資訊
- same-day 市場，但你沒有可依賴的 lineups / injury / weather 來源
- 沒有可研究的新資訊，只能靠感覺猜
- 太多同質比賽，不知道先看哪一場時
- 你說不清楚為什麼市場還沒 fully price in 的盤

## 執行方式

1. 先跑 `uv run python -m skill_poly_trader_v2 markets --profile sports --limit 50`
2. 快速掃過整個 working set，不要先寫死只研究幾個
3. 只要市場符合下面條件，就放進 shortlist：
   - 有明確可研究的新資訊向量
   - 流動性與成交量夠
   - 問題結構清楚
   - 不是同一 thesis 的重複盤
   - 你有能力判斷，不是純憑感覺
4. 依資訊強度、流動性、時間敏感度排序後，對 shortlist 逐一研究
5. 對 shortlisted candidate 跑 `uv run python -m skill_poly_trader_v2 market --slug <slug>`
6. 在形成 probability 之前，先做 WebSearch
7. 至少回答這些問題：
   - 有沒有最新傷病、輪休、禁賽或先發異動
   - 有沒有賽程密度 / 背靠背 / 旅行劣勢
   - 有沒有天氣或場地因素
   - 市場價格有沒有已經把這些因素完全反映
8. 只有在你能清楚說明「新資訊 + 市場尚未完全反映」時，才考慮交易

## Shortlist 原則

- shortlist 的大小由市場品質決定，不由固定配額決定
- 如果符合條件的只有 2 個，就只研究 2 個
- 如果符合條件的有 10 個，就都進 shortlist，再按優先級逐一處理
- 不要為了控制數量，把明顯值得研究的市場排除在外

## Edge 原則

- 不因為盤很熱門就做
- 不因為某隊是強隊就做
- 如果 research 做完後，你仍然只是模糊覺得某邊比較強，就不算 edge
- 如果市場已經接近你自己的概率判斷，就 `NO_TRADE`

## 持有與風控

- 預設不做長天期持有
- 如果這筆本質上更像收斂交易，要先想好出場條件
- 如果你沒有明確的賽前資訊 edge，就不要硬持有到最後

## Journal

- 這筆交易標註 `[sports]`
- Research 要寫清楚你查了哪些 injury / lineup / schedule / weather / context
- Analysis 要寫清楚市場錯在哪裡，而不是只寫「看好某隊」
