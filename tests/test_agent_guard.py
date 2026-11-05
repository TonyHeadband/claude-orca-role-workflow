import tempfile
import unittest
from pathlib import Path

from role_workflow.agent_guard import check_agent_call
from role_workflow.messages import agent_refusal

REPO = Path(__file__).resolve().parent.parent


class CheckAgentCallTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = Path(tmp.name) / "config"
        (self.config / "agents").mkdir(parents=True)
        (self.config / "agents" / "x.md").write_text("---\nname: x\nmodel: inherit\n---\nbody\n")
        self.cwd = Path(tmp.name) / "cwd"
        self.cwd.mkdir()

    def check(self, tool_input):
        return check_agent_call(tool_input, self.cwd, self.config, REPO)

    def test_refused(self):
        cases = [
            {},
            {"subagent_type": "general-purpose"},
            {"subagent_type": "Explore"},
            {"subagent_type": "general-purpose", "model": "inherit"},
            {"subagent_type": "general-purpose", "model": "INHERIT"},
            {"subagent_type": "x"},
            {"subagent_type": "role-workflow:reviewer", "model": "inherit"},
            {"subagent_type": "role-workflow:reviewer", "model": "INHERIT"},
            {"subagent_type": "general-purpose", "model": ""},
            {"subagent_type": "general-purpose", "model": 5},
            {"subagent_type": ["a"], "model": None},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNotNone(self.check(case))

    def test_allowed(self):
        cases = [
            {"subagent_type": "fork"},
            {"subagent_type": "general-purpose", "model": "haiku"},
            {"subagent_type": "role-workflow:reviewer"},
            {"subagent_type": "role-workflow:reviewer", "model": "sonnet"},
            {"subagent_type": "Explore", "model": "opus"},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(self.check(case))

    def test_refusal_text(self):
        text = self.check({}).reason
        for needle in ("role-workflow:implementer", "role-workflow:reviewer", "model"):
            self.assertIn(needle, text)
        self.assertEqual(text, agent_refusal(None))


if __name__ == "__main__":
    unittest.main()
