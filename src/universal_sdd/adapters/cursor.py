from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import AgentAdapter
from ..models import AgentCapabilities


class CursorAdapter(AgentAdapter):
    name = "cursor"

    def capabilities(self) -> AgentCapabilities:
        installed = shutil.which("agent") is not None or shutil.which("cursor-agent") is not None
        command = "agent" if shutil.which("agent") else "cursor-agent"
        version = self.installed_version(command) if installed else None
        return AgentCapabilities(
            installed=installed,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=True,
            interrupt=True,
            command=command,
            version=version,
            notes=["Uses Cursor CLI print mode for SDD-controlled runs."],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        caps = self.capabilities()
        cmd = [caps.command, "-p", prompt, "--output-format", "json", "--workspace", str(self.root)]
        if mode == "plan" or not writable:
            cmd += ["--mode", "plan" if mode == "plan" else "ask"]
        return cmd

    def final_text(self, lines: list[str]) -> str:
        text = "".join(lines).strip()
        try:
            obj = json.loads(text)
            for key in ("result", "text", "message", "content"):
                if isinstance(obj.get(key), str):
                    return obj[key]
        except Exception:
            pass
        return text
