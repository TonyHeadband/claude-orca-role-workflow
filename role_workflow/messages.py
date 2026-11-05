def orca_refusal(launch: str) -> str:
    return (
        f"`{launch}` launches a Claude agent without an explicit model. "
        "Add `--model sonnet` for building or `--model opus` for reviewing or coordinating. "
        "Without it, Orca applies your chat default, which may be Opus at high effort, "
        "to every worker."
    )


def agent_refusal(subagent_type: str | None) -> str:
    called = f"`{subagent_type}`" if subagent_type else "An untyped subagent"
    return (
        f"{called} was called without an explicit model. "
        "Use `role-workflow:implementer` for building (Sonnet) or "
        "`role-workflow:reviewer` for reviewing (Opus), "
        "or pass `model` explicitly: `opus` for research or exploration, "
        "`haiku` for plain string or file searches. "
        "Without a model, the subagent inherits this chat's model."
    )


GUIDANCE = """\
role-workflow: keep each kind of work on the model that suits it.
- You (this session's model) plan and coordinate; that is the work that needs your judgment.
- Build with `role-workflow:implementer`, or with Orca workers launched with `--model sonnet`; Sonnet is cheaper and fast enough for well-specified code.
- Review with `role-workflow:reviewer`, or with Orca workers launched with `--model opus`, then run one final whole-branch review; Opus catches what per-task reviews miss, and the final pass catches cross-task problems.
- For research or exploration pass `model: opus`; it needs depth, not speed.
- For plain string or file searches pass `model: haiku`; it is the cheapest model that can do the job.
- Do not override a role agent's model; the model is the point of the role.
- Subagent calls and Orca launches without an explicit model are refused; otherwise they silently inherit this chat's model and effort.
- If you use superpowers' subagent-driven-development, dispatch `role-workflow:implementer`/`role-workflow:reviewer` for its implementer/reviewer steps; that keeps its workflow on the right models.
"""
