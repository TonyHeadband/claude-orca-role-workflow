import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from role_workflow.__main__ import PLUGIN_ROOT, main
from role_workflow.doctor import format_report, run_checks

ORCA_ENV = {"ORCA_CLI_COMMAND": "orca"}
DENY = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}})
GUIDANCE = json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "x"}})


def good_hook(subcommand, stdin):
    payload = json.loads(stdin) if stdin else {}
    if subcommand == "session-guidance":
        return 0, GUIDANCE
    if subcommand == "orca-guard":
        return 0, "" if "--model" in payload["tool_input"]["command"] else DENY
    tool_input = payload["tool_input"]
    return 0, DENY if "model" not in tool_input and tool_input["subagent_type"] == "general-purpose" else ""


class DoctorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.config = self.dir / "config"
        self.config.mkdir()

    def checks(self, hook=good_hook, env=ORCA_ENV):
        return run_checks(PLUGIN_ROOT, self.dir, self.config, env, hook)

    def test_all_green(self):
        checks = self.checks()
        self.assertEqual([c.status for c in checks[:4]], ["OK"] * 4)
        self.assertNotIn("FAIL", [c.status for c in checks])

    def test_orca_na(self):
        self.assertEqual(self.checks(env={})[0].status, "N/A")

    def test_shadow_agent(self):
        (self.config / "agents").mkdir()
        (self.config / "agents" / "reviewer.md").write_text("---\nname: reviewer\n---\n")
        agents = self.checks()[2]
        self.assertEqual(agents.status, "FAIL")
        self.assertIn("delete", agents.fix)

    def test_hook_not_refusing(self):
        checks = self.checks(hook=lambda s, i: (0, ""))
        self.assertEqual(checks[1].status, "FAIL")

    def test_no_python(self):
        checks = self.checks(hook=lambda s, i: (1, ""))
        for index in (0, 1, 3):
            self.assertEqual(checks[index].status, "FAIL")
            self.assertIn("Python 3.10+ not found", checks[index].detail)

    def test_subagent_env_info(self):
        checks = self.checks(env={**ORCA_ENV, "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"})
        info = [c for c in checks if c.status == "INFO"]
        self.assertEqual(len(info), 1)
        self.assertIn("CLAUDE_CODE_SUBAGENT_MODEL=sonnet", info[0].detail)

    def test_report_exit_code(self):
        report = format_report(self.checks())
        self.assertTrue(all(line.startswith(("[OK]", "[N/A]", "[INFO]", "[FAIL]", "  fix:")) for line in report.splitlines()))
        (self.config / "agents").mkdir()
        (self.config / "agents" / "reviewer.md").write_text("---\nname: reviewer\n---\n")
        out = io.StringIO()
        rc = main(["doctor", "--cwd", str(self.dir)], io.StringIO(""), out, {"CLAUDE_CONFIG_DIR": str(self.config)})
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL] Agents", out.getvalue())

    @unittest.skipUnless(os.name == "posix", "needs bash")
    def test_real_launcher(self):
        checks = run_checks(PLUGIN_ROOT, self.dir, self.config, {**os.environ, **ORCA_ENV})
        self.assertEqual([checks[i].status for i in (0, 1, 3)], ["OK"] * 3)
