from __future__ import annotations

import subprocess
from pathlib import Path


PRIORITY_NAMES = {
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.toml",
    "go.mod",
    "go.sum",
    "composer.json",
    "gemfile",
    "podfile",
    "dockerfile",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "makefile",
    "readme.md",
    "agents.md",
    "requirements.txt",
    "poetry.lock",
    "pipfile",
    "tsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "vite.config.ts",
    "manage.py",
    "main.py",
    "app.py",
    "index.ts",
    "index.js",
    "main.go",
    "main.rs",
}

PRIORITY_DIRS = {
    "src",
    "app",
    "apps",
    "cmd",
    "pkg",
    "lib",
    "server",
    "backend",
    "frontend",
    "infra",
    "terraform",
    "deploy",
    "migrations",
    "docs",
    "architecture",
}


def _priority(rel: str) -> tuple[int, str]:
    path = Path(rel)
    name = path.name.lower()
    if name in PRIORITY_NAMES or name.startswith("dockerfile"):
        return (0, rel)
    if any(part.lower() in PRIORITY_DIRS for part in path.parts[:-1]):
        return (1, rel)
    if path.suffix.lower() in {".toml", ".yml", ".yaml", ".json", ".tf", ".sql"}:
        return (2, rel)
    return (3, rel)


def summarize_repository(root: Path, max_files: int = 200) -> str:
    """Deterministic brownfield pack: manifests, entrypoints, then a bounded file list."""
    ignored = {".git", ".sdd", ".venv", "node_modules", "dist", "build", "__pycache__", "graphify-out"}
    files: list[str] = []
    for path in root.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            try:
                files.append(str(path.relative_to(root)))
            except ValueError:
                continue
    files.sort(key=_priority)
    selected = files[:max_files]
    git = ""
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, timeout=5)
        status = subprocess.run(["git", "status", "--short"], cwd=root, capture_output=True, text=True, timeout=5)
        git = f"Git branch: {branch.stdout.strip() or 'unknown'}\nWorking tree:\n{status.stdout.strip() or 'clean'}"
    except Exception:
        git = "Git context unavailable."
    graph = root / "graphify-out" / "graph.json"
    graph_note = (
        "Graphify graph: present. Query it before inventing architecture."
        if graph.exists()
        else "Graphify graph: not built. Run `sdd graph refresh` after installing graphify."
    )
    lines = [
        git,
        "",
        graph_note,
        "",
        "Priority evidence (manifests, entrypoints, architecture/infra first):",
        *[f"- {name}" for name in selected],
    ]
    if len(files) > max_files:
        lines.append(f"- … {len(files) - max_files} additional files omitted")
    return "\n".join(lines)
