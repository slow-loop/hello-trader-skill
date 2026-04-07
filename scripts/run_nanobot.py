from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from nanobot import Nanobot
from nanobot.agent.hook import AgentHook

try:
    from scripts.trader_run_common import REPO_ROOT
except ModuleNotFoundError:
    from trader_run_common import REPO_ROOT  # type: ignore[no-redef]

DEFAULT_SESSION_KEY_PREFIX = "sdk:trader-poc"
DEFAULT_WORKSPACE = REPO_ROOT / ".nanobot-workspace"
DEFAULT_WORKSPACE_CONFIG = DEFAULT_WORKSPACE / "config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TW trader skill through nanobot.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="Workspace path passed to nanobot. Defaults to repo-local .nanobot-workspace.",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Extra instruction appended after the trader-run scaffold.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Nanobot config path. Defaults to workspace config.json, then ~/.nanobot/config.json.",
    )
    parser.add_argument(
        "--session-key",
        default="",
        help="Session key to resume. Defaults to a fresh timestamped session per run.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Overall wall-clock timeout in seconds for the full agent run. Use 0 to disable.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Disable the end-of-run execution report.",
    )
    return parser.parse_args()


def build_stream_hook(agent_hook_cls: type[AgentHook]) -> AgentHook:
    class LiveConsoleHook(agent_hook_cls):
        def __init__(self) -> None:
            self.streamed_any = False
            self._line_open = False
            self._reasoning_line_open = False
            self._iteration_start = time.monotonic()
            self._tool_started_at: dict[str, float] = {}
            self.iteration_reports: list[dict[str, object]] = []
            self.final_stop_reason: str | None = None
            self.final_error: str | None = None

        def wants_streaming(self) -> bool:
            return True

        def _close_line(self) -> None:
            if self._line_open:
                print("", flush=True)
                self._line_open = False
            if self._reasoning_line_open:
                print("", flush=True)
                self._reasoning_line_open = False

        @staticmethod
        def _tool_key(tool_call) -> str:
            payload = json.dumps(tool_call.arguments, ensure_ascii=False, sort_keys=True)
            return f"{tool_call.name}:{payload}"

        @staticmethod
        def _truncate(text: str, limit: int = 160) -> str:
            clean = " ".join(text.split())
            if len(clean) <= limit:
                return clean
            return clean[:limit] + "..."

        async def before_iteration(self, context) -> None:
            self._iteration_start = time.monotonic()
            print(f"\n[iter {context.iteration + 1}] thinking", flush=True)

        async def on_stream(self, context, delta: str) -> None:
            if not delta:
                return
            if not self._line_open:
                print("\nassistant> ", end="", flush=True)
                self._line_open = True
            print(delta, end="", flush=True)
            self.streamed_any = True

        async def on_reasoning_stream(self, context, delta: str) -> None:
            if not delta:
                return
            if self._line_open:
                print("", flush=True)
                self._line_open = False
            if not self._reasoning_line_open:
                print("\nreasoning> ", end="", flush=True)
                self._reasoning_line_open = True
            print(delta, end="", flush=True)
            self.streamed_any = True

        async def on_stream_end(self, context, *, resuming: bool) -> None:
            if not resuming:
                self._close_line()

        async def before_execute_tools(self, context) -> None:
            self._close_line()
            for tool_call in context.tool_calls:
                key = self._tool_key(tool_call)
                self._tool_started_at[key] = time.monotonic()
                args_preview = self._truncate(
                    json.dumps(tool_call.arguments, ensure_ascii=False, sort_keys=True),
                    limit=120,
                )
                print(
                    f"[iter {context.iteration + 1}] tool start: {tool_call.name}({args_preview})",
                    flush=True,
                )

        async def after_iteration(self, context) -> None:
            elapsed = time.monotonic() - self._iteration_start
            usage = context.usage or {}
            usage_summary = {
                "prompt": int(usage.get("prompt_tokens", 0) or 0),
                "completion": int(usage.get("completion_tokens", 0) or 0),
                "cached": int(usage.get("cached_tokens", 0) or 0),
            }
            report: dict[str, object] = {
                "iteration": context.iteration + 1,
                "elapsed_s": round(elapsed, 2),
                "stop_reason": context.stop_reason,
                "usage": usage_summary,
                "tools": [],
            }
            tools = report["tools"]
            assert isinstance(tools, list)
            for tool_call, event in zip(context.tool_calls, context.tool_events, strict=False):
                key = self._tool_key(tool_call)
                started_at = self._tool_started_at.pop(key, None)
                tool_elapsed = None if started_at is None else round(time.monotonic() - started_at, 2)
                status = (event or {}).get("status", "unknown")
                detail = self._truncate((event or {}).get("detail", ""))
                print(
                    f"[iter {context.iteration + 1}] tool end: {tool_call.name} status={status}"
                    + (f" elapsed={tool_elapsed}s" if tool_elapsed is not None else "")
                    + (f" detail={detail}" if detail else ""),
                    flush=True,
                )
                tools.append(
                    {
                        "name": tool_call.name,
                        "status": status,
                        "elapsed_s": tool_elapsed,
                        "detail": detail,
                    }
                )
            print(
                f"[iter {context.iteration + 1}] done: elapsed={elapsed:.2f}s "
                f"prompt={usage_summary['prompt']} completion={usage_summary['completion']} "
                f"cached={usage_summary['cached']}",
                flush=True,
            )
            self.iteration_reports.append(report)
            self.final_stop_reason = context.stop_reason
            self.final_error = context.error

    return LiveConsoleHook()


