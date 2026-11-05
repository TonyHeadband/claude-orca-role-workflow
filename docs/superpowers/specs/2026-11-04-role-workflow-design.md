# role-workflow — design

Date: 2026-11-04 · Status: draft for approval · Source brief: [agent-hierarchy-plugin-brief.md](../../agent-hierarchy-plugin-brief.md)

## Intent

Multi-agent work currently picks models by accident. On 2026-11-04 every Orca build worker for one project ran on Opus at high effort because that was Orca's chat default, which burned 57% of a 5-hour usage window in about 3 hours. Untyped / `general-purpose` subagents (which inherit the chat's model) were 93% of a week's subagent usage.

This plugin is **infrastructure**: it makes a role hierarchy hold by configuration rather than by the coordinator remembering a flag.

- **Opus**: brainstorming, specs, plans, coordination (the chats the user opens themselves).
- **Sonnet**: implementation (Orca workers, in-session builders).
- **Opus**: reviews (per task or lane, plus one final whole-branch review).

It is also a **teaching tool**. The author is using it to teach a friend Claude Code, and possibly Orca. Refusals and guidance explain *why* in a sentence, so the structure is learned from the tool itself.

## Goals

- One `/plugin install` gives the hooks, the role agents and the session guidance. One uninstall removes all of them.
- No agent launch, whether an Orca worker or an in-session subagent, starts without an explicitly chosen model.
- A review dispatched from any session runs on Opus via the `reviewer` agent. A build runs on Sonnet via `implementer`.
- Works on Linux, macOS and Windows. Works with or without Orca, and with or without superpowers.
- Shareable on GitHub with nothing personal to the author inside.

## Non-goals

- Checking, reporting or changing Orca's in-app chat model default. The user deliberately switches it (e.g. Sonnet for fast local iteration). It is out of scope entirely, and `/hierarchy-doctor` does not read it.
- Changing Orca itself, editing Orca's database, or a per-role Orca feature (that belongs with the Orca developers).
- Making the models or role text configurable. They are fixed in the plugin for now (see Decisions).

## Anti-goals (failure even if it "works")

- **Guessing a model.** The hooks never rewrite a command to add a model. A review launched without a model must not silently become Sonnet. Refuse, explain, let the caller choose.
- **Blocking things that only mention orca** (`grep orca`, `echo "orca agent launch"`, `git log --grep=orca`, reading Orca docs). False positives on ordinary commands make the plugin get uninstalled.
- **Touching a friend's setup** beyond what the plugin installs (no edits to their `~/.claude/agents/`, CLAUDE.md or settings).
- **Personal content shipping**: no Forgejo, no author paths, no author-specific workflow rules.

## Decided

### Names and distribution

- GitHub repo `claude-orca-role-workflow` (this repo), MIT licence. The repo is its own marketplace (`.claude-plugin/marketplace.json` alongside the plugin), so install is `/plugin marketplace add <owner>/claude-orca-role-workflow` then `/plugin install role-workflow@<marketplace>`.
- Plugin name: `role-workflow`. Half of it is Orca-specific and half works in any Claude Code setup, so the plugin name doesn't say "orca".
- The README states that the plugin targets Orca (MIT; link its repo) as a first-class host, and works without it.

### Layer A: Orca launch hook (hard)

`PreToolUse` hook matching **both `Bash` and `PowerShell`** tools (Windows sessions can run commands through PowerShell, so a Bash-only hook would leak).

Refuses when a command launches an Orca agent **without `--model`**. The launch forms:

- `<orca> orchestration worker-start …`
- `<orca> agent launch …`
- `<orca> worktree create … --agent …` (only when `--agent` is present; plain worktree creation passes)

`<orca>` is any of: `orca`, `orca-ide`, `orca-dev`, or the value of `$ORCA_CLI_COMMAND`. Commands are often written literally as `"$ORCA_CLI_COMMAND" …`, so the hook must recognise the unexpanded `$ORCA_CLI_COMMAND` / `${ORCA_CLI_COMMAND}` token as well as its expanded path. Match on the executable's **base name**, ignoring directory, `/` or `\` separators, and a `.exe` suffix.

`--model x` and `--model=x` both count as explicit. `--effort` is not required (only the model is enforced).

*Designer's calls (not discussed with the user):*
- **Claude launches only.** The rule applies when the launched agent is Claude (`--agent claude`). Other agents (`--agent codex`, `--agent shell`, …) pass untouched, because their model names differ and they're outside this hierarchy.

