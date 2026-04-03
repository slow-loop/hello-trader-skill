---
name: persona-social
description: >
  自主經營「下班後的 Alpha」Threads 頻道。每次執行時主動搜尋市場狀況、決定當日發文策略、
  撰寫 3 篇完稿，並將貼文寫入 data/posts/。
  當使用者說「發文」、「今天的貼文」、「經營頻道」、「產文」時立即觸發。
  不需要使用者指定細節，直接完整執行整個流程。
---

# 下班後的 Alpha — Threads 頻道自主經營

本 skill 會完整執行今日的頻道經營工作，從市場研究到完稿輸出一氣呵成，不需等待使用者確認每一步。

## 工作目錄

專案根目錄：`/Users/cw/Documents/GitHub/hello-invest/apps/skill-persona-social`
所有檔案路徑都相對於此目錄

## References

**執行前必讀**

| 檔案 | 內容 | 何時讀 |
|------|------|--------|
| `references/channel-brand.md` | 品牌定位、發文路線、固定話術、品質清單 | 執行前必讀 |
| `references/posts-examples.md` | 貼文範例庫（few-shot） | 撰寫 posts 時參考語氣與結構 |
| `references/reply-examples.md` | 留言回覆範例庫（few-shot） | 需要回覆讀者留言時參考 |

---

## 執行流程

### Step 1：掌握今日市場狀況

請使用 `browser`，瀏覽以下資訊：
- 今日財經話最新新聞 (https://m.cnyes.com/news/cat/headline)
- 散戶社群風向（Reddit r/wallstreetbets、r/investing 或 X 財經討論）

### Step 2：撰寫 3 篇完稿並儲存

語氣與結構參考 `references/post-examples.md`

發布時間固定：08:00 / 12:30 / 21:00

將今日 3 篇完稿寫入 `posts/YYYY-MM-DD.md`，檔案格式：

```markdown
# YYYY-MM-DD 今日貼文

> 市場情緒：{一句話總結}
> 路線組合：{篇1路線} / {篇2路線} / {篇3路線}

---

## 第 1 篇｜08:00｜路線 {X}

{完稿內容}

---

## 第 2 篇｜12:30｜路線 {X}

{完稿內容}

---

## 第 3 篇｜21:00｜路線 {X}

{完稿內容}
```

完成後，回報檔案路徑，讓使用者可以直接點開確認

