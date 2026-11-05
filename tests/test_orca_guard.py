import unittest

from role_workflow.orca_guard import check_orca_command


def refused(cmd, shell="bash", env=None):
    return check_orca_command(cmd, shell, env or {}) is not None


class CheckOrcaCommandTest(unittest.TestCase):
    def test_refused(self):
        cases = [
            ("orca orchestration worker-start --spec 'x' --agent claude",),
            ('"$ORCA_CLI_COMMAND" orchestration worker-start --task t1 --agent claude',),
            ("${ORCA_CLI_COMMAND} agent launch --agent claude --prompt hi",),
            ("orca-ide worktree create --name a --agent claude",),
            ("orca-dev agent launch --agent=claude",),
            ("cd repo && orca agent launch --agent claude",),
            ("FOO=1 orca agent launch --agent claude",),
            ("orca agent launch --agent claude --model=",),
            ('"C:\\Users\\x\\orca\\orca.exe" agent launch --agent claude',),
            ("& $env:ORCA_CLI_COMMAND orchestration worker-start --agent claude", "powershell"),
            ("C:\\Users\\x\\AppData\\Local\\orca\\orca.exe agent launch --agent claude", "powershell"),
            ("/opt/orca/bin/orca-cli agent launch --agent claude", "bash",
             {"ORCA_CLI_COMMAND": "/opt/orca/bin/orca-cli"}),
            ("echo ok\norca agent launch --agent claude",),
            ('orca orchestration worker-start --agent claude --spec "line1\nline2"',),
            ("orca \\\n  agent launch --agent claude",),
            ("orca orchestration \\\n  worker-start --agent claude",),
            ('orca orchestration worker-start --agent claude --spec "Fix the cout << x bug\nin src/main.cpp"',),
            ('orca orchestration worker-start --agent claude --spec "Resolve the <<<<<<< HEAD markers\nin a.py"',),
            ('orca orchestration worker-start --agent claude --spec "Use a <<EOF heredoc\nfor input"',),
            ('jq . <<< "$x"\norca agent launch --agent claude',),
            ("cat <<EOF \\\n  && orca agent launch --agent claude\nbody\nEOF",),
            ("& $Env:ORCA_CLI_COMMAND agent launch --agent claude", "powershell"),
            ("& $ENV:ORCA_CLI_COMMAND agent launch --agent claude", "powershell"),
            ('& "${env:ORCA_CLI_COMMAND}" agent launch --agent claude', "powershell"),
            ("& $env:ORCA_CLI_COMMAND orchestration worker-start --agent claude `\n  --spec x", "powershell"),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(refused(*case))

    def test_allowed(self):
        cases = [
            "orca orchestration worker-start --agent claude --model sonnet",
            "orca agent launch --agent claude --model=opus --effort high",
            "orca worktree create --name a",
            "orca orchestration worker-start --terminal term-1 --spec x",
            "orca agent launch --agent codex",
            "orca worktree create --agent shell",
            'git commit -m "orca agent launch --agent claude"',
            'grep -rn "worker-start" src',
            'echo "orca agent launch --agent claude"',
            "cat <<'EOF' > notes.md\norca agent launch --agent claude\nEOF",
            "cat <<-EOF\n\torca agent launch --agent claude\n\tEOF",
            "orca orchestration status",
            'git commit -m "$(cat <<\'EOF\'\nmsg\norca agent launch --agent claude\nEOF\n)"',
            "orca agent launch --agent claude 'unterminated",
        ]
        for cmd in cases:
            with self.subTest(cmd=cmd):
                self.assertFalse(refused(cmd))

    def test_powershell_backtick_continuation_allowed(self):
        cmd = "& $env:ORCA_CLI_COMMAND orchestration worker-start --agent claude `\n  --model sonnet --spec x"
        self.assertFalse(refused(cmd, "powershell"))

    def test_refusal_text(self):
        result = check_orca_command("orca agent launch --agent claude", "bash", {})
        for text in ("agent launch", "--model sonnet", "--model opus"):
            self.assertIn(text, result.reason)


if __name__ == "__main__":
    unittest.main()
