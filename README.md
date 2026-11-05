# role-workflow

A Claude Code plugin that keeps each kind of work on the model that suits it. It is built for [Orca](https://github.com/stablyai/orca) and also works without it.

## What it does

When you run several agents at once, the model each one uses is easy to get wrong without noticing. A subagent or an Orca worker that is started without a model inherits the chat's model and effort. If your chat is on Opus at high effort, every helper runs on Opus at high effort. In one real case this used 57% of a 5-hour usage window in about 3 hours.

The plugin sets up this split:

- **Opus** plans, writes specs and coordinates. These are the chats you open yourself.
- **Sonnet** builds. It is cheaper and fast enough for well-specified code.
- **Opus** reviews: once per task or lane, and once more over the whole branch at the end.

It does this with four parts:

1. **Orca launch guard (hard).** Refuses an Orca command that starts a Claude agent with no `--model`.
2. **Agent guard (hard).** Refuses a subagent call that has no explicit model.
3. **Role agents (hard for those roles).** `implementer` runs on Sonnet. `reviewer` runs on Opus and is read-only. Calling them gets the right model with no extra flag.
4. **Session guidance (soft).** At session start, a short note tells Claude which role to use for which step, and why. It is re-sent after `/clear` and after compaction.

Every refusal explains why in a sentence, so the structure is easy to learn from the tool itself.

`/hierarchy-doctor` checks that all of this is active.

## Install

In Claude Code:

```
/plugin marketplace add <owner>/claude-orca-role-workflow
/plugin install role-workflow@claude-orca-role-workflow
/hierarchy-doctor
```

`<owner>` is the GitHub account that hosts this repo. The doctor prints one line per check and a fix for each failure.

## Requirements

- Python 3.10 or newer on your PATH, as `python3` or `python`. The hooks are Python scripts that use only the standard library.
- On Windows, [Git for Windows](https://git-scm.com/download/win). Claude Code runs hooks through Git Bash.

## Orca

The plugin treats Orca (MIT, <https://github.com/stablyai/orca>) as a first-class host. Orca is optional. Without it, the Orca guard never triggers and the doctor reports "n/a (Orca not detected)".

The guard refuses these three commands when they start a Claude agent without `--model`:

- `orca orchestration worker-start …`
- `orca agent launch …`
- `orca worktree create … --agent claude`

It also recognises `orca-ide`, `orca-dev`, `$ORCA_CLI_COMMAND` and full paths to them, on both the Bash and PowerShell tools. Both `--model x` and `--model=x` count. `--effort` is not required.

Why: without `--model`, Orca fills in your chat's default model. That is how every worker in one project ended up on Opus.

The guard is careful about what it does not block. Plain `worktree create`, `worker-start --terminal` (which launches nothing), non-Claude agents such as `--agent codex`, and commands that only mention orca (`grep orca`, `echo "orca agent launch"`) all pass. If a command cannot be parsed, the guard lets it through. It never rewrites a command to add a model for you, because a guessed model is worse than a refusal.

### Known gaps

- **Orca automations are not checked.** Only the three launch forms above are matched.
- **Direct `claude` runs are not checked.** A `claude` or `claude -p` typed in a shell is a deliberate act, and matching `claude` would cause false alarms.
- **Workers get no role check.** Orca cannot start a worker as a named agent, so the guard can only check that a model is present. It cannot check that a reviewer got Opus.
- **Orca's in-app chat model is out of scope.** You may switch it on purpose, for example to Sonnet for quick local work. The plugin neither reads nor changes it.

## Rules

For the `Agent` tool (subagents inside a session):

| Call | Result |
| --- | --- |
| Sets `model` | Allowed |
| `subagent_type` is an agent whose definition sets `model` (`implementer`, `reviewer`, or your own) | Allowed |
| `subagent_type: "fork"` | Allowed. A fork runs on the parent's model and is the coordinator doing its own work. |
| No `subagent_type`, or `general-purpose` | Refused |
| Any other agent with no model in its definition and none on the call (including built-ins like `Explore` and `Plan`) | Refused |
| `model: inherit`, on the call or in the definition | Refused. It reproduces the accident this plugin exists to stop. |

A default set with `CLAUDE_CODE_SUBAGENT_MODEL` does not count as explicit either. The call or the agent definition has to name the model.

When refused, Claude is told to use `role-workflow:implementer` for building, `role-workflow:reviewer` for reviewing, or to pass `model` itself: `opus` for research that needs judgement, `haiku` for plain string or file searches.

### Explicit, not role-checked

The rule is "the model is explicit", not "the model is right for the role". A `reviewer` call with `model: sonnet` is allowed on purpose.

The reason: in Orca a worker launch carries no role, so the Orca guard can only check that a model is present. The Agent guard follows the same rule, so Claude Code and Orca behave the same way. The session guidance tells Claude not to override a role agent's model. If a role check for Orca workers becomes possible, both hosts can be tightened together.

## Migrating from personal agents

This is for the author, who already had `implementer.md` and `reviewer.md` in their own config. After installing, delete `~/.claude/agents/implementer.md` and `~/.claude/agents/reviewer.md` so they do not shadow the plugin's copies. `/hierarchy-doctor` flags them. The plugin never edits `~/.claude/agents/` itself.

## Uninstall

```
/plugin uninstall role-workflow@claude-orca-role-workflow
```

The plugin writes no files of its own, so nothing is left behind.

## Development

Run the tests from the repo root. They use only the standard library:

```
python -m unittest
```

To try the plugin without installing it:

```
claude --model sonnet --plugin-dir "$PWD"
```

Always pass `--model` here. The plugin does not guard a direct `claude` run, so nothing else will stop it from using your default.

Credits: `hooks/run-hook.cmd` is adapted from the [superpowers](https://github.com/obra/superpowers) plugin (MIT). The plugin itself is MIT licensed; see [LICENSE](LICENSE).
