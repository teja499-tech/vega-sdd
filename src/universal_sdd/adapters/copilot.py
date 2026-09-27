from __future__ import annotations

import shutil

from .base import AgentAdapter, unrestricted_agent_allowed
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
                "Writable runs pass --allow-all only when allow_unrestricted_agent is set.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["copilot", "-p", prompt, "--silent"]
        if writable and unrestricted_agent_allowed(self.root):
            cmd.append("--allow-all")
        return cmd
