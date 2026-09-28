from __future__ import annotations

import hashlib
import shutil
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

EVIDENCE_CHARS = 360
MAX_EVIDENCE = 10
_VIEW_MAX_FILES = 10_000
_VIEW_MAX_BYTES = 128 * 1024 * 1024
_VIEW_MAX_FILE_BYTES = 4 * 1024 * 1024
_INSTRUCTION_ROOTS = {".agents", ".codex", ".claude", ".cursor", ".git", ".sdd"}
_INSTRUCTION_FILES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
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


def materialize_repository_view(source: Path, target: Path) -> str:
    """Copy a bounded source view without pre-approval agent instructions or secrets."""
    completed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=source, capture_output=True,
    )
    if completed.returncode:
        names = [p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()]
    else:
        names = [name for name in completed.stdout.decode().split("\0") if name]
    copied = omitted = total = 0
    for rel in sorted(set(names), key=_priority):
        path = Path(rel)
        lower_name = path.name.lower()
        if (
            not path.parts
            or path.parts[0] in _INSTRUCTION_ROOTS
            or rel in _INSTRUCTION_FILES
            or path.name in {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}
            or rel.startswith(".github/instructions/")
            or lower_name == ".env" or lower_name.startswith(".env.")
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        ):
            omitted += 1
            continue
        src = source / path
        if not src.is_file() or src.is_symlink():
            omitted += 1
            continue
        size = src.stat().st_size
        if size > _VIEW_MAX_FILE_BYTES or copied >= _VIEW_MAX_FILES or total + size > _VIEW_MAX_BYTES:
            omitted += 1
            continue
        dest = target / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
        total += size
    return f"Isolated source view: {copied} files / {total} bytes copied; {omitted} instruction, secret, symlink, or over-budget files omitted."


def _excerpt(root: Path, rel: str) -> str | None:
    path = root / rel
    try:
        data = path.read_bytes()
    except OSError:
        return None
    digest = hashlib.sha256(data).hexdigest()[:16]
    if len(data) > 200_000:
        return f"### {rel}\nsha256={digest} omitted as too large ({len(data)} bytes)"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return f"### {rel}\nsha256={digest} binary {len(data)} bytes"
    return f"### {rel}\nsha256={digest} ({len(text)} chars)\n{text[:EVIDENCE_CHARS]}"


def summarize_repository(root: Path, max_files: int = 200) -> str:
    """Deterministic brownfield pack: excerpts from evidence, then a bounded file list."""
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
    graph_query = ""
    try:
        from .graphify_index import query_knowledge_graph
        graph_query = query_knowledge_graph(root, "architecture requirements entrypoints")
    except Exception:
        graph_query = ""
    evidence = [rel for rel in selected if _priority(rel)[0] <= 2][:MAX_EVIDENCE]
    excerpts: list[str] = []
    omitted_evidence: list[str] = []
    for rel in evidence:
        text = _excerpt(root, rel)
        if text:
            excerpts.append(text)
        else:
            omitted_evidence.append(rel)
    lines = [
        git,
        "",
        graph_note,
        "",
        "Pre-init Graphify query:",
        graph_query or "No graph/corpus hit. Do not invent architecture from filenames alone.",
        "",
        "Evidence excerpts (size-capped; omitted paths are unresolved boundaries):",
        *excerpts,
    ]
    if omitted_evidence:
        lines += ["", "Unreadable or oversized evidence:", *[f"- {name}" for name in omitted_evidence]]
    lines += [
        "",
        "Priority inventory (manifests, entrypoints, architecture/infra first):",
        *[f"- {name}" for name in selected],
    ]
    if len(files) > max_files:
        lines.append(
            f"- … {len(files) - max_files} additional files omitted. "
            "Treat omitted paths as explicit questions, not inferred architecture."
        )
    return "\n".join(lines)
