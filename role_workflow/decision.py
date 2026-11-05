from dataclasses import dataclass


@dataclass(frozen=True)
class Refusal:
    reason: str
