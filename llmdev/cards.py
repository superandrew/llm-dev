import json
import tomllib
from dataclasses import dataclass


class CardError(Exception): ...


@dataclass(frozen=True)
class Card:
    path: str
    id: str
    title: str
    edit: tuple
    read: tuple
    checks: tuple
    commit: str
    edit_format: str = ""


def parse(path: str) -> Card:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        raise CardError(f"{path}: cannot read card: {e}")

    lines = content.splitlines()

    if not lines or lines[0] != "+++":
        raise CardError(f"{path}: missing opening +++")

    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line == "+++":
            end_idx = i
            break

    if end_idx is None:
        raise CardError(f"{path}: missing closing +++")

    front_matter_lines = lines[1:end_idx]
    if not front_matter_lines:
        raise CardError(f"{path}: empty front matter")

    front_matter_str = "\n".join(front_matter_lines)

    try:
        data = tomllib.loads(front_matter_str)
    except tomllib.TOMLDecodeError as e:
        raise CardError(f"{path}: invalid TOML: {e}")

    required_keys = {"id", "title", "edit", "checks", "commit"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise CardError(f"{path}: missing required key(s): {', '.join(sorted(missing_keys))}")

    edit = data["edit"]
    if not isinstance(edit, list):
        raise CardError(f"{path}: edit must be a list")
    edit = tuple(edit)

    read = data.get("read", [])
    if not isinstance(read, list):
        raise CardError(f"{path}: read must be a list")
    read = tuple(read)

    checks = data["checks"]
    if not isinstance(checks, list):
        raise CardError(f"{path}: checks must be a list")
    checks = tuple(checks)

    edit_format = data.get("edit_format", "")
    if not isinstance(edit_format, str):
        raise CardError(f"{path}: edit_format must be a string")

    return Card(
        path=path,
        id=data["id"],
        title=data["title"],
        edit=edit,
        read=read,
        checks=checks,
        commit=data["commit"],
        edit_format=edit_format,
    )
