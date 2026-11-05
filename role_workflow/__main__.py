import json
import os
import sys
from pathlib import Path
from typing import Mapping, TextIO

from role_workflow.agent_guard import check_agent_call
from role_workflow.decision import Refusal
from role_workflow.messages import GUIDANCE
from role_workflow.orca_guard import check_orca_command

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

SHELLS = {"Bash": "bash", "PowerShell": "powershell"}


def config_dir(environ: Mapping[str, str]) -> Path:
    configured = environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured) if configured else Path.home() / ".claude"


def _orca_guard(payload: dict, environ: Mapping[str, str]) -> Refusal | None:
    shell = SHELLS.get(payload["tool_name"])
    if shell is None:
        return None
    return check_orca_command(payload["tool_input"]["command"], shell, environ)


def _agent_guard(payload: dict, environ: Mapping[str, str]) -> Refusal | None:
    return check_agent_call(payload["tool_input"], Path(payload["cwd"]), config_dir(environ), PLUGIN_ROOT)


GUARDS = {"orca-guard": _orca_guard, "agent-guard": _agent_guard}


def _emit(stdout: TextIO, output: dict) -> None:
    stdout.write(json.dumps(output))


def main(argv: list[str], stdin: TextIO, stdout: TextIO, environ: Mapping[str, str]) -> int:
    command = argv[0] if argv else ""
    if command == "session-guidance":
        _emit(stdout, {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": GUIDANCE}})
        return 0
    if command == "doctor":
        print("not implemented", file=stdout)
        return 2
    guard = GUARDS.get(command)
    if guard is None:
        return 0
    # Fail open: a broken hook must never block the user's tool call.
    try:
        refusal = guard(json.loads(stdin.read()), environ)
        if refusal is not None:
            _emit(stdout, {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": refusal.reason,
            }})
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin, sys.stdout, os.environ))
