from __future__ import annotations

import shutil

from .base import AgentAdapter, unrestricted_agent_allowed
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
                "Restricted writable runs use --sandbox --approval-mode auto_edit.",
                "Writable runs add --yolo only when allow_unrestricted_agent is set.",
                "Read-only review/ask uses --sandbox when the local CLI supports it.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["gemini", "-p", prompt]
        if writable and unrestricted_agent_allowed(self.root):
            cmd.append("--yolo")
        elif writable:
            cmd.extend(["--sandbox", "--approval-mode", "auto_edit"])
        else:
            cmd.append("--sandbox")
        return cmd
