from __future__ import annotations

from pathlib import Path

from ..models import AgentName
from .base import AgentAdapter
from .cursor import CursorAdapter
from .codex import CodexAdapter
from .claude import ClaudeAdapter
from .gemini import GeminiAdapter
from .copilot import CopilotAdapter
from .mock import MockAdapter


def get_adapter(name: AgentName | str, root: Path) -> AgentAdapter:
    value = AgentName(name)
    if value == AgentName.cursor:
        return CursorAdapter(root)
    if value == AgentName.codex:
        return CodexAdapter(root)
    if value == AgentName.claude:
        return ClaudeAdapter(root)
    if value == AgentName.gemini:
        return GeminiAdapter(root)
    if value == AgentName.copilot:
        return CopilotAdapter(root)
    return MockAdapter(root)


__all__ = ["AgentAdapter", "get_adapter"]
