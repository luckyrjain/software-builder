from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    skill: str
    case_id: str
    passed: bool
    messages: list[str]
