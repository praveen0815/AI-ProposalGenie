"""Provider-neutral generation results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    usage: TokenUsage | None
