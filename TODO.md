# TODO

Follow-ups from the role-workflow build (2026-11-05). None blocked the first release. Move them to GitHub issues once the repo has a remote.

## Bugs

- Orca parser: inside `"$( … )"` the quote tracker treats the substitution as a quoted string. A `git commit -m "$(cat <<'EOF' … EOF)"` whose body has an odd number of `"` and a line that is itself an unmodelled launch is refused (fails closed). Treat `$( … )` inside double quotes as unquoted.
- Orca parser: PowerShell backtick plus CRLF continuation, and bash `\` plus CRLF, aren't joined. A modelled launch split over CRLF lines is refused. CRLF heredoc delimiter lines never match.
- Orca parser: fail-open shapes. `(( x = 1 << 2 ))` is read as a heredoc. `<<\EOF` never closes. `<<EOF` or an odd `'` inside a `#` comment hides later lines. `#` inside a word (`issue#12`) acts as a comment (set `lexer.commenters = ""`). `echo "$(orca agent launch …)"` and backtick substitution aren't checked. `nohup`/`time`/`env -i` prefixes aren't skipped.
- Orca parser: flag values or redirections before the subcommand (`orca 2>/dev/null agent launch …`) count as positionals. With PowerShell, an `ORCA_CLI_COMMAND` value containing backslashes isn't normalised.
- Agent definitions: an unclosed frontmatter block returns the body's `key: value` lines. A UTF-8 BOM drops the frontmatter (read with `utf-8-sig`). An inline `# comment` stays in the value. One bad `installed_plugins.json` entry hides that plugin's other install paths.
- Agent definitions: project agents are looked up only at `cwd/.claude/agents`. Also search `$CLAUDE_PROJECT_DIR/.claude/agents`.
- Doctor: every exit code 1 is reported as "Python not found", including timeouts, a missing bash, or crashes. The worst case (5 × 30 s) exceeds the Bash tool's 120 s timeout. If the user has a `general-purpose.md` with a model, the Agent-hook probe reports a false FAIL.
- Doctor: the "shadow" check tells anyone with their own `implementer.md`/`reviewer.md` to delete it. Reword it, or report INFO when the file differs from the plugin's copy.

## Improvements

- Windows: also try the `py -3` launcher in `hooks/run-python`.
- `/hierarchy-doctor`: it needs a Bash approval, and in `-p` mode it is refused. Consider dropping `--cwd "$PWD"` and adding a narrow `allowed-tools`. Confirm that `${CLAUDE_PLUGIN_ROOT}` is substituted in the command body.
- An unknown CLI subcommand is silent. Add a stderr line.
- GUIDANCE: the review "why" line is muddled.
- README: the doctor output it quotes doesn't match the real text. Soften "always pass `--model`". Frame the migration note for anyone with same-named agents.
- Tests:
  - `test_launcher_writes_no_bytecode` should assert that the launcher ran.
  - Add a test through `run-hook.cmd`.
  - Assert the `hooks.json` command strings and SessionStart matcher.
  - Strengthen the deny assertions.
  - Cover: whitespace-only model; a bare-name agent with a model; recursive agent dirs; non-UTF-8 files; plugin prefix collision; a found agent with no model shadowing a later one; doctor paths for a wrong-model agent and missing matchers; an allowed test for a quoted newline whose second line looks like a launch.
- Manifests: add trailing newlines.

## Field trial checklist (install from the marketplace, use inside Orca on one project)

- An unmodelled `worker-start` through the Bash tool is refused. On Windows, try the same through the PowerShell tool; this proves the tool name and the stdin path.
- An Agent call with `general-purpose` and no model is refused. A `role-workflow:reviewer` dispatch runs on Opus.
- Check whether the Agent tool accepts `model: "inherit"` at all.
- Record the real Windows value of `ORCA_CLI_COMMAND` (`.exe`, `.cmd` shim?).
- Check `/hierarchy-doctor`'s permission behaviour.
- Delete `~/.claude/agents/implementer.md` and `reviewer.md`, then confirm the doctor goes green.