def print_report(hook: AgentHook, timed_out: bool) -> None:
    iteration_reports = getattr(hook, "iteration_reports", [])
    final_error = getattr(hook, "final_error", None)
    final_stop_reason = getattr(hook, "final_stop_reason", None)

    print("\n=== Execution Report ===", flush=True)
    if timed_out:
        print("status: timed_out", flush=True)
    elif final_error:
        print(f"status: error ({final_error})", flush=True)
    else:
        print(f"status: {final_stop_reason or 'completed'}", flush=True)
    print(f"iterations: {len(iteration_reports)}", flush=True)

    for report in iteration_reports:
        usage = report["usage"]
        tools = report["tools"]
        print(
            f"- iter {report['iteration']}: elapsed={report['elapsed_s']}s "
            f"prompt={usage['prompt']} completion={usage['completion']} cached={usage['cached']}",
            flush=True,
        )
        for tool in tools:
            line = f"  tool {tool['name']}: {tool['status']}"
            if tool["elapsed_s"] is not None:
                line += f" {tool['elapsed_s']}s"
            if tool["detail"]:
                line += f" | {tool['detail']}"
            print(line, flush=True)


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


def resolve_config_path(workspace: Path, configured_path: Path | None) -> Path:
    candidates: list[Path] = []
    if configured_path is not None:
        candidates.append(configured_path.expanduser().resolve())
    candidates.append((workspace / "config.json").resolve())
    candidates.append((Path.home() / ".nanobot" / "config.json").resolve())

    for path in candidates:
        if path.exists():
            return path

    searched = "\n".join(f"- {path}" for path in candidates)
    raise SystemExit(f"Nanobot config not found. Searched:\n{searched}")


async def close_bot_mcp(bot: Nanobot) -> None:
    close_mcp = getattr(getattr(bot, "_loop", None), "close_mcp", None)
    if close_mcp is None:
        return
    await close_mcp()


async def run_agent(args: argparse.Namespace) -> int:
    workspace = args.workspace.expanduser().resolve()
    ensure_workspace_layout(workspace)
    config_path = resolve_config_path(workspace, args.config)

    hook = build_stream_hook(AgentHook)
    bot = Nanobot.from_config(config_path=config_path, workspace=workspace)
    session_key = args.session_key.strip() or f"{DEFAULT_SESSION_KEY_PREFIX}:{int(time.time())}"
    print(f"[session] {session_key}", flush=True)
    print(f"[config] {config_path}", flush=True)
    timed_out = False
    try:
        run_coro = bot.run(args.message, session_key=session_key, hooks=[hook])
        if args.timeout and args.timeout > 0:
            result = await asyncio.wait_for(run_coro, timeout=args.timeout)
        else:
            result = await run_coro
        if not hook.streamed_any:
            print(result.content)
    except asyncio.TimeoutError:
        timed_out = True
        print(f"\n[timeout] agent run exceeded {args.timeout}s and was cancelled", flush=True)
    finally:
        await close_bot_mcp(bot)
        if not args.no_report:
            print_report(hook, timed_out=timed_out)
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run_agent(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
