def orca_refusal(launch: str) -> str:
    return (
        f"`{launch}` launches a Claude agent without an explicit model. "
        "Add `--model sonnet` for building or `--model opus` for reviewing or coordinating. "
        "Without it, Orca applies your chat default, which may be Opus at high effort, "
        "to every worker."
    )
