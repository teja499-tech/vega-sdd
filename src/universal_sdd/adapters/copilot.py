from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path

from .base import AgentAdapter, unrestricted_agent_allowed
from ..models import AgentCapabilities


_SAFE_EXE = re.compile(r"^[A-Za-z0-9._+-]+$")
_INTERPRETERS = {
    "python",
    "python3",
    "node",
    "nodejs",
    "bash",
    "sh",
    "zsh",
    "dash",
    "fish",
    "ruby",
    "perl",
    "pwsh",
    "powershell",
    "cmd",
    "osascript",
    "deno",
    "lua",
    "php",
}
_PACKAGE_RUNNERS = {"npm", "npx", "pnpm", "yarn", "bun", "cargo", "go"}


def _is_interpreter(exe: str) -> bool:
    lowered = exe.lower()
    if lowered in _INTERPRETERS:
        return True
    return bool(re.fullmatch(r"python\d+(\.\d+)*", lowered))


def copilot_shell_spec(argv: list[str] | None) -> str | None:
    """Exact command prefix only. Never grant a bare interpreter or generic shell."""
    if not argv:
        return None
    for part in argv:
        if not part or any(ch in part for ch in ";|&`$()<>\\\"'\n\r"):
            return None
    exe = Path(argv[0]).name
    if not exe or not _SAFE_EXE.fullmatch(exe):
        return None
    rest = argv[1:]
    if _is_interpreter(exe):
        if not rest or rest[0] in {"-c", "-e", "-", "--"}:
            return None
        prefix = [exe]
        if rest[0] == "-m" and len(rest) >= 2:
            if rest[1] in {"base64", "http.server", "code"}:
                return None
            prefix.extend(["-m", rest[1]])
        elif rest[0].startswith("-"):
            return None
        else:
            prefix.append(Path(rest[0]).name)
        return "shell(" + " ".join(prefix) + ":*)"
    if exe.lower() in _PACKAGE_RUNNERS:
        if len(rest) < 1:
            return None
        kept = [exe, *rest[:2]] if rest[0] in {"run", "exec", "test"} else [exe, rest[0]]
        return "shell(" + " ".join(kept) + ":*)"
    if rest and not rest[0].startswith("-"):
        return f"shell({exe} {rest[0]}:*)"
    return f"shell({exe}:*)"


def approved_copilot_tools(root: Path) -> list[str]:
    """Write plus scoped check prefixes from the approved project policy."""
    tools = ["write"]
    seen = {"write"}

    def add_shell(argv: list[str] | None) -> None:
        token = copilot_shell_spec(argv)
        if not token or token in seen:
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
                "Restricted writable runs allow write plus command-prefix shell specs from the approved policy.",
                "Bare interpreters and generic shell are not granted. The controller rechecks regardless.",
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