*Verified in Orca's source (stablyai/orca `d586aff1`, 2026-11-04):*
- Usage is `worker-start … (--agent <agent> | --terminal <handle>) … [--model <id>] [--effort <level>]` and `agent launch --agent <id> … [--model <id>] [--effort <level>]`. A `worker-start --terminal <handle>` dispatches into an existing terminal and launches nothing, so it **passes**.
- Neither command forwards other `claude` arguments, so a worker can't be started as a named Claude agent (`claude --agent reviewer`). Automations' `--extra-agent-args` allows only `--model`, `--effort` and `--add-dir`. This is why Orca workers get the "explicit" check only, never a role check (see Layer B).
- **Scope is exactly the three forms.** Orca automations, and direct `claude` / `claude -p` runs from a shell, are not matched: matching `claude` invites false positives, and those launches are typed deliberately. The README states this gap.

Parsing must be quote-aware and handle compound commands (`&&`, `||`, `;`, pipes, `$( )`, subshells): a launch anywhere in the line is checked, and a launch inside a quoted string argument (e.g. `echo "orca agent launch"`) is not. When the command cannot be parsed, **allow** it (fail open). The hook must never become the reason an ordinary command can't run. Fail-open cases are covered by tests.

Refusal message (to Claude, via the hook's deny reason) names the command, says to add `--model sonnet` for building or `--model opus` for reviewing/coordination, and gives the one-sentence why.

### Layer B: Agent-tool hook (hard)

`PreToolUse` hook on the `Agent` tool. Refuses a subagent call unless its model is explicit:

- **Allowed:** the call sets `model`, **or** its `subagent_type` resolves to an agent definition whose frontmatter sets `model`. The hook reads the frontmatter at run time rather than keeping a hard-coded list, so `implementer` (sonnet) and `reviewer` (opus) pass, and so does any user or project agent that declares a model.
- **Allowed:** `subagent_type: "fork"`. Forks always run on the parent's model and are the coordinator doing its own work.
- **Refused:** untyped calls, `general-purpose`, and any typed agent with no model in its definition and none on the call. This applies to built-ins (`Explore`, `Plan`, …) and to user agents alike.

The user chose strict to start. Loosening comes later, based on real friction.

*Designer's calls (not discussed with the user):*
- **`inherit` is not explicit**, on the call or in frontmatter. It reproduces the exact accident the plugin exists to stop.
- **A configured default subagent model (e.g. `CLAUDE_CODE_SUBAGENT_MODEL`) doesn't count either.** Strict start: the call or the agent definition has to say the model. Doctor shows the variable as information if it's set.

**Open on purpose: an explicit model that contradicts the role.** A call such as `reviewer` with `model: sonnet` passes, because the rule is "the model is explicit", not "the model is right for the role". This is the user's decision, made to keep behaviour the same in Claude Code and Orca. In Orca a worker launch carries no role, so its hook can only check that a model is present (see Layer A), and the Agent hook holds to the same rule. The README says this plainly. The likely sources of such overrides are a coordinator saving usage, a skill that picks models per task, and a session that lost its guidance after compaction. The session guidance tells callers not to override role agents' models. Revisit together with the Orca companion plugin (Future work).

Refusal message: suggests `implementer` for building, `reviewer` for reviewing, or passing `model` explicitly, with the why.

### Layer C: Role agents (hard for those roles)

Ship `agents/implementer.md` (Sonnet, medium effort, edit tools, TDD, fixed report) and `agents/reviewer.md` (Opus, high effort, read-only, ranked findings plus verdict). Content comes from the author's existing `~/.claude/agents/implementer.md` and `reviewer.md`, which were checked and are already generic.

**Author-only migration** (README note, not a plugin action): delete those two originals after installing so they don't shadow or duplicate the plugin's copies. The plugin never touches `~/.claude/agents/`.

**Future role agents (not in this version):** a research/explore agent on Opus and a string-matching search agent on Haiku. Until they exist, the guidance and the refusal text recommend passing `model` explicitly on that work: `opus` for research and exploration that needs judgement, `haiku` for plain string or file searches.

### Layer D: Session guidance (soft)

`SessionStart` hook that injects short additional context: don't override a role agent's model; which role for which step (plan/coordinate on the session's own model, build with `implementer` or Orca workers with `--model sonnet`, review with `reviewer` or workers with `--model opus`, one final whole-branch review), each with its one-sentence why, and the fact that unmodelled launches will be refused. Superpowers is mentioned only conditionally ("if you use superpowers' subagent-driven-development, dispatch `implementer`/`reviewer` for its builder/reviewer steps"). This is how skills that pick their own subagents get steered; there is no separate hook for them. The text is generic and contains no author-specific rules. It is not written into CLAUDE.md.

Workers launched by Orca run the real `claude` binary with the user's home folder and `--setting-sources=user,project,local`, so they get the plugin too (hooks, agents, guidance). That is intended.

### `/hierarchy-doctor` command

Reports, one line per check, green / red / n/a, with the fix for each red:

1. **Orca hook**: registered, and the hook script refuses a built-in bad fixture and allows a good one (it runs the script on sample input; nothing is launched). If Orca isn't detected, report "n/a (Orca not detected)", not red.
2. **Agent hook**: registered, and refuses/allows fixtures the same way.
3. **Agents**: `implementer` and `reviewer` resolve with the expected models, and no same-named copies exist in `~/.claude/agents/` that would shadow them.
4. **Guidance**: the SessionStart hook is registered and emits its text.

It never runs the `orca` binary (on Linux, bare `orca` outside an Orca terminal starts the GNOME screen reader), and it never reads Orca's settings database.

### Platform and tooling

- Hook scripts: **Python 3.10+, standard library only** (`shlex`-based parsing). Python is a documented requirement.
- The hook command in `hooks/hooks.json` must resolve the interpreter, trying `python3` and then `python`, because on Windows `python3` is often a Store stub and python.org installs `python`/`py`. It must preserve the script's exit code and output exactly (no `a || b` that reruns on a deny).
- Windows: Claude Code runs hooks through Git Bash, so Git for Windows is a documented requirement.
- Tests: stdlib `unittest`, runnable with `python -m unittest` from the repo root, no extra installs.

### Fixed, not configurable

Models and role text are fixed in the plugin. Loosening means editing the plugin, which is a visible, versioned change. A plugin settings file may come later.

## Done when

- One `/plugin install` gives the agents, both hooks and the guidance; `/hierarchy-doctor` is all green (or n/a for Orca where absent).
- An Orca `worker-start`, `agent launch` or `worktree create --agent` without `--model` is refused, via Bash and via PowerShell.
- An untyped / `general-purpose` Agent call without `model` is refused, and a `reviewer` dispatch from any session without a `model` override runs on Opus.
- Uninstalling leaves no trace.
- Tests cover the Orca parser: every launch form; each `<orca>` spelling including `$ORCA_CLI_COMMAND`, `${ORCA_CLI_COMMAND}`, absolute POSIX and Windows paths, and `.exe`; quoting; `--model=x` vs `--model x`; compound commands; commands that only mention orca; and fail-open on unparseable input. Tests also cover the Agent hook's allow/refuse matrix, including fork and frontmatter resolution.
- A field trial: installed from the marketplace and used inside Orca on one real project, with the refusals and guidance observed in practice before loosening or extending anything.
- README covers install, requirements (Python, Git for Windows), what each layer does and why, the Orca note, and the author-only migration note.

## Future work (not in this version)

- **Research and search role agents:** research/explore on Opus, string matching on Haiku (see Layer C).
- **Orca companion plugin.** Orca 1.4.248 added plugin hooks. `agent.launch.before` runs before every agent CLI launch from any launcher and can rewrite `command` (for example, add `claude --agent reviewer`) or deny the launch. Its payload today is only `agent`, workspace, terminal, `command` and `env`: no launcher kind and no task or role. And Orca always fills `--model` from the chat default, so at that point an explicit model can't be told from a defaulted one. Once Orca adds launcher and task/role metadata, which is worth requesting from the Orca developers, a companion plugin could apply role checks to workers too, and the open decision in Layer B can be revisited for both hosts together.

## Left to the builder

- Repo layout within the plugin conventions; script and module names; how parser code is shared between the hook and doctor.
- The exact hook output mechanism (JSON `permissionDecision: "deny"` with a reason vs exit code 2), provided the reason reaches Claude.
- How the Agent hook locates agent definitions (plugin, user, project, built-ins) and handles plugin-namespaced `subagent_type` values, which must be verified against the current Claude Code docs.
- Exact wording of refusals and guidance, within the constraints above (short, explains why, generic).
