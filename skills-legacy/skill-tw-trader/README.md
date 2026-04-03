# Skill-TW-Trader

Autonomous Taiwan Stock Trading Agent.

## Features
- **Autonomous Reasoning**: Wake up periodically to analyze market state.
- **TW Stock Focused**: Optimized for the Taiwan stock market (RSI, MA, etc.).
- **Disciplined Execution**: Automated stop-loss and position management.
- **Journaling**: Detailed daily journals of all thoughts and actions.
- **Threads Integration**: Auto-generated social media posts for trade recaps.

## Project Structure
- `backend/`: FastAPI server and Agent Reasoning Loop.
- `ui/`: (Coming Soon) Svelte-based dashboard.
- `prompts/`: Core instruction set (System, Persona, Workflow).
- `memory/`: (In backend) Local persistent storage for Agent state and history.

## Getting Started

### Environment Variables

Create a `.env` file:

```env
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# LINE
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
```

### Telegram Setup

1. Telegram 搜尋 `@BotFather` → `/newbot` → 取得 `TELEGRAM_BOT_TOKEN`
2. Telegram 搜尋 `@userinfobot` → 取得自己的 `TELEGRAM_CHAT_ID`
3. 測試 push：
   ```bash
   uv run python -m skill_tw_trader.cli notify \
     --agent trading --action test --summary "Hello"
   ```

### LINE Setup

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 建立 Provider → Messaging API channel
3. **Basic settings** → 取得 `LINE_CHANNEL_SECRET`
4. **Messaging API** → Issue → 取得 `LINE_CHANNEL_ACCESS_TOKEN`
5. [LINE Official Account Manager](https://manager.line.biz/) → 回應設定：
   - 聊天：關閉
   - 自動回應訊息：關閉
   - Webhook：開啟

### ngrok (LINE webhook 本地測試)

免費固定 domain：

1. 申請 [ngrok](https://ngrok.com/) 帳號 → Dashboard → Domains → 取得固定 domain
2. 啟動：
   ```bash
   ngrok http 8000 --domain=你的固定domain.ngrok-free.app
   ```
3. LINE Console → Messaging API → Webhook URL：
   ```
   https://你的固定domain.ngrok-free.app/webhook/line
   ```
4. 按 Verify

### Start Server

```bash
uv run uvicorn skill_tw_trader.api:app --reload --loop asyncio
```
