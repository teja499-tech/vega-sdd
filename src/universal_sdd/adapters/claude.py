from __future__ import annotations

import json
import shutil

from .base import AgentAdapter
from ..models import AgentCapabilities


class ClaudeAdapter(AgentAdapter):
    name = "claude"

    def capabilities(self) -> AgentCapabilities:
        installed = shutil.which("claude") is not None
        version = self.installed_version("claude") if installed else None
        return AgentCapabilities(
            installed=installed,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=True,
            interrupt=True,
            command="claude",
            version=version,
            notes=[
                "Uses Claude Code print mode with stream-json output.",
                "CLI flags can be overridden in a future adapter config if local Claude Code differs.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]
        if writable:
            cmd += ["--permission-mode", "acceptEdits"]
        else:
            cmd += ["--permission-mode", "plan"]
        return cmd

    def final_text(self, lines: list[str]) -> str:
        candidates: list[str] = []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "result" and isinstance(obj.get("result"), str):
                candidates.append(obj["result"])
            message = obj.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            candidates.append(part["text"])
        return candidates[-1] if candidates else "".join(lines).strip()
