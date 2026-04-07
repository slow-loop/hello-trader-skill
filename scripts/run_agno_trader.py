#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "agno",
#   "openai",
#   "python-dotenv",
# ]
# ///

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.skills import LocalSkills, Skills

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

TRADER_ROOT = REPO_ROOT / "skills" / "tw-trader"
DEFAULT_SKILL_PATH = REPO_ROOT / "skills" / "tw-trader-agno"
DEFAULT_ENV_CANDIDATES = (
    REPO_ROOT / ".env",
    REPO_ROOT / "scripts" / ".env",
)
DEFAULT_MODEL = "openai/gpt-5-mini"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the TW trader workflow through Agno using OpenRouter.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=REPO_ROOT,
        help="Workspace path referenced in the operator prompt. Defaults to this repo root.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional .env file. Defaults to repo .env, then scripts/.env if present.",
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
        "--session-id",
        default="agno:trader-poc",
        help="Agno session id used for this run.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL),
        help=f"OpenRouter model id. Defaults to OPENROUTER_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum completion tokens for the OpenRouter model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the model.",
    )
    parser.add_argument(
        "--print-message",
        action="store_true",
        help="Print the rendered operator message before the run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate env, skill loading, and prompt construction without calling the model.",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable Agno debug mode. Defaults to on.",
    )
    parser.add_argument(
        "--debug-level",
        type=int,
        choices=(1, 2),
        default=2,
        help="Agno debug verbosity. Defaults to 2.",
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


def ensure_openrouter_key() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        raise SystemExit(
            "Missing OPENROUTER_API_KEY.\n"
            "Set it in the environment or put it in .env / scripts/.env before running this script."
        )

def within_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def clamp_text(output: str, *, max_chars: int = 16000) -> str:
    output = output.strip()
    if len(output) <= max_chars:
        return output
    omitted = len(output) - max_chars
    return f"{output[:max_chars]}\n\n...[truncated {omitted} chars]"


def run_subprocess(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    extra_env: dict[str, str] | None = None,
) -> str:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return f"Command timed out after {timeout}s: {shlex.join(args)}\n{exc}"

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    parts = [
        f"cwd: {cwd}",
        f"command: {shlex.join(args)}",
        f"exit_code: {completed.returncode}",
    ]
    if stdout:
        parts.append("stdout:\n" + stdout)
    if stderr:
        parts.append("stderr:\n" + stderr)
    return clamp_text("\n\n".join(parts))


def build_tools():
    def list_repo_files(path: str = ".", max_entries: int = 200) -> str:
        """List files under a repo-relative directory so you can discover prompts, data, and code."""
        target = (REPO_ROOT / path).resolve()
        if not within_repo(target):
            return f"Path is outside the repo: {path}"
        if not target.exists():
            return f"Path does not exist: {target}"
        if target.is_file():
            return str(target.relative_to(REPO_ROOT))

        max_entries = max(1, min(max_entries, 500))
        output = run_subprocess(
            ["rg", "--files", str(target)],
            cwd=REPO_ROOT,
            timeout=30,
        )
        repo_prefix = f"{REPO_ROOT}/"
        return output.replace(repo_prefix, "") if repo_prefix in output else output

    def search_repo(pattern: str, file_glob: str = "") -> str:
        """Search repo text with ripgrep. Use this before reading large files when you need a specific symbol or prompt."""
        args = ["rg", "-n", "--hidden", pattern, str(REPO_ROOT)]
        if file_glob.strip():
            args.extend(["-g", file_glob.strip()])
        output = run_subprocess(args, cwd=REPO_ROOT, timeout=30)
        repo_prefix = f"{REPO_ROOT}/"
        return output.replace(repo_prefix, "") if repo_prefix in output else output

    def read_repo_file(path: str, start_line: int = 1, max_lines: int = 220) -> str:
        """Read a repo-relative text file with line numbers. Use this for prompts, journals, watchlists, and Python files."""
        target = (REPO_ROOT / path).resolve()
        if not within_repo(target):
            return f"Path is outside the repo: {path}"
        if not target.exists():
            return f"File does not exist: {target}"
        if not target.is_file():
            return f"Path is not a file: {target}"

        start_line = max(1, start_line)
        max_lines = max(1, min(max_lines, 400))
        lines = target.read_text(encoding="utf-8").splitlines()
        end_line = min(len(lines), start_line + max_lines - 1)
        numbered = [
            f"{line_no:>4}: {lines[line_no - 1]}"
            for line_no in range(start_line, end_line + 1)
        ]
        header = f"{target.relative_to(REPO_ROOT)}:{start_line}-{end_line}"
        return clamp_text(header + "\n" + "\n".join(numbered))

    def run_trader_market(symbols: str = "") -> str:
        """Run the read-only trader market command. Pass symbols like '2330 2454' or leave blank for the market overview."""
        args = ["uv", "run", "python", "-m", "tw_trader.cli", "market"]
        if symbols.strip():
            args.extend(symbols.split())
        return run_subprocess(args, cwd=TRADER_ROOT)

    def run_trader_account() -> str:
        """Run the read-only trader account command to inspect current holdings and orders."""
        return run_subprocess(
            ["uv", "run", "python", "-m", "tw_trader.cli", "account"],
            cwd=TRADER_ROOT,
        )

    def run_trader_watchlist() -> str:
        """Run the read-only trader watchlist command to inspect raw data, analysis, and evaluation."""
        return run_subprocess(
            ["uv", "run", "python", "-m", "tw_trader.cli", "watchlist"],
            cwd=TRADER_ROOT,
        )

    def run_trader_check_triggers() -> str:
        """Run the read-only watchlist trigger summary command."""
        return run_subprocess(
            ["uv", "run", "python", "-m", "tw_trader.cli", "check-triggers"],
            cwd=TRADER_ROOT,
        )

    def run_news_scan(tags: str = "tw,macro,sentiment") -> str:
        """Run the web-reader news scan used by the TW trader workflow."""
        return run_subprocess(
            ["uv", "run", "web-reader", "data/config/sources.tw.yaml", f"--tags={tags}"],
            cwd=TRADER_ROOT,
        )

    return [
        list_repo_files,
        search_repo,
        read_repo_file,
        run_trader_market,
        run_trader_account,
        run_trader_watchlist,
        run_trader_check_triggers,
        run_news_scan,
    ]


def build_agent(args: argparse.Namespace) -> Agent:
    return Agent(
        model=OpenRouter(
            id=args.model,
            max_completion_tokens=args.max_tokens,
            temperature=args.temperature,
        ),
        name="tw-trader-agno",
        session_id=args.session_id,
        description="Read-only Taiwan trader validation agent for this repository.",
        instructions=[
            "Always load the `tw-trader-agno` skill instructions before starting the workflow.",
            "Use the provided tools instead of inventing commands.",
            "Treat this run as read-only paper-trading validation.",
            "If a command fails, report the blocker and continue only where the evidence is sufficient.",
        ],
        expected_output=(
            "A concise report with execution summary, market and portfolio state, "
            "watchlist trigger summary, paper-trading candidate actions, and blockers."
        ),
        markdown=True,
        skills=Skills(loaders=[LocalSkills(str(DEFAULT_SKILL_PATH))]),
        tools=build_tools(),
        debug_mode=args.debug,
        debug_level=args.debug_level,
        telemetry=False,
    )


def main() -> int:
    args = parse_args()
    loaded_env_files = load_environment(args.env_file)
    ensure_openrouter_key()

    prompt_path = resolve_prompt_path(args.mode, args.prompt_file)
    workspace = args.workspace.expanduser().resolve()
    message = build_run_message(
        prompt_path,
        context_lines=(
            "Repo root: {repo_root}",
            f"Agent workspace: {workspace}",
            f"Skill workspace: {TRADER_ROOT}",
            "Primary trader prompt: {prompt_path}",
        ),
        execution_rules=(
            "Load the Agno skill instructions for `tw-trader-agno` before you start.",
            "Read `{prompt_path}` first and follow it as the primary instruction file.",
            "If that file references other prompt files, read and apply them too.",
            "Prefer the provided read-only tools for market, account, watchlist, trigger, news, and file access.",
            "Do not place or modify orders, watchlist items, journals, lessons, or prompt files in this PoC.",
            "If a workflow step would normally mutate state, explain what you would have done instead.",
            "If a tool fails, report the blocker instead of guessing.",
        ),
        extra_message=args.message,
    )

    if args.print_message or args.dry_run:
        print("=== Rendered Message ===")
        print(message)
        print("========================")

    if args.dry_run:
        agent = build_agent(args)
        print(f"Loaded env files: {', '.join(str(path) for path in loaded_env_files) or '(none)'}")
        print(f"OpenRouter model: {args.model}")
        print(f"Agno skill path: {DEFAULT_SKILL_PATH}")
        print(f"Prompt path: {prompt_path}")
        print(f"Agent ready: {agent.name}")
        return 0

    agent = build_agent(args)
    try:
        agent.print_response(
            message,
            stream=True,
            debug_mode=args.debug,
            show_full_reasoning=False,
        )
    except KeyboardInterrupt:
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
