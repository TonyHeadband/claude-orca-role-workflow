import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from role_workflow.__main__ import main

REPO = Path(__file__).resolve().parent.parent
LAUNCH = "orca agent launch --agent claude"


def run(argv, payload, environ=None):
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    out = io.StringIO()
    rc = main(argv, io.StringIO(stdin), out, environ or {})
    return rc, out.getvalue()


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class CliTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def assertDeny(self, out, contains):
        data = json.loads(out)
        self.assertEqual(list(data), ["hookSpecificOutput"])
        spec = data["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "deny")
        self.assertIn(contains, spec["permissionDecisionReason"])

    def test_orca_guard_denies(self):
        rc, out = run(["orca-guard"], bash(LAUNCH))
        self.assertEqual(rc, 0)
        self.assertDeny(out, "--model sonnet")

    def test_orca_guard_powershell(self):
        payload = {
            "tool_name": "PowerShell",
            "tool_input": {"command": "& $env:ORCA_CLI_COMMAND agent launch --agent claude"},
        }
        rc, out = run(["orca-guard"], payload)
        self.assertEqual(rc, 0)
        self.assertDeny(out, "--model sonnet")

    def test_orca_guard_allows(self):
        self.assertEqual(run(["orca-guard"], bash("ls -la")), (0, ""))

    def test_other_tool_ignored(self):
        payload = {"tool_name": "Read", "tool_input": {"command": LAUNCH}}
        self.assertEqual(run(["orca-guard"], payload), (0, ""))

    def test_agent_guard_denies(self):
        payload = {"tool_name": "Agent", "cwd": self.tmp, "tool_input": {"subagent_type": "general-purpose"}}
        rc, out = run(["agent-guard"], payload, {"CLAUDE_CONFIG_DIR": self.tmp})
        self.assertEqual(rc, 0)
        self.assertDeny(out, "model")

    def test_agent_guard_allows_reviewer(self):
        payload = {"tool_name": "Agent", "cwd": self.tmp, "tool_input": {"subagent_type": "role-workflow:reviewer"}}
        self.assertEqual(run(["agent-guard"], payload, {"CLAUDE_CONFIG_DIR": self.tmp}), (0, ""))

    def test_malformed_inputs(self):
        for stdin in ["", "not json", "{}", '{"tool_name":"Bash","tool_input":{"command":5}}']:
            for sub in ["orca-guard", "agent-guard"]:
                with self.subTest(stdin=stdin, sub=sub):
                    self.assertEqual(run([sub], stdin), (0, ""))

    def test_agent_guard_non_mapping_tool_input(self):
        for tool_input in [None, []]:
            payload = {"tool_name": "Agent", "cwd": self.tmp, "tool_input": tool_input}
            with self.subTest(tool_input=tool_input):
                self.assertEqual(run(["agent-guard"], payload, {"CLAUDE_CONFIG_DIR": self.tmp}), (0, ""))

    def test_unknown_subcommand(self):
        self.assertEqual(run(["bogus"], "")[1], "")

    def test_session_guidance(self):
        rc, out = run(["session-guidance"], "")
        self.assertEqual(rc, 0)
        spec = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "SessionStart")
        for text in ["role-workflow:implementer", "role-workflow:reviewer", "--model sonnet", "--model opus"]:
            self.assertIn(text, spec["additionalContext"])

    def test_entry_decodes_stdin_as_utf8(self):
        command = 'orca orchestration worker-start --agent claude --spec "\u274c bad"'
        proc = subprocess.run(
            [sys.executable, "-m", "role_workflow", "orca-guard"],
            input=json.dumps(bash(command), ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            cwd=REPO,
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertDeny(proc.stdout.decode("utf-8"), "--model sonnet")

    @unittest.skipUnless(os.name == "posix", "launcher is a POSIX script")
    def test_launcher_ignores_pythonsafepath(self):
        proc = subprocess.run(
            ["bash", str(REPO / "hooks" / "run-python"), "orca-guard"],
            input=json.dumps(bash(LAUNCH)),
            capture_output=True,
            text=True,
            cwd=self.tmp,
            env={**os.environ, "PYTHONSAFEPATH": "1"},
        )
        self.assertDeny(proc.stdout, "--model sonnet")

    @unittest.skipUnless(os.name == "posix", "launcher is a POSIX script")
    def test_launcher_writes_no_bytecode(self):
        copy = Path(self.tmp) / "plugin"
        shutil.copytree(REPO / "role_workflow", copy / "role_workflow",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "hooks", copy / "hooks")
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        subprocess.run(
            ["bash", str(copy / "hooks" / "run-python"), "orca-guard"],
            input=json.dumps(bash(LAUNCH)), capture_output=True, text=True, env=env,
        )
        self.assertEqual(list(copy.rglob("__pycache__")), [])

    @unittest.skipUnless(os.name == "posix", "launcher is a POSIX script")
    def test_launcher_end_to_end(self):
        proc = subprocess.run(
            ["bash", str(REPO / "hooks" / "run-python"), "orca-guard"],
            input=json.dumps(bash(LAUNCH)),
            capture_output=True,
            text=True,
            cwd=self.tmp,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertDeny(proc.stdout, "--model sonnet")

    @unittest.skipUnless(os.name == "posix", "launcher is a POSIX script")
    def test_launcher_no_python(self):
        stub_dir = Path(self.tmp) / "bin"
        stub_dir.mkdir()
        stub = stub_dir / "python3"
        stub.write_text("#!/bin/sh\nexit 9\n")
        stub.chmod(0o755)
        proc = subprocess.run(
            [shutil.which("bash"), str(REPO / "hooks" / "run-python"), "orca-guard"],
            input="{}",
            capture_output=True,
            text=True,
            env={"PATH": str(stub_dir)},
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Python 3.10+ not found", proc.stderr)

    def test_manifests_parse(self):
        load = lambda p: json.loads((REPO / p).read_text())
        plugin = load(".claude-plugin/plugin.json")
        self.assertEqual((plugin["name"], plugin["version"]), ("role-workflow", "0.1.0"))
        market = load(".claude-plugin/marketplace.json")
        self.assertEqual(market["plugins"][0]["source"], "./")
        hooks = load("hooks/hooks.json")["hooks"]
        self.assertEqual([h["matcher"] for h in hooks["PreToolUse"]], ["Bash|PowerShell", "Agent|Task"])
        self.assertIn("SessionStart", hooks)


if __name__ == "__main__":
    unittest.main()
