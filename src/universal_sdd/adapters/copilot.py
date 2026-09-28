from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path

from .base import AgentAdapter, unrestricted_agent_allowed
from ..models import AgentCapabilities


_SAFE_EXE = re.compile(r"^[A-Za-z0-9._+-]+$")


def approved_copilot_tools(root: Path) -> list[str]:
    """Read/write plus scoped check executables from the approved project policy."""
    tools = ["write"]
    seen = {"write"}

    def add_shell(argv: list[str] | None) -> None:
        if not argv:
            return
        exe = Path(argv[0]).name
        if not exe or not _SAFE_EXE.fullmatch(exe):
            return
        token = f"shell({exe})"
        if token in seen:
            return
        seen.add(token)
        tools.append(token)

    try:
        from ..storage import SDDPaths, load_config
        config = load_config(SDDPaths(root))
        for command in (config.test_command, config.lint_command, config.typecheck_command):
            if command:
                add_shell(shlex.split(command, posix=True))
    except Exception:
        pass
    try:
        from ..workspace import load_workspace, policy_path
        if policy_path(root).exists():
            workspace = load_workspace(root)
            for component in workspace.components:
                for check in component.checks.values():
                    add_shell(check.argv)
                if component.build:
                    add_shell(component.build.argv)
    except Exception:
        pass
    return tools


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
                "Uses GitHub Copilot CLI `-p` prompt mode with --silent --no-ask-user.",
                "Restricted writable runs allow write plus scoped shell(<check-exe>) from the approved policy.",
                "Generic shell is not granted. The controller rechecks regardless.",
                "Writable runs pass --allow-all only when allow_unrestricted_agent is set.",
            ],
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        cmd = ["copilot", "-p", prompt, "--silent", "--no-ask-user"]
        if writable and unrestricted_agent_allowed(self.root):
            cmd.append("--allow-all")
        elif writable:
            for tool in approved_copilot_tools(self.root):
                cmd.extend(["--allow-tool", tool])
        return cmd
