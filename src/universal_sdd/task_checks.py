"""Task-scoped deterministic checks and compact failure evidence."""
from __future__ import annotations

import re
from pathlib import Path

from .models import Feature, SDDConfig, Task


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


def scoped_test_command(config: SDDConfig, task: Task) -> str | None:
    if task.check_command:
        return task.check_command
    command = config.test_command
    if not command:
        return None
    paths = [p for p in task.check_paths if p and ".." not in p]
    if paths and "pytest" in command:
        return f"{command} {' '.join(paths)}"
    return command


def infer_check_paths(root: Path, task: Task, feature: Feature) -> list[str]:
    if task.check_paths:
        return [p for p in task.check_paths if p and ".." not in p]
    candidates: list[str] = []
    for rel in [*task.working_set, *feature.target_files]:
        if not rel or ".." in rel:
            continue
        path = root / rel
        if path.is_file() and ("test" in rel or rel.endswith("_test.py")):
            candidates.append(rel)
    return candidates[:15]


def commands_for_task(config: SDDConfig, task: Task) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    test = scoped_test_command(config, task)
    if test:
        rows.append(("test", test))
    if config.lint_command:
        rows.append(("lint", config.lint_command))
    if config.typecheck_command:
        rows.append(("typecheck", config.typecheck_command))
    return rows
