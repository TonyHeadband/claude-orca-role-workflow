# role-workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code plugin, `role-workflow`, that refuses Orca worker launches and in-session subagent calls that don't state a model, ships the `implementer` (Sonnet) and `reviewer` (Opus) role agents, injects role guidance at session start, and reports its own health with `/hierarchy-doctor`.

**Architecture:** One Python package (`role_workflow/`) holds pure decision functions: an Orca command parser, an agent-definition resolver, an Agent-call guard, and the doctor. A single CLI entry point (`python -m role_workflow <subcommand>`) adapts them to Claude Code's hook stdin/stdout JSON. Hooks reach Python through a polyglot `run-hook.cmd` (Windows → Git Bash) and a bash launcher that finds a Python 3.10+ interpreter. The repo is its own marketplace.

**Tech Stack:** Python 3.10+ standard library only (`shlex`, `json`, `dataclasses`, `pathlib`, `subprocess`), `unittest`, bash, Claude Code plugin manifests.

**Spec:** [docs/superpowers/specs/2026-11-04-role-workflow-design.md](../specs/2026-11-04-role-workflow-design.md). Read it before any task.

## Global Constraints

- Python **3.10+**, standard library only; no `tomllib`, no third-party packages. Tests: `python3 -m unittest discover -s tests -t .` from the repo root.
- Plugin name `role-workflow`; repo `claude-orca-role-workflow`; MIT licence.
- The plugin **writes no files anywhere** at run time (uninstall must leave no trace) and never touches `~/.claude/agents/`, CLAUDE.md or settings.
- Never execute `orca` (Linux: screen reader). Detect Orca only via the `ORCA_CLI_COMMAND` environment variable. Never read Orca's settings database.
- Hooks **fail open**: unparseable commands, malformed hook input, or internal exceptions → allow (exit 0, no deny output). Missing Python → exit 1 with a one-line stderr message (non-blocking hook error).
- Deny output is exactly: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <reason>}}` on stdout, exit 0.
- The plugin's agents are dispatched as `role-workflow:implementer` and `role-workflow:reviewer`. All refusal and guidance text uses those names.
- Refusal and guidance text: short, generic (no author paths, no Forgejo), each rule with a one-sentence why.
- Config dir is `$CLAUDE_CONFIG_DIR` if set, else `~/.claude`.
- Before Task 4, the implementer confirms against current Claude Code hook docs: the PowerShell tool's name (assumed `PowerShell`), the Agent tool's name (`Agent`, legacy `Task`) and its input keys (`subagent_type`, `model`), and the deny JSON above. If any differ, use the documented value and note it in the commit message.

## Review Focus

1. **Text that only mentions orca.** Commit messages, `grep` patterns, `echo` strings, and heredoc bodies containing `orca agent launch --agent claude` must be allowed. Tests in Task 1.
2. **Windows command shapes.** `& $env:ORCA_CLI_COMMAND orchestration worker-start …` in PowerShell, `C:\Users\x\AppData\Local\orca\orca.exe agent launch …`, and quoted Windows paths in Git Bash must be recognised. Tests in Task 1.
3. **No usable Python, or the Windows Store `python3` stub.** The launcher must skip an interpreter that fails the version probe. With none found, the hooks are inactive but never block, and doctor reports FAIL. Tests in Task 4 (launcher) and Task 5 (doctor).
4. **Malformed hook input** (empty stdin, non-JSON, missing `tool_input`, `command` not a string) → allow, no traceback on stdout. Tests in Task 4.
5. **Agent files as people really write them.** CRLF line endings, a quoted `model: "sonnet"`, no frontmatter, `name:` different from the filename, and the same name in both project and user dirs (project wins). Tests in Task 2.

---

## File structure

```
.claude-plugin/plugin.json          plugin manifest
.claude-plugin/marketplace.json     repo-as-marketplace, source "./"
agents/implementer.md               copied verbatim from ~/.claude/agents/
agents/reviewer.md                  copied verbatim from ~/.claude/agents/
commands/hierarchy-doctor.md        slash command → runs the doctor
hooks/hooks.json                    PreToolUse ×2, SessionStart
hooks/run-hook.cmd                  polyglot Windows/Unix launcher (from superpowers 7.0.0, MIT)
hooks/run-python                    bash: find Python 3.10+, cd to plugin root, exec module
role_workflow/__init__.py
role_workflow/__main__.py           CLI: orca-guard | agent-guard | session-guidance | doctor
role_workflow/decision.py           Refusal dataclass
role_workflow/messages.py           refusal texts + guidance text
role_workflow/orca_guard.py         Orca command parser
role_workflow/agent_defs.py         frontmatter + agent model resolution
role_workflow/agent_guard.py        Agent-call decision
role_workflow/doctor.py             health checks
tests/test_orca_guard.py
tests/test_agent_defs.py
tests/test_agent_guard.py
tests/test_cli.py
tests/test_doctor.py
README.md, LICENSE
```

---

### Task 1: Orca launch parser

**Files:**
- Create: `role_workflow/__init__.py` (empty), `role_workflow/decision.py`, `role_workflow/messages.py`, `role_workflow/orca_guard.py`, `LICENSE` (MIT, holder "Tony Headband")
- Test: `tests/__init__.py` (empty), `tests/test_orca_guard.py`

**Interfaces:**
- Produces:
  - `decision.Refusal` — `@dataclass(frozen=True) class Refusal: reason: str`
  - `messages.orca_refusal(launch: str) -> str`, where `launch` is the matched form, e.g. `"orchestration worker-start"`
  - `orca_guard.check_orca_command(command: str, shell: Literal["bash", "powershell"], env: Mapping[str, str]) -> Refusal | None`

**Rules the function implements** (from the spec, Layer A, plus Orca's verified usage):
- Split into simple commands on `;`, `&&`, `||`, `|`, `&`, `(`, `)`, and newlines. Skip heredoc bodies: after a `<<WORD`, `<<-WORD`, `<<'WORD'` or `<<"WORD"`, ignore lines until one equal to `WORD` (stripped of leading tabs for `<<-`).
- Tokenise each command with `shlex.shlex(…, posix=True, punctuation_chars=True)`, `whitespace_split=True`. For `shell="powershell"`, first replace `\` with `/` (backslash isn't an escape in PowerShell). A `ValueError` from shlex → return `None`.
- Skip leading `VAR=value` assignments and the prefixes `&`, `command`, `exec`, `env`. The next token is the executable.
- The executable is Orca if it is literally `$ORCA_CLI_COMMAND`, `${ORCA_CLI_COMMAND}` or `$env:ORCA_CLI_COMMAND`, equals `env["ORCA_CLI_COMMAND"]` (when set), or its base name (split on `/` and `\`, lower-cased, `.exe` removed) is `orca`, `orca-ide` or `orca-dev`.
- The subcommand is the first two following tokens that don't start with `-`. Launch forms: `orchestration worker-start`, `agent launch`, `worktree create`.
- Read flags from the remaining tokens, accepting `--flag value` and `--flag=value`:
  - `worktree create` is a launch only when `--agent` is present.
  - `worker-start` with `--terminal` is not a launch.
  - A launch is checked only when the `--agent` value, lower-cased, is `claude`. Any other value, or a missing `--agent`, → `None`.
  - A launch passes when `--model` has a non-empty value.
- The first offending launch in the line → `Refusal(messages.orca_refusal(form))`.

**Refusal text:** it must contain the form, `--model sonnet` (building), `--model opus` (reviewing or coordinating), and one sentence of why: without it, Orca applies your chat default, which may be Opus at high effort, to every worker. Wording is otherwise the implementer's.

- [ ] **Step 1: Write the failing tests** in `tests/test_orca_guard.py`, class `CheckOrcaCommandTest`, using a `refused(cmd, shell="bash", env={})` helper that returns `check_orca_command(...) is not None`. Each test asserts the following:

```python
# refused
"orca orchestration worker-start --spec 'x' --agent claude"
'"$ORCA_CLI_COMMAND" orchestration worker-start --task t1 --agent claude'
"${ORCA_CLI_COMMAND} agent launch --agent claude --prompt hi"
"orca-ide worktree create --name a --agent claude"
"orca-dev agent launch --agent=claude"
"cd repo && orca agent launch --agent claude"
"FOO=1 orca agent launch --agent claude"
"orca agent launch --agent claude --model="                         # empty value
'"C:\\Users\\x\\orca\\orca.exe" agent launch --agent claude'          # bash, quoted Windows path
("& $env:ORCA_CLI_COMMAND orchestration worker-start --agent claude", "powershell")
("C:\\Users\\x\\AppData\\Local\\orca\\orca.exe agent launch --agent claude", "powershell")
("/opt/orca/bin/orca-cli agent launch --agent claude", env={"ORCA_CLI_COMMAND": "/opt/orca/bin/orca-cli"})
"echo ok\norca agent launch --agent claude"                         # second line
# allowed
"orca orchestration worker-start --agent claude --model sonnet"
"orca agent launch --agent claude --model=opus --effort high"
"orca worktree create --name a"                                     # no --agent
"orca orchestration worker-start --terminal term-1 --spec x"        # existing terminal
"orca agent launch --agent codex"
"orca worktree create --agent shell"
'git commit -m "orca agent launch --agent claude"'
'grep -rn "worker-start" src'
'echo "orca agent launch --agent claude"'
"cat <<'EOF' > notes.md\norca agent launch --agent claude\nEOF"
"cat <<-EOF\n\torca agent launch --agent claude\n\tEOF"
"orca orchestration status"
"orca agent launch --agent claude 'unterminated"                    # unparseable → allow
```

Also: `test_refusal_text` asserts that the reason for `orca agent launch --agent claude` contains `"agent launch"`, `"--model sonnet"` and `"--model opus"`.

- [ ] **Step 2: Run** `python3 -m unittest tests.test_orca_guard -v`. Expected: errors with `ModuleNotFoundError: role_workflow.orca_guard`.
- [ ] **Step 3: Implement** `Refusal`, `orca_refusal` and `check_orca_command` per the rules above. Private helpers in `orca_guard.py` as needed: `_split_commands(command: str) -> list[str]` for the heredoc-aware split, and `_is_orca(token, env) -> bool`.
- [ ] **Step 4: Run** `python3 -m unittest tests.test_orca_guard -v`. Expected: all pass.
- [ ] **Step 5: Commit** `git add LICENSE role_workflow tests && git commit -m "feat: Orca launch parser that requires an explicit model"`

---

### Task 2: Agent definitions and role agents

**Files:**
- Create: `role_workflow/agent_defs.py`
- Create: `agents/implementer.md`, `agents/reviewer.md`, both copied byte-for-byte from `~/.claude/agents/` (the originals stay until the author's migration step, see README)
- Test: `tests/test_agent_defs.py`

**Interfaces:**
- Produces:
  - `agent_defs.parse_frontmatter(text: str) -> dict[str, str]`: keys/values between a leading `---` line and the next `---`. It tolerates CRLF and strips matching surrounding quotes from values. With no frontmatter it returns `{}`. Multi-line YAML values are ignored (only `key: value` lines are read).
  - `agent_defs.find_agent_model(subagent_type: str, cwd: Path, config_dir: Path, plugin_root: Path) -> str | None` returns the agent's `model` value, or `None` if the agent isn't found or declares no model.

**Lookup rules:**
- `"<plugin>:<name>"`: search `plugin_root/agents` when `<plugin>` is `role-workflow`. Otherwise read `config_dir/plugins/installed_plugins.json` (`{"plugins": {"<plugin>@<marketplace>": [{"installPath": …}, …]}}`) and search `<installPath>/agents` for each entry whose key starts with `<plugin>@`.
- A plain `"<name>"`: search `cwd/.claude/agents`, then `config_dir/agents`. The first match wins.
- Within a directory, recursively check each `*.md` file. It matches when its frontmatter `name` equals `<name>`, or, if it has no `name`, when the file stem equals `<name>`.
- Unreadable files or a malformed `installed_plugins.json` are skipped silently.

- [ ] **Step 1: Write the failing tests.** Use `tempfile.TemporaryDirectory` trees, and add one test against the real `agents/` folder:

```python
test_frontmatter_basic:        "---\nname: a\nmodel: sonnet\n---\nbody" -> {"name": "a", "model": "sonnet"}
test_frontmatter_crlf_quoted:  '---\r\nname: a\r\nmodel: "opus"\r\n---\r\n' -> model == "opus"
test_frontmatter_missing:      "# just text" -> {}
test_name_differs_from_stem:   agents/x.md with name: builder, model: haiku -> find("builder") == "haiku"
test_stem_fallback:            agents/solo.md, frontmatter has model only -> find("solo") == model
test_project_beats_user:       same name in cwd/.claude/agents (sonnet) and config_dir/agents (opus) -> "sonnet"
test_no_model:                 found, no model key -> None
test_not_found:                -> None
test_plugin_namespace_self:    find("role-workflow:implementer", plugin_root=repo root) == "sonnet"
test_plugin_namespace_self_reviewer: -> "opus"
test_other_plugin_via_registry: installed_plugins.json points to tmp installPath with agents/r.md (model: opus) -> find("other:r") == "opus"
test_bad_registry_json:        installed_plugins.json = "{" -> None, no exception
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_agent_defs -v`. Expected: `ModuleNotFoundError`.
- [ ] **Step 3: Copy** the two agent files: `cp ~/.claude/agents/implementer.md ~/.claude/agents/reviewer.md agents/`. Implement `parse_frontmatter` and `find_agent_model`.
- [ ] **Step 4: Run** the tests. Expected: all pass.
- [ ] **Step 5: Commit** `git add agents role_workflow/agent_defs.py tests/test_agent_defs.py && git commit -m "feat: resolve subagent models from agent definitions; ship implementer and reviewer"`

---

### Task 3: Agent-call guard

**Files:**
- Create: `role_workflow/agent_guard.py`
- Modify: `role_workflow/messages.py` (add `agent_refusal`)
- Test: `tests/test_agent_guard.py`

**Interfaces:**
- Consumes: `Refusal` (Task 1), `find_agent_model` (Task 2).
- Produces:
  - `messages.agent_refusal(subagent_type: str | None) -> str`
  - `agent_guard.check_agent_call(tool_input: Mapping, cwd: Path, config_dir: Path, plugin_root: Path) -> Refusal | None`

**Rules** (spec, Layer B):
1. `subagent_type == "fork"` → allow.
2. `model` on the call is a non-empty string other than `inherit` (case-insensitive) → allow. A contradicting model on a role agent is allowed on purpose (spec: "Open on purpose").
3. Otherwise, a `subagent_type` (missing → treated as `general-purpose`) whose `find_agent_model` result is non-empty and not `inherit` → allow.
4. Otherwise → `Refusal(agent_refusal(subagent_type))`.

**Refusal text** must contain: `role-workflow:implementer` (building, Sonnet), `role-workflow:reviewer` (reviewing, Opus), the option to pass `model` explicitly, with `opus` for research/exploration and `haiku` for plain string or file searches, and one sentence of why: without a model, the subagent inherits this chat's model.

- [ ] **Step 1: Write the failing tests** with a `tmp` config dir and the real repo as `plugin_root`:

```python
refused:  {}                                         # untyped
refused:  {"subagent_type": "general-purpose"}
refused:  {"subagent_type": "Explore"}               # built-in, no definition
refused:  {"subagent_type": "general-purpose", "model": "inherit"}
refused:  {"subagent_type": "x"} where config_dir/agents/x.md has model: inherit
refused:  {"subagent_type": "general-purpose", "model": ""}
allowed:  {"subagent_type": "fork"}
allowed:  {"subagent_type": "general-purpose", "model": "haiku"}
allowed:  {"subagent_type": "role-workflow:reviewer"}
allowed:  {"subagent_type": "role-workflow:reviewer", "model": "sonnet"}   # open on purpose
allowed:  {"subagent_type": "Explore", "model": "opus"}
test_refusal_text: contains "role-workflow:implementer", "role-workflow:reviewer", "model"
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_agent_guard -v`. Expected: failures (missing module).
- [ ] **Step 3: Implement** `agent_refusal` and `check_agent_call`.
- [ ] **Step 4: Run** `python3 -m unittest discover -s tests -t . -v`. Expected: all pass.
- [ ] **Step 5: Commit** `git add role_workflow tests/test_agent_guard.py && git commit -m "feat: refuse subagent calls without an explicit model"`

---

### Task 4: Hook wiring, guidance and plugin manifests

**Files:**
- Create: `role_workflow/__main__.py`, `hooks/hooks.json`, `hooks/run-hook.cmd`, `hooks/run-python` (executable), `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Modify: `role_workflow/messages.py` (add `GUIDANCE`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `check_orca_command`, `check_agent_call`, `Refusal`, `messages.GUIDANCE`.
- Produces:
  - `__main__.main(argv: list[str], stdin: TextIO, stdout: TextIO, environ: Mapping[str, str]) -> int`, with subcommands `orca-guard`, `agent-guard`, `session-guidance` and `doctor` (doctor is wired in Task 5; until then it prints `not implemented` and returns 2)
  - `__main__.config_dir(environ) -> Path`
  - `__main__.PLUGIN_ROOT: Path` = `Path(__file__).resolve().parent.parent`
  - The launcher contract: `hooks/run-python <subcommand> [args…]` runs `python -m role_workflow <subcommand> [args…]` from the plugin root, with stdin passed through.

**Behaviour:**
- **`orca-guard`:** read stdin JSON. If `tool_name` is `Bash` → shell `bash`; `PowerShell` → `powershell`; anything else → allow. Pass `tool_input.command` and `environ` to `check_orca_command`.
- **`agent-guard`:** pass `tool_input`, `Path(payload["cwd"])`, `config_dir(environ)` and `PLUGIN_ROOT` to `check_agent_call`.
- **Refusal:** print the deny JSON from Global Constraints. Allow: print nothing. Both return 0. Any exception, including bad JSON or missing keys → return 0 with nothing on stdout.
- **`session-guidance`:** print `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": GUIDANCE}}` and return 0.
- **`GUIDANCE`** (wording is the implementer's; content is fixed by the spec, Layer D), at most about 20 lines:
  - The session's own model plans and coordinates.
  - Build with `role-workflow:implementer`, or with Orca workers launched with `--model sonnet`.
  - Review with `role-workflow:reviewer`, or with Orca workers launched with `--model opus`, plus one final whole-branch review.
  - Research/exploration: pass `model: opus`. Plain string or file searches: pass `model: haiku`.
  - Don't override a role agent's model.
  - Subagent calls and Orca launches without a model will be refused.
  - "If you use superpowers' subagent-driven-development, dispatch `role-workflow:implementer`/`role-workflow:reviewer` for its implementer/reviewer steps."
  - Each rule gets a one-sentence why.
- **`hooks/run-hook.cmd`:** copy superpowers 7.0.0's `hooks/run-hook.cmd` verbatim (path: `~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/hooks/run-hook.cmd`) and add a one-line header comment crediting it (MIT).
- **`hooks/run-python`:**
  - Pick the first of `python3` and `python` that passes `"$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'`. This skips the Windows Store stub.
  - With none found: print `role-workflow: Python 3.10+ not found on PATH; hooks are inactive` to stderr and exit 1.
  - Otherwise `cd` to the plugin root (the script's parent's parent, found as superpowers does: no `dirname`, works with `\`) and `exec "$PY" -m role_workflow "$@"`. Running from the plugin root keeps a project's files from shadowing the module.
- **`hooks/hooks.json`:**
  - `PreToolUse` with matcher `Bash|PowerShell` → `"\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" run-python orca-guard"`.
  - `PreToolUse` with matcher `Agent|Task` → `… run-python agent-guard`.
  - `SessionStart` with matcher `startup|clear|compact` → `… run-python session-guidance`.
  - Every entry has `"type": "command"` and `"shell": "bash"`, as superpowers' `hooks.json` does.
- **`plugin.json`:** name `role-workflow`, version `0.1.0`, description, author `{"name": "Tony Headband"}`, license `MIT`, keywords.
- **`marketplace.json`:** marketplace name `claude-orca-role-workflow`, owner `Tony Headband`, and one plugin `role-workflow` with `"source": "./"`. Same shape as `~/.claude/plugins/cache/epp-claude/epp-claude/0.1.0/.claude-plugin/marketplace.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_cli.py`. Call `main` with `io.StringIO` streams, and run the launcher through `subprocess` (skipped unless `os.name == "posix"`):

```python
test_orca_guard_denies:     Bash payload "orca agent launch --agent claude" -> rc 0, stdout JSON permissionDecision == "deny", reason contains "--model sonnet"
test_orca_guard_powershell: tool_name "PowerShell", "& $env:ORCA_CLI_COMMAND agent launch --agent claude" -> deny
test_orca_guard_allows:     "ls -la" -> rc 0, stdout == ""
test_other_tool_ignored:    tool_name "Read" -> stdout == ""
test_agent_guard_denies:    {"tool_name": "Agent", "cwd": tmp, "tool_input": {"subagent_type": "general-purpose"}} -> deny
test_agent_guard_allows_reviewer: subagent_type "role-workflow:reviewer" -> stdout == ""
test_malformed_inputs:      for stdin in ["", "not json", "{}", '{"tool_name":"Bash","tool_input":{"command":5}}'] -> rc 0, stdout == ""
test_session_guidance:      JSON hookEventName == "SessionStart"; additionalContext contains "role-workflow:implementer", "role-workflow:reviewer", "--model sonnet", "--model opus"
test_launcher_end_to_end:   subprocess ["bash", "hooks/run-python", "orca-guard"] from a tmp cwd, with a payload whose command launches without a model -> stdout deny JSON
test_launcher_no_python:    PATH = a tmp dir holding only an executable `python3` stub (`#!/bin/sh` + `exit 9`, mimicking the Store stub); invoke [absolute path of bash, "hooks/run-python", "orca-guard"] -> rc 1, stderr contains "Python 3.10+ not found"
test_manifests_parse:       plugin.json, marketplace.json, hooks.json load as JSON; hooks.json has matchers "Bash|PowerShell", "Agent|Task" and a SessionStart entry
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_cli -v`. Expected: failures.
- [ ] **Step 3: Implement** everything listed under Files, then run `chmod +x hooks/run-python hooks/run-hook.cmd`.
- [ ] **Step 4: Run** the full suite: `python3 -m unittest discover -s tests -t . -v`. Expected: all pass. Then run `claude plugin validate .` if this Claude Code version has it. Expected: no errors.
- [ ] **Step 5: Commit** `git add .claude-plugin hooks role_workflow tests/test_cli.py && git commit -m "feat: wire guards and session guidance into Claude Code hooks"`

---

### Task 5: `/hierarchy-doctor`

**Files:**
- Create: `role_workflow/doctor.py`, `commands/hierarchy-doctor.md`
- Modify: `role_workflow/__main__.py` (the `doctor` subcommand takes `--cwd <path>`, prints the report and returns its exit code)
- Test: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `PLUGIN_ROOT`, `config_dir`, `find_agent_model`, and the `hooks/run-python` launcher contract.
- Produces:
  - `doctor.Check`: `@dataclass(frozen=True)` with fields `status: Literal["OK", "FAIL", "N/A", "INFO"]`, `name: str`, `detail: str`, `fix: str = ""`
  - `doctor.run_checks(plugin_root: Path, cwd: Path, config_dir: Path, environ: Mapping[str, str], run_hook: Callable[[str, str], tuple[int, str]]) -> list[Check]`, where `run_hook(subcommand, stdin_json)` returns `(returncode, stdout)`. The default runs `bash <plugin_root>/hooks/run-python <subcommand>`, and tests inject a fake.
  - `doctor.format_report(checks: list[Check]) -> str`: one line per check, `[STATUS] name: detail`, plus `  fix: …` on FAIL. The exit code is 1 if any check FAILs, else 0.

**Checks, in order:**
1. **Orca hook:**
   - `N/A` with "Orca not detected (ORCA_CLI_COMMAND unset); guard idle" if the variable is unset.
   - Otherwise run the hook on a launch with no model (expect deny) and one with `--model sonnet` (expect empty stdout). `OK` or `FAIL`.
   - If `hooks.json` lacks the `Bash|PowerShell` matcher, `FAIL` regardless.
2. **Agent hook:** `hooks.json` has the `Agent|Task` matcher. `general-purpose` with no model gives deny, and `role-workflow:reviewer` gives allow.
3. **Agents:**
   - `find_agent_model` gives `sonnet` for `role-workflow:implementer` and `opus` for `role-workflow:reviewer`.
   - `FAIL` if `config_dir/agents/implementer.md` or `reviewer.md` exists, with the fix "delete it; the plugin's copy replaces it".
4. **Guidance:** the `session-guidance` output parses and has a non-empty `additionalContext`.
5. **Python:** a `run_hook` return code of 1 → `FAIL` on checks 1, 2 and 4, with detail "Python 3.10+ not found", and the fix names the README requirements.
6. **INFO:** shown only when set. "CLAUDE_CODE_SUBAGENT_MODEL=<v> is set; role-workflow still requires an explicit model per call."

**`commands/hierarchy-doctor.md`:**
- Frontmatter `description: Check that role-workflow's hooks, role agents and session guidance are active`.
- Body: tell Claude to run `bash "${CLAUDE_PLUGIN_ROOT}/hooks/run-python" doctor --cwd "$PWD"` with the Bash tool, show the output verbatim, then explain each FAIL line's fix in one sentence. It must change nothing itself.

- [ ] **Step 1: Write the failing tests** with a fake `run_hook` and tmp config dirs:

```python
test_all_green:            fake hook mimics real deny/allow; env has ORCA_CLI_COMMAND -> no FAIL, statuses of checks 1-4 == OK
test_orca_na:              env without ORCA_CLI_COMMAND -> check 1 status "N/A"
test_shadow_agent:         config_dir/agents/reviewer.md exists -> Agents FAIL, fix mentions "delete"
test_hook_not_refusing:    fake returns (0, "") for everything -> Agent hook FAIL
test_no_python:            fake returns (1, "") -> checks 1 (with ORCA set), 2, 4 FAIL with "Python 3.10+ not found"
test_subagent_env_info:    CLAUDE_CODE_SUBAGENT_MODEL=sonnet -> one INFO check
test_report_exit_code:     format_report lines start with "[OK]"/"[FAIL]"…; main(["doctor","--cwd",tmp]) returns 1 when a FAIL exists
test_real_launcher:        (posix only) run_checks with the default run_hook and ORCA_CLI_COMMAND set -> checks 1, 2, 4 OK
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_doctor -v`. Expected: failures.
- [ ] **Step 3: Implement** `doctor.py`, the `doctor` subcommand and the command file.
- [ ] **Step 4: Run** the full suite. Expected: all pass. Run `bash hooks/run-python doctor --cwd "$PWD"`. Expected: a report whose Agents line FAILs on this machine while `~/.claude/agents/reviewer.md` still exists. That is correct; note it.
- [ ] **Step 5: Commit** `git add commands role_workflow tests/test_doctor.py && git commit -m "feat: /hierarchy-doctor reports the health of each layer"`

---

### Task 6: README and local install check

**Files:**
- Create: `README.md`

README sections (content fixed by the spec; wording is the implementer's):
- **What it does.** The three layers plus the doctor, with the why from the spec's Intent.
- **Install.** `/plugin marketplace add <owner>/claude-orca-role-workflow`, then `/plugin install role-workflow@claude-orca-role-workflow`, then `/hierarchy-doctor`.
- **Requirements.** Python 3.10+ on PATH, plus Git for Windows on Windows.
- **Orca.** It targets Orca (MIT, link its repo) and works without it. It refuses the three launch forms when they have no `--model`, and why. Known gaps: automations, direct `claude` runs, and no role check on workers.
- **Rules.** The Agent-call allow/refuse rules. "Explicit, not role-checked", and why it's the same in both hosts.
- **Migrating from personal agents.** Delete `~/.claude/agents/implementer.md` and `reviewer.md` after installing. Doctor flags them.
- **Uninstall.** One command; the plugin writes no files.
- **Development.** How to run the tests, and the credit for `run-hook.cmd` (superpowers, MIT).

- [ ] **Step 1: Write** `README.md`.
- [ ] **Step 2: Local install check.** Run `claude --plugin-dir "$PWD" -p "/hierarchy-doctor"`, or install via `/plugin marketplace add "$PWD"` in a scratch session.
  - Expected: the doctor report appears, with the Agents line FAILing only because of the personal copies.
  - In that session, an Agent call with `subagent_type: general-purpose` and no model is refused with the plugin's message.
- [ ] **Step 3: Commit** `git add README.md && git commit -m "docs: README for install, requirements, rules and Orca notes"`

---

## After the plan (not tasks)

- The author pushes to GitHub, installs from the marketplace, deletes the two personal agent files, and runs the field trial inside Orca on one project (spec: Done when).
- Request to the Orca developers: launcher and task/role metadata in the `agent.launch.before` payload (spec: Future work).
