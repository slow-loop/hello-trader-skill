from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_FILE = Path("skills/tw-trader/prompts/TRADING.TW.md")
PROMPT_PRESETS = {
    "trading": Path("skills/tw-trader/prompts/TRADING.TW.md"),
    "research": Path("skills/tw-trader/prompts/RESEARCH.TW.md"),
    "social": Path("skills/tw-trader/prompts/SOCIAL.md"),
}
DEFAULT_OUTPUT_SECTIONS = (
    "Execution summary",
    "Market / portfolio state used",
    "Watchlist trigger and invalidation summary",
    "Candidate actions for paper trading only",
    "Blockers, tool failures, or prompt mismatches",
)


def resolve_prompt_path(mode: str | None, prompt_file: Path) -> Path:
    selected_prompt = PROMPT_PRESETS[mode] if mode else prompt_file
    prompt_path = (REPO_ROOT / selected_prompt).resolve()
    if not prompt_path.exists():
        raise SystemExit(f"Prompt file not found: {prompt_path}")
    return prompt_path


def build_run_message(
    prompt_path: Path,
    *,
    context_lines: Sequence[str],
    execution_rules: Sequence[str],
    extra_message: str,
    output_sections: Sequence[str] = DEFAULT_OUTPUT_SECTIONS,
) -> str:
    relative_prompt_path = prompt_path.relative_to(REPO_ROOT)
    values = {
        "prompt_path": relative_prompt_path,
        "repo_root": REPO_ROOT,
    }

    rendered_context = [line.format(**values) for line in context_lines]
    rendered_rules = [
        f"{index}. {rule.format(**values)}"
        for index, rule in enumerate(execution_rules, start=1)
    ]
    rendered_sections = [f"- {section}" for section in output_sections]

    message = [
        "You are running a PoC for the TW trader skill inside this repository.",
        "",
        *rendered_context,
        "",
        "Required execution rules:",
        *rendered_rules,
        "",
        "Output format:",
        *rendered_sections,
    ]
    if extra_message.strip():
        message.extend(
            [
                "",
                "Additional operator instruction:",
                extra_message.strip(),
            ]
        )

    return textwrap.dedent("\n".join(message)).strip()
