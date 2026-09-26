from __future__ import annotations

import json
import os
import shutil
import subprocess
import signal
from threading import Thread,Timer
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Iterable

from ..models import AgentCapabilities, AgentEvent, AgentResult

EventCallback = Callable[[AgentEvent], None]


class AgentAdapter(ABC):
    name: str

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._active: subprocess.Popen[str] | None = None

    @abstractmethod
    def capabilities(self) -> AgentCapabilities:
        raise NotImplementedError

    @abstractmethod
    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        raise NotImplementedError

    def run(
        self,
        prompt: str,
        *,
        writable: bool = False,
        mode: str = "agent",
        on_event: EventCallback | None = None,
        env: dict[str, str] | None = None,
    ) -> AgentResult:
        cmd = self.build_command(prompt, writable=writable, mode=mode)
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        try:
            self._active = subprocess.Popen(
                cmd,
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=merged_env,
                start_new_session=(os.name != "nt"),
            )
        except FileNotFoundError:
            return AgentResult(success=False, text=f"Agent command not found: {cmd[0]}", exit_code=127)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        assert self._active.stdout is not None
        assert self._active.stderr is not None
        process = self._active
        timed_out=[]
        def timeout_run():
            timed_out.append(True);self.interrupt()
        timer=Timer(getattr(self,'timeout_seconds',1800),timeout_run)
        timer.daemon=True;timer.start()
        def drain_stderr():
            stderr_lines.extend(process.stderr.readlines())
        reader = Thread(target=drain_stderr, daemon=True)
        reader.start()
        try:
            for line in process.stdout:
                stdout_lines.append(line)
                event = self.parse_event(line)
                if event and on_event:
                    on_event(event)
            code = process.wait()
            reader.join(timeout=5)
        except BaseException:
            timer.cancel()
            self.interrupt()
            reader.join(timeout=5)
            raise
        timer.cancel()
        self._active = None
        text = self.final_text(stdout_lines)
        if code != 0 and stderr_lines:
            text = (text + "\n" + "".join(stderr_lines)).strip()
        return AgentResult(
            success=not timed_out and code == 0 and not any(
                e.payload.get("is_error") is True or e.type in {"error", "turn.failed"}
                for line in stdout_lines if (e := self.parse_event(line))
            ),
            text=("Agent timed out. " + text) if timed_out else text,
            events=[e for line in stdout_lines if (e := self.parse_event(line))],
            exit_code=code,
            raw={"stdout": stdout_lines, "stderr": stderr_lines, "command": cmd[:-1] + ["<prompt>"]},
        )

    def parse_event(self, line: str) -> AgentEvent | None:
        stripped = line.strip()
        if not stripped:
            return None
        try:
            obj = json.loads(stripped)
            if not isinstance(obj, dict):
                return AgentEvent(type="agent_output", message=stripped)
            msg = self._event_message(obj)
            return AgentEvent(type=str(obj.get("type", "agent_event")), message=msg, payload=obj)
        except json.JSONDecodeError:
            return AgentEvent(type="agent_output", message=stripped)

    def _event_message(self, obj: dict) -> str:
        for key in ("message", "text", "content", "result"):
            value = obj.get(key)
            if isinstance(value, str):
                return value
        item = obj.get("item")
        if isinstance(item, dict):
            for key in ("text", "command", "type"):
                value = item.get(key)
                if isinstance(value, str):
                    return value
        return str(obj.get("type", "event"))

    def final_text(self, lines: list[str]) -> str:
        # Most adapters override this. Generic mode preserves stdout.
        return "".join(lines).strip()

    def interrupt(self) -> bool:
        proc = self._active
        if not proc or proc.poll() is not None:
            return False
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait(timeout=5)
        self._active = None
        return True

    def installed_version(self, command: str, args: list[str] | None = None) -> str | None:
        if not shutil.which(command):
            return None
        try:
            completed = subprocess.run(
                [command, *(args or ["--version"])],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = (completed.stdout or completed.stderr).strip()
            return output.splitlines()[0] if output else "installed"
        except Exception:
            return "installed"
