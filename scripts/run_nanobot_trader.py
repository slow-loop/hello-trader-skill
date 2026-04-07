from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

try:
    from scripts.trader_run_common import (
        DEFAULT_PROMPT_FILE,
        PROMPT_PRESETS,
        REPO_ROOT,
        build_run_message,
        resolve_prompt_path,
    )
except ModuleNotFoundError:
    from trader_run_common import (  # type: ignore[no-redef]
        DEFAULT_PROMPT_FILE,
        PROMPT_PRESETS,
        REPO_ROOT,
        build_run_message,
        resolve_prompt_path,
    )

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_WORKSPACE = REPO_ROOT / ".nanobot-workspace"
DEFAULT_ENV_CANDIDATES = (
    REPO_ROOT / ".env",
    REPO_ROOT / "scripts" / ".env",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TW trader skill through an external nanobot runtime.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="Workspace path passed to nanobot. Defaults to repo-local .nanobot-workspace.",
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("TRADER_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Backend2 base URL. Defaults to TRADER_BACKEND_URL or http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional .env file. Defaults to repo .env, then scripts/.env if present.",
    )
    parser.add_argument(
        "--nanobot-config",
        type=Path,
        default=None,
        help="Optional nanobot config.json path. Defaults to ~/.nanobot/config.json.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=DEFAULT_PROMPT_FILE,
        help="Prompt file to execute relative to the repo root.",
    )
    parser.add_argument(
        "--mode",
        choices=sorted(PROMPT_PRESETS),
        default=None,
        help="Convenience shortcut for common prompt files.",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Extra instruction appended after the trader-run scaffold.",
    )
    parser.add_argument(
        "--session-key",
        default="",
        help="Nanobot session key used for this run. Defaults to a fresh timestamped session.",
    )
    parser.add_argument(
        "--backend-healthcheck",
        action="store_true",
        help="Run an optional GET /health preflight before starting the agent.",
    )
    parser.add_argument(
        "--skip-backend-healthcheck",
        action="store_false",
        dest="backend_healthcheck",
        help="Deprecated alias kept for compatibility. Healthcheck is off by default.",
    )
    parser.add_argument(
        "--print-message",
        action="store_true",
        help="Print the fully rendered prompt message before the run.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream assistant text to stdout while the run is in progress.",
    )
    return parser.parse_args()


def load_environment(env_file: Path | None) -> list[Path]:
    loaded: list[Path] = []
    candidates = [env_file.expanduser()] if env_file else list(DEFAULT_ENV_CANDIDATES)

    for candidate in candidates:
        resolved = candidate.resolve()
        if env_file and not resolved.exists():
            raise SystemExit(f".env file not found: {resolved}")
        if resolved.exists() and load_dotenv(resolved, override=False):
            loaded.append(resolved)

    return loaded


def ensure_backend_healthy(backend_url: str) -> None:
    health_url = backend_url.rstrip("/") + "/health"
    request = urllib.request.Request(health_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise SystemExit(f"Backend healthcheck failed: {health_url} returned {response.status}")
    except urllib.error.URLError as exc:
        raise SystemExit(
            "Backend healthcheck failed. Start backend2 first, for example:\n"
            "  cd /Users/cw/Documents/GitHub/hello-trader-skill/backend2\n"
            "  uv run uvicorn backend2.main:app --reload\n"
            f"Health URL: {health_url}\n"
            f"Original error: {exc}"
        ) from exc


def load_nanobot_class():
    try:
        from nanobot import Nanobot

        return Nanobot
    except Exception as exc:
        raise SystemExit(
            "Unable to import nanobot.\n"
            "Install it in the current environment first, for example:\n"
            "  uv pip install -e /Users/cw/Documents/GitHub/nanobot\n"
            f"Original error: {exc}"
        ) from exc


def build_workspace_config() -> dict[str, object]:
    return {
        "tools": {
            "exec": {"enable": False},
            "mcpServers": {
                "web-reader": {
                    "command": "uv",
                    "args": [
                        "run",
                        "--project",
                        str((REPO_ROOT / "scripts").resolve()),
                        "web-reader-mcp",
                    ],
                    "enabledTools": [
                        "read_url_content",
                        "read_config",
                        "web_reader_server_info",
                    ],
                    "toolTimeout": 120,
                }
            },
        }
    }


def ensure_workspace_layout(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "sessions").mkdir(parents=True, exist_ok=True)

    skills_path = workspace / "skills"
    target_skills = REPO_ROOT / "skills"
    if skills_path.is_symlink():
        pass
    elif skills_path.exists():
        pass
    else:
        skills_path.symlink_to(target_skills, target_is_directory=True)

    config_path = workspace / "config.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(build_workspace_config(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def resolve_nanobot_config(args: argparse.Namespace) -> Path | None:
    workspace = args.workspace.expanduser().resolve()
    candidates = []
    if args.nanobot_config is not None:
        candidates.append(args.nanobot_config.expanduser().resolve())
    candidates.append((workspace / "config.json").resolve())
    candidates.append((Path.home() / ".nanobot" / "config.json").resolve())

    for path in candidates:
        if path.exists():
            return path

    searched = "\n".join(f"- {path}" for path in candidates)
    raise SystemExit(f"Nanobot config not found. Searched:\n{searched}")


def build_hooks(stream: bool):
    if not stream:
        return [], None

    from nanobot.agent.hook import AgentHook

    class LiveConsoleHook(AgentHook):
        def __init__(self) -> None:
            self.streamed_any = False
            self._line_open = False

        def wants_streaming(self) -> bool:
            return True

        def _close_line(self) -> None:
            if self._line_open:
                print("", flush=True)
                self._line_open = False

        async def on_stream(self, context, delta: str) -> None:
            if not delta:
                return
            if not self._line_open:
                print("\nassistant> ", end="", flush=True)
                self._line_open = True
            print(delta, end="", flush=True)
            self.streamed_any = True

        async def on_stream_end(self, context, *, resuming: bool) -> None:
            if not resuming:
                self._close_line()

        async def before_execute_tools(self, context) -> None:
            self._close_line()

    hook = LiveConsoleHook()
    return [hook], hook


async def close_bot_mcp(bot) -> None:
    close_mcp = getattr(getattr(bot, "_loop", None), "close_mcp", None)
    if close_mcp is None:
        return
    await close_mcp()


async def run_agent(args: argparse.Namespace) -> int:
    prompt_path = resolve_prompt_path(args.mode, args.prompt_file)
    workspace = args.workspace.expanduser().resolve()
    ensure_workspace_layout(workspace)
    nanobot_config = resolve_nanobot_config(args)

    if args.backend_healthcheck:
        ensure_backend_healthy(args.backend_url)

    os.environ["TRADER_BACKEND_URL"] = args.backend_url

    Nanobot = load_nanobot_class()
    bot = Nanobot.from_config(config_path=nanobot_config, workspace=workspace)
    session_key = args.session_key.strip() or f"sdk:trader-poc:{int(asyncio.get_running_loop().time())}"
    print(f"[session] {session_key}", flush=True)
    print(f"[config] {nanobot_config}", flush=True)
    message = build_run_message(
        prompt_path,
        context_lines=(
            "Repo root: {repo_root}",
            f"Nanobot workspace: {workspace}",
            "Primary trader prompt: {prompt_path}",
            f"Backend URL: {args.backend_url}",
        ),
        execution_rules=(
            "Read `{prompt_path}` first and follow it as the primary instruction file.",
            "If that file references other prompt files, read and apply them too.",
            "Prefer the repo's CLI/API path for market, watchlist, and account state.",
            "When you need the trader CLI, use commands in this form from the repo root: `uv run --project skills/tw-trader python -m tw_trader.cli <command>`.",
            f"Use `{args.backend_url}` as the backend target for CLI/API calls when those commands need it. Do not assume the backend is available before you try the repo workflow. If a backend-dependent command fails, report that blocker in the output.",
            "Do not place or modify orders, watchlist items, journals, or lessons in this PoC. This is a read-only trader-skill validation run.",
            "If a prompt step would normally mutate state, explain what you would have done instead.",
        ),
        extra_message=args.message,
    )
    hooks, stream_hook = build_hooks(args.stream)

    if args.print_message:
        print("=== Rendered Message ===")
        print(message)
        print("========================")

    try:
        result = await bot.run(message, session_key=session_key, hooks=hooks)
        if stream_hook is None or not stream_hook.streamed_any:
            print(result.content)
    finally:
        await close_bot_mcp(bot)
    return 0


def main() -> int:
    args = parse_args()
    load_environment(args.env_file)
    try:
        return asyncio.run(run_agent(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
