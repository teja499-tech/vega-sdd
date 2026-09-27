from __future__ import annotations

import shutil

from .base import AgentAdapter
from ..models import AgentCapabilities


class CopilotAdapter(AgentAdapter):
    name = "copilot"

    def capabilities(self) -> AgentCapabilities:
        installed = shutil.which("copilot") is not None
        version = self.installed_version("copilot") if installed else None
        return AgentCapabilities(
            installed=installed,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=False,
            interrupt=True,
            command="copilot",
            version=version,
            notes=[
                "Uses GitHub Copilot CLI `-p` prompt mode with --silent.",
                "Writable runs pass --allow-all; read-only review omits write approvals.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["copilot", "-p", prompt, "--silent"]
        if writable:
            cmd.append("--allow-all")
        return cmd
