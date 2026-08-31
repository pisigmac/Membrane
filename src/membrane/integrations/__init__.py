"""Thin helpers so existing agents can inject Membrane memory into prompts."""

from membrane.integrations.agents import (
    cursor_rule_snippet,
    fetch_memory_block,
    inject_system_memory,
)

__all__ = [
    "cursor_rule_snippet",
    "fetch_memory_block",
    "inject_system_memory",
]
