from __future__ import annotations

import json
import shutil

from .base import AgentAdapter
from ..models import AgentCapabilities


class CodexAdapter(AgentAdapter):
    name = "codex"

    def capabilities(self) -> AgentCapabilities:
        installed = shutil.which("codex") is not None
        version = self.installed_version("codex") if installed else None
        return AgentCapabilities(
            installed=installed,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=True,
            interrupt=True,
            command="codex",
            version=version,
            notes=[
                "Uses `codex exec --json` for bounded SDD tasks.",
                "Writable runs use --full-auto; read-only runs rely on Codex's default restricted sandbox.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["codex", "exec", "--json", "--sandbox", "workspace-write" if writable else "read-only"]
        cmd.append(prompt)
        return cmd

    def final_text(self, lines: list[str]) -> str:
        final_candidates: list[str] = []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = obj.get("item")
            if isinstance(item, dict):
                for key in ("text", "content", "message"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        final_candidates.append(value)
            for key in ("result", "text", "message", "content"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    final_candidates.append(value)
        return final_candidates[-1] if final_candidates else "".join(lines).strip()
