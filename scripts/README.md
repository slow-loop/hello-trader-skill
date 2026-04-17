# Nanobot Setup

這個目錄提供一套較安全的 `nanobot` 開發方式：

- `nanobot` workspace 不直接用 repo root
- workspace 放在 repo 內的 [`.nanobot-workspace`](/Users/cw/Documents/GitHub/hello-trader-skill/.nanobot-workspace)
- workspace 的 `skills/` 是 symlink 到 repo 的 [skills](/Users/cw/Documents/GitHub/hello-trader-skill/skills)
- `nanobot` 不需要開通用 shell，改接 `web-reader` package 內建的通用 MCP server

## 結構

```text
hello-trader-skill/
  .nanobot-workspace/
    config.json
    memory/
    sessions/
    skills -> ../skills
  skills/
    wallstreet-research/
  scripts/
    run_nanobot.py
    pyproject.toml
```

## 為什麼這樣做

- 避免把整個 repo root 當成 nanobot workspace，減少 runtime 檔案污染
- skill 仍然只維護一份，直接放在 repo `skills/`
- nanobot 從 workspace 掃 skill 時，仍然能看到 repo 裡的 skill
- 直接重用 `web-reader` package 的 MCP，不再維護 repo-local `trader_mcp.py`
- 用 MCP tools 取代自由 shell，讓 agent 只能呼叫固定能力

## Workspace 行為

[run_nanobot.py](/Users/cw/Documents/GitHub/hello-trader-skill/scripts/run_nanobot.py) 預設會使用：

```text
/Users/cw/Documents/GitHub/hello-trader-skill/.nanobot-workspace
```

啟動時會自動確保這些內容存在：

- `config.json`
- `memory/`
- `sessions/`
- `skills/`

其中 `skills/` 的處理方式是：

- 如果 `skills` 已經是 symlink，保留
- 如果 `skills` 不存在，自動建立成指向 repo `skills/` 的 symlink
- 如果 `skills` 已經是實體資料夾，不會強制覆蓋

## MCP Server

現在改用 `web-reader` package 內建的 `stdio` MCP server：`web-reader-mcp`。

目前提供這些通用 tools：

- `read_url`
- `read_config`
- `web_reader_server_info`

台股 trader workflow 應透過 `read_config` 指向本 repo 的來源設定：

- config: `/Users/cw/Documents/GitHub/hello-trader-skill/skills/tw-trader/data/config/sources.tw.yaml`
- sentiment tags: `sentiment`
- macro tags: `tw,macro`
- research tags: `research`

## 安裝

在 `scripts/` 目錄同步依賴：

```bash
cd /Users/cw/Documents/GitHub/hello-trader-skill/scripts
uv sync
```

## Nanobot Config

`run_nanobot.py` 現在會依序尋找：

1. `--config` 指定的路徑
2. workspace 內的 [`.nanobot-workspace/config.json`](/Users/cw/Documents/GitHub/hello-trader-skill/.nanobot-workspace/config.json)
3. `~/.nanobot/config.json`

第一次執行時，workspace 內若還沒有 `config.json`，會自動建立一份預設設定：

```json
{
  "tools": {
    "exec": {
      "enable": false
    },
    "mcpServers": {
      "web-reader": {
        "command": "uv",
        "args": [
          "run",
          "--project",
          "/Users/cw/Documents/GitHub/hello-trader-skill/scripts",
          "web-reader-mcp"
        ],
        "enabledTools": [
          "read_url",
          "read_config",
          "web_reader_server_info"
        ],
        "toolTimeout": 120
      }
    }
  }
}
```

所以這個 repo 現在可以把 nanobot config 直接放在專案內的 workspace，不必依賴 home 目錄。

## 啟動

直接跑：

```bash
cd /Users/cw/Documents/GitHub/hello-trader-skill/scripts
uv run python run_nanobot.py --message "用 wallstreet-research 做台積電研究"
```

也可以指定 workspace：

```bash
uv run python run_nanobot.py \
  --workspace /Users/cw/Documents/GitHub/hello-trader-skill/.nanobot-workspace \
  --message "用 wallstreet-research 做台積電研究"
```

也可以顯式指定 config：

```bash
uv run python run_nanobot.py \
  --config /Users/cw/Documents/GitHub/hello-trader-skill/.nanobot-workspace/config.json \
  --message "用 wallstreet-research 做台積電研究"
```

## Skill 使用方式

[wallstreet-research](/Users/cw/Documents/GitHub/hello-trader-skill/skills/wallstreet-research/SKILL.md) 應優先使用通用 MCP tools：

- `read_url`
- `read_config`
- `web_reader_server_info`

不要在 skill 內再教 agent 直接跑 shell CLI。

## 驗證

已驗證：

- MCP server 可以被 `stdio` client 連上
- `list_tools` 可列出 `web-reader` 通用 tools
- `read_url` 可直接讀單一 URL 或 pseudo-URL
- `read_config` 可讀取 `skills/tw-trader/data/config/sources.tw.yaml`
