from __future__ import annotations

import subprocess
from pathlib import Path


def summarize_repository(root: Path, max_files: int = 200) -> str:
    """Produce lightweight deterministic repository context without needing an LLM."""
    ignored = {".git", ".sdd", ".venv", "node_modules", "dist", "build", "__pycache__"}
    files: list[str] = []
    for path in root.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            try:
                files.append(str(path.relative_to(root)))
            except ValueError:
                continue
            if len(files) >= max_files:
                break
    git = ""
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, timeout=5)
        status = subprocess.run(["git", "status", "--short"], cwd=root, capture_output=True, text=True, timeout=5)
        git = f"Git branch: {branch.stdout.strip() or 'unknown'}\nWorking tree:\n{status.stdout.strip() or 'clean'}"
    except Exception:
        git = "Git context unavailable."
    return git + "\n\nRepository files (sample):\n" + "\n".join(f"- {f}" for f in files)
