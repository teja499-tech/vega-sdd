"""Task-scoped deterministic checks and compact failure evidence."""
from __future__ import annotations

import re
import shlex
from pathlib import Path

from .models import Feature, SDDConfig, Task

_UNSAFE_PATH_CHARS = set(";&|`$()<>\\\"'\n\r\t")


def compact_output(text: str, limit: int = 2000) -> str:
    """Keep failure snippets; never ship a wall of green pytest dots."""
    raw = (text or "").strip()
    if not raw:
        return ""
    lines = raw.splitlines()
    keep: list[str] = []
    capture = False
    for line in lines:
        marked = bool(re.search(r"(FAILED|ERROR|E\s+|AssertionError|Error:|TypeError|fail)", line))
        if marked:
            capture = True
        if capture or marked:
            keep.append(line)
            if len(keep) >= 80:
                break
            if line.startswith("=") and "failed" in line.lower() and keep:
                break
    if not keep:
        tail = raw[-limit:]
        if re.fullmatch(r"[.sFEx]+", raw.replace("\n", "")):
            return f"{len(raw)} check characters; no failure snippet (likely all passed)."
        return tail
    snippet = "\n".join(keep)
    return snippet[-limit:]


def safe_repo_paths(root: Path, relatives: list[str]) -> list[str]:
    """Return relative paths that resolve inside root. Reject shell metacharacters."""
    root = root.resolve()
    safe: list[str] = []
    for rel in relatives:
        if not rel or not isinstance(rel, str):
            continue
        candidate = Path(rel)
        if candidate.is_absolute() or any(ch in rel for ch in _UNSAFE_PATH_CHARS):
            continue
        if ".." in candidate.parts:
            continue
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        safe.append(candidate.as_posix())
    return safe


def owner_command_argv(command: str | None) -> list[str]:
    """Split a project-owner command. Never interpolate model text into this string."""
    if not command or not command.strip():
        return []
    return shlex.split(command, posix=True)


def scoped_test_argv(root: Path, config: SDDConfig, task: Task) -> list[str] | None:
    argv = owner_command_argv(config.test_command)
    if not argv:
        return None
    paths = safe_repo_paths(root, task.check_paths)
    if paths and any("pytest" in part for part in argv):
        return argv + paths
    return argv


def scoped_test_command(config: SDDConfig, task: Task, root: Path | None = None) -> str | None:
    """Compatibility wrapper. Prefer scoped_test_argv for execution."""
    argv = scoped_test_argv(root or Path("."), config, task)
    return shlex.join(argv) if argv else None


def infer_check_paths(root: Path, task: Task, feature: Feature) -> list[str]:
    declared = safe_repo_paths(root, task.check_paths)
    if declared:
        return declared
    candidates: list[str] = []
    for rel in safe_repo_paths(root, [*task.working_set, *feature.target_files]):
        path = root / rel
        if path.is_file() and ("test" in rel or rel.endswith("_test.py")):
            candidates.append(rel)
    return candidates[:15]


def commands_for_task(root: Path, config: SDDConfig, task: Task) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    test = scoped_test_argv(root, config, task)
    if test:
        rows.append(("test", test))
    lint = owner_command_argv(config.lint_command)
    if lint:
        rows.append(("lint", lint))
    typecheck = owner_command_argv(config.typecheck_command)
    if typecheck:
        rows.append(("typecheck", typecheck))
    return rows
