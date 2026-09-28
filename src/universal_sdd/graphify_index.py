"""Graphify owns the code graph. Vega searches the traceability corpus separately and merges hits."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .storage import SDDPaths, load_yaml


CORPUS_DIR = "graphify-corpus"
CORPUS_FILE = "sdd-traceability.md"


def graphify_installed() -> bool:
    return shutil.which("graphify") is not None


def corpus_path(root: Path) -> Path:
    return root / CORPUS_DIR / CORPUS_FILE


def graph_json(root: Path) -> Path:
    return root / "graphify-out" / "graph.json"


def write_trace_corpus(paths: SDDPaths) -> Path:
    """Markdown Vega searches deterministically. Graphify extract is code-only."""
    requirements = load_yaml(paths.requirements_file, []) or []
    features = load_yaml(paths.features_file, []) or []
    decisions = load_yaml(paths.architecture_decisions_file, []) or []
    lines = [
        "# SDD traceability corpus",
        "",
        "Generated for Graphify. Canonical execution state remains under `.sdd/state/`.",
        "Query with `graphify query`, `graphify path`, or `graphify explain` before reading the repository.",
        "",
    ]
    lines.append("## Architecture decisions")
    for decision in decisions:
        if not isinstance(decision, dict) or not decision.get("id"):
            continue
        lines.append(
            f"- {decision['id']} ({decision.get('status', 'open')}): {decision.get('question', '')} "
            f"Selected: {decision.get('selected') or 'undecided'}. "
            f"Requirements: {', '.join(decision.get('requirements') or []) or 'none'}."
        )
    lines += ["", "## Requirements"]
    for req in requirements:
        if not isinstance(req, dict) or not req.get("id"):
            continue
        criteria = "; ".join(req.get("acceptance_criteria") or [])
        lines.append(f"- {req['id']}: {req.get('title', '')}. {req.get('statement', '')} Acceptance: {criteria}")
    lines += ["", "## Features and tasks"]
    for feature in features:
        if not isinstance(feature, dict) or not feature.get("id"):
            continue
        lines.append(
            f"### {feature['id']} {feature.get('name', '')}",
            )
        lines.append(feature.get("summary") or "")
        lines.append(f"Requirements: {', '.join(feature.get('requirements') or []) or 'none'}.")
        lines.append(f"Depends on: {', '.join(feature.get('depends_on') or []) or 'none'}.")
        if feature.get("target_files"):
            lines.append("Target files: " + ", ".join(feature["target_files"]))
        for task in feature.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            lines.append(
                f"- {task.get('id')}: {task.get('title', '')} ({task.get('status', 'pending')}). "
                f"Implements {', '.join(task.get('implements') or []) or 'none'}. "
                f"Verification: {'; '.join(task.get('verification') or []) or 'none'}."
            )
        lines.append("")
    target = corpus_path(paths.root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def run_graphify(root: Path, args: list[str], *, timeout: int) -> tuple[int, str]:
    if not graphify_installed():
        return 127, "graphify CLI is not installed. Install Graphify-Labs/graphify and re-run `sdd graph refresh`."
    try:
        completed = subprocess.run(
            ["graphify", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"graphify {' '.join(args)} exceeded {timeout}s"
    except OSError as exc:
        return 127, str(exc)
    return completed.returncode, ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()


def refresh_knowledge_graph(paths: SDDPaths, *, timeout: int = 600) -> dict:
    corpus = write_trace_corpus(paths)
    if not graphify_installed():
        return {"installed": False, "corpus": str(corpus.relative_to(paths.root)), "exit_code": 127, "output": "graphify not installed"}
    # extract --code-only is local AST. update refreshes code without an LLM pass.
    if graph_json(paths.root).exists():
        args = ["update", str(paths.root)]
    else:
        args = ["extract", str(paths.root), "--code-only", "--no-cluster"]
    code, output = run_graphify(paths.root, args, timeout=timeout)
    return {
        "installed": True,
        "corpus": str(corpus.relative_to(paths.root)),
        "command": "graphify " + " ".join(args),
        "exit_code": code,
        "graph": str(graph_json(paths.root).relative_to(paths.root)) if graph_json(paths.root).exists() else None,
        "output": output[-4000:],
    }


_ID_TOKEN = re.compile(r"^(?:REQ|TASK|ARCH|ADR|FEAT|F)[-_]?\d+", re.I)


def search_trace_corpus(root: Path, question: str, *, limit: int = 2500) -> str:
    """Deterministic keyword search of the SDD traceability corpus."""
    corpus = corpus_path(root)
    if not corpus.exists():
        return ""
    tokens = [tok for tok in re.findall(r"[A-Za-z0-9_./-]+", question or "") if len(tok) >= 3]
    if not tokens:
        return ""
    id_tokens = [tok for tok in tokens if _ID_TOKEN.match(tok)]
    id_hits: list[str] = []
    other: list[str] = []
    for line in corpus.read_text(encoding="utf-8").splitlines():
        lowered = line.lower()
        if any(tok.lower() in lowered for tok in tokens):
            if id_tokens and any(tok.lower() in lowered for tok in id_tokens):
                id_hits.append(line)
            else:
                other.append(line)
    kept = list(id_hits)
    text = "\n".join(kept)
    for line in other:
        candidate = f"{text}\n{line}" if text else line
        if len(candidate) > limit:
            break
        text = candidate
    if not text:
        text = "\n".join(id_hits)
    return text[:limit]


def query_knowledge_graph(root: Path, question: str, *, limit: int = 4000, timeout: int = 90) -> str:
    limit = max(1, int(limit))
    code_text = ""
    if graphify_installed() and graph_json(root).exists():
        code, output = run_graphify(root, ["query", question], timeout=timeout)
        if code == 0 and output.strip():
            code_text = output.strip()
    header_corpus = "# Traceability corpus\n"
    header_code = "# Code graph\n"
    joiner = "\n\n"
    corpus_budget = limit
    if code_text:
        corpus_budget = max(1, min(limit, (limit * 3) // 5))
        corpus_budget = min(corpus_budget, max(1, limit - len(header_code) - len(joiner)))
    corpus = search_trace_corpus(root, question, limit=max(1, corpus_budget - len(header_corpus)))
    if not corpus and not corpus_path(root).exists():
        try:
            write_trace_corpus(SDDPaths(root))
        except Exception:
            pass
        corpus = search_trace_corpus(root, question, limit=max(1, corpus_budget - len(header_corpus)))
    parts: list[str] = []
    remaining = limit
    if corpus:
        chunk = header_corpus + corpus
        parts.append(chunk[:remaining])
        remaining = max(0, remaining - len(parts[-1]) - len(joiner))
    if code_text and remaining > len(header_code):
        chunk = header_code + code_text
        parts.append(chunk[:remaining])
    result = joiner.join(parts)
    if len(result) > limit:
        result = result[:limit]
    return result


def graph_context(paths: SDDPaths, question: str = "architecture and requirements") -> str:
    scoped = query_knowledge_graph(paths.root, question)
    if scoped:
        return "# Graphify query\n\n" + scoped
    corpus = corpus_path(paths.root)
    if not corpus.exists():
        write_trace_corpus(paths)
    text = corpus.read_text(encoding="utf-8") if corpus.exists() else ""
    note = "Graphify graph is not built. Run `sdd graph refresh` after installing the graphify CLI.\n\n"
    return note + text[:8000]
