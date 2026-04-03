from __future__ import annotations

import json
from typing import Any


def dump_yaml(data: Any) -> str:
    lines = _dump_node(data, indent=0)
    return "\n".join(lines).rstrip() + "\n"


def _dump_node(value: Any, indent: int) -> list[str]:
    if isinstance(value, dict):
        return _dump_dict(value, indent)
    if isinstance(value, list):
        return _dump_list(value, indent)
    raise TypeError(f"Unsupported top-level YAML node: {type(value)!r}")


def _dump_dict(data: dict[str, Any], indent: int) -> list[str]:
    pad = " " * indent
    if not data:
        return [f"{pad}{{}}"]

    lines: list[str] = []
    for key, value in data.items():
        key_text = str(key)
        if isinstance(value, str) and "\n" in value:
            lines.append(f"{pad}{key_text}: |-")
            for line in value.splitlines():
                lines.append(f"{pad}  {line}")
            continue

        if _is_scalar(value):
            lines.append(f"{pad}{key_text}: {_format_scalar(value)}")
            continue

        if isinstance(value, list) and not value:
            lines.append(f"{pad}{key_text}: []")
            continue

        if isinstance(value, dict) and not value:
            lines.append(f"{pad}{key_text}: {{}}")
            continue

        lines.append(f"{pad}{key_text}:")
        lines.extend(_dump_node(value, indent + 2))
    return lines


def _dump_list(items: list[Any], indent: int) -> list[str]:
    pad = " " * indent
    if not items:
        return [f"{pad}[]"]

    lines: list[str] = []
    for item in items:
        if isinstance(item, str) and "\n" in item:
            lines.append(f"{pad}- |-")
            for line in item.splitlines():
                lines.append(f"{pad}  {line}")
            continue

        if _is_scalar(item):
            lines.append(f"{pad}- {_format_scalar(item)}")
            continue

        if isinstance(item, dict) and item:
            first = True
            for key, value in item.items():
                key_text = str(key)
                if first:
                    if isinstance(value, str) and "\n" in value:
                        lines.append(f"{pad}- {key_text}: |-")
                        for line in value.splitlines():
                            lines.append(f"{pad}    {line}")
                    elif _is_scalar(value):
                        lines.append(f"{pad}- {key_text}: {_format_scalar(value)}")
                    else:
                        lines.append(f"{pad}- {key_text}:")
                        lines.extend(_dump_node(value, indent + 4))
                    first = False
                    continue

                if isinstance(value, str) and "\n" in value:
                    lines.append(f"{pad}  {key_text}: |-")
                    for line in value.splitlines():
                        lines.append(f"{pad}    {line}")
                elif _is_scalar(value):
                    lines.append(f"{pad}  {key_text}: {_format_scalar(value)}")
                elif isinstance(value, list) and not value:
                    lines.append(f"{pad}  {key_text}: []")
                elif isinstance(value, dict) and not value:
                    lines.append(f"{pad}  {key_text}: {{}}")
                else:
                    lines.append(f"{pad}  {key_text}:")
                    lines.extend(_dump_node(value, indent + 4))
            continue

        lines.append(f"{pad}-")
        lines.extend(_dump_node(item, indent + 2))
    return lines


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return json.dumps(value, ensure_ascii=False)
    if value == "":
        return '""'
    if "\n" in value:
        return json.dumps(value, ensure_ascii=False)
    if _needs_quotes(value):
        return json.dumps(value, ensure_ascii=False)
    return value


def _needs_quotes(value: str) -> bool:
    lowered = value.lower()
    reserved = {"true", "false", "null", "yes", "no", "~"}
    if lowered in reserved:
        return True
    if value[0].isspace() or value[-1].isspace():
        return True
    special = [": ", "#", "[", "]", "{", "}", ",", "&", "*", "!", "|", ">", "%", "@", "`", '"', "'"]
    return any(token in value for token in special)
