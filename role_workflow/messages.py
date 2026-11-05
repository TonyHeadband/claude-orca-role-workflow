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
