"""Resolve which model a subagent type runs on from agent definition frontmatter."""
from __future__ import annotations

import json
from pathlib import Path

SELF_PLUGIN = "role-workflow"


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        key, sep, value = line.partition(":")
        if not sep or not key.strip() or key[0].isspace():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key.strip()] = value
    return result


def _model_in_dir(directory: Path, name: str) -> tuple[bool, str | None]:
    """Returns (found, model) for the first agent file in directory matching name."""
    try:
        files = sorted(directory.rglob("*.md"))
    except OSError:
        return False, None
    for path in files:
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if fm.get("name", path.stem) == name:
            return True, fm.get("model") or None
    return False, None


def _plugin_agent_dirs(plugin: str, config_dir: Path, plugin_root: Path) -> list[Path]:
    if plugin == SELF_PLUGIN:
        return [plugin_root / "agents"]
    try:
        data = json.loads((config_dir / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
        dirs = []
        for key, entries in data["plugins"].items():
            if key.startswith(plugin + "@"):
                dirs += [Path(e["installPath"]) / "agents" for e in entries]
        return dirs
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def find_agent_model(subagent_type: str, cwd: Path, config_dir: Path, plugin_root: Path) -> str | None:
    if ":" in subagent_type:
        plugin, name = subagent_type.split(":", 1)
        dirs = _plugin_agent_dirs(plugin, config_dir, plugin_root)
    else:
        name = subagent_type
        dirs = [cwd / ".claude" / "agents", config_dir / "agents"]
    for directory in dirs:
        found, model = _model_in_dir(directory, name)
        if found:
            return model
    return None
