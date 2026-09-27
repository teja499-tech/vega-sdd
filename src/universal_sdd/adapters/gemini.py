from __future__ import annotations

import shutil

from .base import AgentAdapter
from ..models import AgentCapabilities


class GeminiAdapter(AgentAdapter):
    name = "gemini"

    def capabilities(self) -> AgentCapabilities:
        installed = shutil.which("gemini") is not None
        version = self.installed_version("gemini") if installed else None
        return AgentCapabilities(
            installed=installed,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=False,
            interrupt=True,
            command="gemini",
            version=version,
            notes=[
                "Uses Gemini CLI one-shot `-p` prompt mode.",
                "Writable runs enable --yolo so SDD is not blocked on TTY approvals.",
                "Read-only review/ask uses --sandbox when the local CLI supports it.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["gemini", "-p", prompt]
        if writable:
            cmd.append("--yolo")
        else:
            cmd.append("--sandbox")
        return cmd
