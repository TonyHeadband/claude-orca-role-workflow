import json
import tempfile
import unittest
from pathlib import Path

from role_workflow.agent_defs import find_agent_model, parse_frontmatter

REPO = Path(__file__).resolve().parent.parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class FrontmatterTests(unittest.TestCase):
    def test_frontmatter_basic(self):
        self.assertEqual(
            parse_frontmatter("---\nname: a\nmodel: sonnet\n---\nbody"),
            {"name": "a", "model": "sonnet"},
        )

    def test_frontmatter_crlf_quoted(self):
        fm = parse_frontmatter('---\r\nname: a\r\nmodel: "opus"\r\n---\r\n')
        self.assertEqual(fm["model"], "opus")

    def test_frontmatter_missing(self):
        self.assertEqual(parse_frontmatter("# just text"), {})


class FindAgentModelTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cwd = self.root / "proj"
        self.config = self.root / "cfg"
        self.cwd.mkdir()
        self.config.mkdir()

    def find(self, name, plugin_root=None):
        return find_agent_model(name, self.cwd, self.config, plugin_root or self.root / "none")

    def test_name_differs_from_stem(self):
        write(self.cwd / ".claude/agents/x.md", "---\nname: builder\nmodel: haiku\n---\n")
        self.assertEqual(self.find("builder"), "haiku")

    def test_stem_fallback(self):
        write(self.config / "agents/solo.md", "---\nmodel: opus\n---\n")
        self.assertEqual(self.find("solo"), "opus")

    def test_project_beats_user(self):
        write(self.cwd / ".claude/agents/a.md", "---\nname: a\nmodel: sonnet\n---\n")
        write(self.config / "agents/a.md", "---\nname: a\nmodel: opus\n---\n")
        self.assertEqual(self.find("a"), "sonnet")

    def test_no_model(self):
        write(self.config / "agents/a.md", "---\nname: a\n---\n")
        self.assertIsNone(self.find("a"))

    def test_not_found(self):
        self.assertIsNone(self.find("ghost"))

    def test_plugin_namespace_self(self):
        self.assertEqual(self.find("role-workflow:implementer", REPO), "sonnet")

    def test_plugin_namespace_self_reviewer(self):
        self.assertEqual(self.find("role-workflow:reviewer", REPO), "opus")

    def test_other_plugin_via_registry(self):
        install = self.root / "inst"
        write(install / "agents/r.md", "---\nmodel: opus\n---\n")
        write(
            self.config / "plugins/installed_plugins.json",
            json.dumps({"plugins": {"other@mkt": [{"installPath": str(install)}]}}),
        )
        self.assertEqual(self.find("other:r"), "opus")

    def test_bad_registry_json(self):
        write(self.config / "plugins/installed_plugins.json", "{")
        self.assertIsNone(self.find("other:r"))


if __name__ == "__main__":
    unittest.main()
