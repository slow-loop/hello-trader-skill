"""Validate generated strategy files before registration."""

from __future__ import annotations

import ast
import py_compile
import subprocess
import sys
from pathlib import Path

from skill_crypto_trader.journal.helpers import get_strategy_dir


def validate_syntax(strategy_path: Path) -> list[str]:
    """Check Python syntax and verify IStrategy subclass exists."""
    errors = []

    # 1. Compile check
    try:
        py_compile.compile(str(strategy_path), doraise=True)
    except py_compile.PyCompileError as e:
        errors.append(f"Syntax error: {e}")
        return errors

    # 2. AST check for IStrategy subclass
    source = strategy_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        errors.append(f"Parse error: {e}")
        return errors

    has_istrategy = False
    has_stoploss = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name == "IStrategy":
                    has_istrategy = True
            # Check class body for stoploss
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "stoploss":
                            has_stoploss = True

    if not has_istrategy:
        errors.append("No class inheriting from IStrategy found")
    if not has_stoploss:
        errors.append("No stoploss attribute found (mandatory)")

    return errors


def validate_by_name(name: str) -> list[str]:
    """Validate a strategy by name (looks up in strategies dir)."""
    class_name = "".join(part.capitalize() for part in name.split("_"))
    path = get_strategy_dir() / f"{class_name}.py"
    if not path.exists():
        return [f"Strategy file not found: {path}"]
    return validate_syntax(path)
