from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import AgentAdapter, unrestricted_agent_allowed
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
        cmd = [
            caps.command,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--workspace",
            str(self.root),
            "--trust",
            "--model",
            "auto",
        ]
        # --trust confirms the workspace. --force is unrestricted command/write
        # approval and requires an explicit owner opt-in.
        if writable and mode != "plan" and unrestricted_agent_allowed(self.root):
            cmd.append("--force")
        if mode == "plan" or not writable:
            cmd += ["--mode", "plan" if mode == "plan" else "ask"]
        return cmd

    def run(self, prompt: str, *, writable: bool = False, mode: str = "agent", on_event=None, env=None):
        # ~/.zshrc often has `eval "$(agent shell-integration zsh)"`, which
        # execs `agent record` unless CURSOR_RECORD_SESSION is already set.
        # Cursor's tool shells are login zsh (`zsh -il`); without this, a
        # writable SDD run deadlocks on a nested agent session.
        merged = {"CURSOR_RECORD_SESSION": "1"}
        if env:
            merged.update(env)
        return super().run(prompt, writable=writable, mode=mode, on_event=on_event, env=merged)

    def final_text(self, lines: list[str]) -> str:
        text = "".join(lines).strip()
        if not text:
            return text

        def _unwrap(obj):
            if isinstance(obj, dict):
                for key in ("result", "text", "message", "content"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                    if isinstance(value, (dict, list)):
                        return json.dumps(value)
                # Cursor print-mode envelopes sometimes nest payloads, e.g.
                # {"type": "result", "result": {...}} or {"output": {...}}.
                for key in ("output", "data", "payload"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
                    if isinstance(value, (dict, list)):
                        return json.dumps(value)
            return None

        try:
            obj = json.loads(text)
            unwrapped = _unwrap(obj)
            if unwrapped is not None:
                return unwrapped
            # Whole-document JSON without a wrapper is itself the payload.
            if isinstance(obj, (dict, list)):
                return json.dumps(obj) if not isinstance(obj, str) else obj
        except Exception:
            pass

        # Fallback: scan lines for the last JSON object containing a result
        # payload. This handles pretty-printed blobs plus trailing logs.
        last_candidate = None
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                obj = json.loads(stripped)
            except Exception:
                continue
            unwrapped = _unwrap(obj)
            if unwrapped is not None:
                last_candidate = unwrapped
        if last_candidate is not None:
            return last_candidate
        return text
