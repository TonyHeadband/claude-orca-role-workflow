# Agent hierarchy plugin — project brief

Status: idea, not started · 2026-11-04

## Why

Multi-agent work (Orca workers, subagents) currently picks models by accident. On 2026-11-04, every Orca build worker for part D of rpg-house-party ran on **Opus at high effort**, because that was Orca's default for new Claude chats. That burned 57% of a 5-hour usage window in about 3 hours. The goal is a role hierarchy that holds by configuration, not by the coordinator remembering a flag:

- **Opus** for brainstorming, specs, plans and coordination (the chats the user opens).
- **Sonnet** for implementation (Orca workers and in-session builders).
- **Opus** for reviews (per task or lane), plus one final whole-branch review.

## What it is

A Claude Code plugin, in its own Forgejo repo with a marketplace entry, that sets up the four layers in one install and removes them in one uninstall:

| Layer | Plugin piece | Strength |
|---|---|---|
| 1. Chat model for brainstorming | `/hierarchy-doctor` command: reads Orca's saved default read-only and reports it. It does not change it | the user's setting, checked |
| 2. Pre-tool hook | `hooks/hooks.json` + script: `PreToolUse` on `Bash`; blocks `orca orchestration worker-start`, `orca worktree create … --agent`, `orca agent launch` and `orca-ide`/`orca-dev` equivalents when they have no `--model`, with a message saying to add one | hard |
| 3. Role definitions | `agents/implementer.md` (Sonnet, medium, edit tools, TDD, fixed report) and `agents/reviewer.md` (Opus, high, read-only, ranked findings plus verdict) | hard for those roles |
| 4. Direction | a `SessionStart` hook injecting a short "which role for which step" text as additional context, instead of editing CLAUDE.md | guidance |

## Facts already established (Orca 1.4.248, Linux)

- **Workers are not sandboxed.** They run the real `claude` binary with the user's real home folder and `--setting-sources=user,project,local`, so user plugins, agents, skills and CLAUDE.md all reach them.
- **Orca passes `--model <x> --effort <y>` on every launch.** The values come from its chat default, so they beat `model` in `~/.claude/settings.json`. The default is stored in `~/.config/orca/profiles/local-default/profile-state.db`, table `profile_state_documents`, domain `settings`, keys `nativeChatSessionOptions.claude.model` and `….valuesByModel.<model>.effort`. Don't write it while Orca runs.
- **`--model` / `--effort` work per launch** on `worker-start`, `agent launch` and `worktree create --agent`. Orca has no per-role setting.
- **The CLI path** is `$ORCA_CLI_COMMAND` inside Orca sessions. Never run bare `orca` on Linux outside Orca terminals: it starts the GNOME screen reader.
- **Two agents already exist** in `~/.claude/agents/` (`implementer.md`, `reviewer.md`). Move them into the plugin and delete the originals so they aren't duplicated. Existing user agents (`follow-up`, `finalize-branch`, `mdx-creator`) stay where they are.

## Decisions for the brainstorm

- Name and repo location (Forgejo, under the user's account); marketplace setup.
- Should the hook only block, or should it rewrite the command to add `--model sonnet` (newer `PreToolUse` supports `updatedInput`)? Can it tell builder launches from review launches (task title or spec text), or should it stay "must be explicit"?
- Should it also block untyped or `general-purpose` subagent calls (`PreToolUse` on the Agent tool)? That was 93% of a week's subagent usage.
- How skills that choose their own subagent models (superpowers' subagent-driven-development) are steered to `implementer`/`reviewer`: the injected text, or a hook.
- Whether the role text and models are configurable (a plugin settings file) or fixed.

## Out of scope

Changing Orca itself; editing Orca's database; a per-role Orca feature (file it with the Orca developers instead).

## Done when

- One `/plugin install` gives the agents, the hook and the injected guidance, and `/hierarchy-doctor` reports all four layers green.
- An Orca `worker-start` without `--model` is refused.
- A review dispatched from any session runs on Opus.
- Uninstalling leaves no trace.
- Tests cover the hook's command parsing: launch forms, quoting, `--model=` vs `--model x`, and commands that only mention orca.
