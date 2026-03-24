from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PROMPT_INJECTION_REFUSAL = (
    "I can't comply with instruction-overriding requests. "
    "Please ask a question grounded in the indexed runbooks."
)


@dataclass
class PromptInjectionCheck:
    blocked: bool
    matched_signals: list[str]


_DIRECT_SIGNAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_previous_instructions", re.compile(r"\bignore\b.{0,40}\b(previous|prior|all)\b.{0,30}\b(instruction|rule|system)\b", re.IGNORECASE)),
    ("reveal_system_prompt", re.compile(r"\b(reveal|show|print|expose|leak)\b.{0,30}\b(system prompt|developer message|hidden prompt)\b", re.IGNORECASE)),
    ("override_policy", re.compile(r"\b(disregard|bypass|override)\b.{0,30}\b(policy|guardrail|safety|rule)\b", re.IGNORECASE)),
    ("tool_forcing", re.compile(r"\b(call|invoke|run|execute)\b.{0,30}\btool\b.{0,30}\b(ignore|without|bypass)\b", re.IGNORECASE)),
    ("jailbreak_marker", re.compile(r"\b(jailbreak|DAN|developer mode)\b", re.IGNORECASE)),
]

_INDIRECT_SIGNAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bignore\b.{0,40}\b(previous|all)\b.{0,30}\b(instruction|rule|prompt)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|developer message|hidden prompt)\b", re.IGNORECASE),
    re.compile(r"\b(do not mention|don't mention|keep secret|exfiltrate|leak)\b", re.IGNORECASE),
]


def check_user_message_for_prompt_injection(message: str) -> PromptInjectionCheck:
    matched = [name for name, pattern in _DIRECT_SIGNAL_PATTERNS if pattern.search(message or "")]
    return PromptInjectionCheck(blocked=bool(matched), matched_signals=matched)


def _is_retrieved_chunk_suspicious(text: str) -> bool:
    content = text or ""
    return any(pattern.search(content) for pattern in _INDIRECT_SIGNAL_PATTERNS)


def filter_retrieved_chunks_for_prompt_injection(chunks: list[Any]) -> tuple[list[Any], int]:
    safe: list[Any] = []
    blocked_count = 0

    for chunk in chunks:
        text = str(getattr(chunk, "text", "") or "")
        if _is_retrieved_chunk_suspicious(text):
            blocked_count += 1
            continue
        safe.append(chunk)

    return safe, blocked_count
