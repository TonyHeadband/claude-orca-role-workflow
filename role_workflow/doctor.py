"""Health report for /hierarchy-doctor. Read-only: changes nothing and writes no files."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Mapping

from role_workflow.agent_defs import find_agent_model

RunHook = Callable[[str, str], tuple[int, str]]

NO_PYTHON = "Python 3.10+ not found"
NO_PYTHON_FIX = "install Python 3.10+ and put it on PATH (see the README requirements)"
LAUNCH = "orca agent launch --agent claude"


@dataclass(frozen=True)
class Check:
    status: Literal["OK", "FAIL", "N/A", "INFO"]
    name: str
    detail: str
    fix: str = ""


def _default_run_hook(plugin_root: Path, environ: Mapping[str, str]) -> RunHook:
    def run(subcommand: str, stdin_json: str) -> tuple[int, str]:
        try:
            done = subprocess.run(
                ["bash", str(plugin_root / "hooks" / "run-python"), subcommand],
                input=stdin_json, capture_output=True, text=True, env={**os.environ, **environ}, timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return 1, str(error)
        return done.returncode, done.stdout

    return run


def _has_matcher(plugin_root: Path, matcher: str) -> bool:
    try:
        data = json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        return any(entry.get("matcher") == matcher for entry in data["hooks"]["PreToolUse"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _denies(output: str) -> bool:
    try:
        return json.loads(output)["hookSpecificOutput"]["permissionDecision"] == "deny"
    except (ValueError, KeyError, TypeError):
        return False


def _bash(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _agent(cwd: Path, **tool_input: str) -> str:
    return json.dumps({"tool_name": "Agent", "tool_input": tool_input, "cwd": str(cwd)})


def _no_python(name: str) -> Check:
    return Check("FAIL", name, NO_PYTHON, NO_PYTHON_FIX)


def _orca_check(plugin_root: Path, environ: Mapping[str, str], run_hook: RunHook) -> Check:
    name = "Orca hook"
    if not environ.get("ORCA_CLI_COMMAND"):
        return Check("N/A", name, "Orca not detected (ORCA_CLI_COMMAND unset); guard idle")
    if not _has_matcher(plugin_root, "Bash|PowerShell"):
        return Check("FAIL", name, "hooks.json lacks the Bash|PowerShell matcher", "reinstall the role-workflow plugin")
    bare_rc, bare = run_hook("orca-guard", _bash(LAUNCH))
    if bare_rc == 1:
        return _no_python(name)
    _, modeled = run_hook("orca-guard", _bash(f"{LAUNCH} --model sonnet"))
    if _denies(bare) and not modeled.strip():
        return Check("OK", name, "launch without a model is refused; with --model it is allowed")
    return Check("FAIL", name, "the guard did not refuse a launch without a model, or refused one with a model",
                 "run `bash hooks/run-python orca-guard` by hand and check its output")


def _agent_hook_check(plugin_root: Path, cwd: Path, run_hook: RunHook) -> Check:
    name = "Agent hook"
    if not _has_matcher(plugin_root, "Agent|Task"):
        return Check("FAIL", name, "hooks.json lacks the Agent|Task matcher", "reinstall the role-workflow plugin")
    bare_rc, bare = run_hook("agent-guard", _agent(cwd, subagent_type="general-purpose"))
    if bare_rc == 1:
        return _no_python(name)
    _, role = run_hook("agent-guard", _agent(cwd, subagent_type="role-workflow:reviewer"))
    if _denies(bare) and not role.strip():
        return Check("OK", name, "a call without a model is refused; a role agent is allowed")
    return Check("FAIL", name, "the guard did not refuse general-purpose without a model, or refused the reviewer",
                 "run `bash hooks/run-python agent-guard` by hand and check its output")


def _agents_check(cwd: Path, config_dir: Path, plugin_root: Path) -> Check:
    name = "Agents"
    problems, fixes = [], []
    for role, expected in (("implementer", "sonnet"), ("reviewer", "opus")):
        actual = find_agent_model(f"role-workflow:{role}", cwd, config_dir, plugin_root)
        if actual != expected:
            problems.append(f"role-workflow:{role} resolves to {actual or 'no model'}, expected {expected}")
            fixes.append("reinstall the role-workflow plugin")
        shadow = config_dir / "agents" / f"{role}.md"
        if shadow.exists():
            problems.append(f"{shadow} exists")
            fixes.append("delete it; the plugin's copy replaces it")
    if problems:
        return Check("FAIL", name, "; ".join(problems), "; ".join(dict.fromkeys(fixes)))
    return Check("OK", name, "implementer runs on sonnet, reviewer on opus")


def _guidance_check(run_hook: RunHook) -> Check:
    name = "Guidance"
    rc, output = run_hook("session-guidance", "")
    if rc == 1:
        return _no_python(name)
    try:
        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    except (ValueError, KeyError, TypeError):
        context = ""
    if isinstance(context, str) and context.strip():
        return Check("OK", name, "session guidance is produced")
    return Check("FAIL", name, "session-guidance output is missing or has no additionalContext",
                 "run `bash hooks/run-python session-guidance` by hand and check its output")


def run_checks(
    plugin_root: Path,
    cwd: Path,
    config_dir: Path,
    environ: Mapping[str, str],
    run_hook: RunHook | None = None,
) -> list[Check]:
    run_hook = run_hook or _default_run_hook(plugin_root, environ)
    checks = [
        _orca_check(plugin_root, environ, run_hook),
        _agent_hook_check(plugin_root, cwd, run_hook),
        _agents_check(cwd, config_dir, plugin_root),
        _guidance_check(run_hook),
    ]
    override = environ.get("CLAUDE_CODE_SUBAGENT_MODEL")
    if override:
        checks.append(Check("INFO", "Subagent model override",
                            f"CLAUDE_CODE_SUBAGENT_MODEL={override} is set; role-workflow still requires an explicit model per call."))
    return checks


def format_report(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        lines.append(f"[{check.status}] {check.name}: {check.detail}")
        if check.status == "FAIL" and check.fix:
            lines.append(f"  fix: {check.fix}")
    return "\n".join(lines)
