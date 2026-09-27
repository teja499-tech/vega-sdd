"""Bounded working-set packs so agents do not re-crawl the repository."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .graphify_index import query_knowledge_graph
from .models import Feature, Task
from .skill_library import skill_summary
from .storage import SDDPaths, load_yaml


MAX_FILES = 15
MAX_FILE_CHARS = 1800
MAX_PACK_CHARS = 12000


class ContextPack(BaseModel):
    task_id: str
    feature_id: str
    skill: str = "implement-task"
    extra_skills: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    related_tests: list[str] = Field(default_factory=list)
    adr_ids: list[str] = Field(default_factory=list)
    last_findings: list[dict[str, Any]] = Field(default_factory=list)
    spec_excerpt: str = ""
    contracts: str = ""
    graph_excerpt: str = ""

    def render(self, limit: int = MAX_PACK_CHARS) -> str:
        skills = [self.skill, *self.extra_skills]
        catalog = "\n".join(
            f"- {name}: {skill_summary(name)} — read `.agents/skills/{name}/SKILL.md` only if this task matches. Do not expect the runbook in this prompt."
            for name in skills
        )
        body = "\n".join(
            [
                "Before Read, Grep, or Glob, run `graphify query` (or `graphify path` / `graphify explain`) when graphify-out/graph.json exists.",
                "Skill catalog (name + when-to-load only):",
                catalog,
                f"Acceptance criteria:\n{json.dumps(self.acceptance_criteria, indent=2)}",
                f"Working set:\n{json.dumps(self.files[:MAX_FILES], indent=2)}",
                f"Related tests:\n{json.dumps(self.related_tests, indent=2)}",
                f"Relevant ADRs: {', '.join(self.adr_ids) or 'none'}",
                f"Feature contracts:\n{self.contracts or 'none recorded'}",
                f"Spec excerpt:\n{self.spec_excerpt or 'none'}",
                f"Graphify subgraph:\n{self.graph_excerpt or 'No scoped subgraph yet. Run sdd graph refresh.'}",
                f"Last review findings:\n{json.dumps(self.last_findings, indent=2)}",
            ]
        )
        return body[:limit]


def skills_for_task(task: Task) -> tuple[str, list[str]]:
    blob = f"{task.title} {task.description} {' '.join(task.verification)}".lower()
    extra: list[str] = []
    if any(token in blob for token in ("api", "route", "openapi", "endpoint", "http")):
        extra.append("api-design")
    if any(token in blob for token in ("ux", "ui", "page", "screen", "accessibility", "copy")):
        extra.append("ux-design")
    if any(token in blob for token in ("schema", "model", "migration", "database", "entity")):
        extra.append("data-model")
    if any(token in blob for token in ("readme", "docs", "guide", "documentation")):
        extra.append("docs-writer")
    if any(token in blob for token in ("auth", "secret", "threat", "security")):
        extra.append("security-review")
        extra.append("threat-model")
    return "implement-task", extra


def _existing_paths(root: Path, relatives: list[str]) -> list[str]:
    found: list[str] = []
    for rel in relatives:
        if not rel or ".." in rel or Path(rel).is_absolute():
            continue
        if (root / rel).exists():
            found.append(rel)
    return found


def _acceptance_criteria(paths: SDDPaths, task: Task) -> list[str]:
    criteria = list(task.verification)
    requirements = load_yaml(paths.requirements_file, []) or []
    by_id = {row.get("id"): row for row in requirements if isinstance(row, dict)}
    for req_id in task.implements:
        req = by_id.get(req_id) or {}
        criteria.extend(req.get("acceptance_criteria") or [])
    return criteria[:20]


def _spec_excerpt(paths: SDDPaths, feature: Feature, task: Task) -> str:
    chunks: list[str] = []
    for folder in paths.specs.glob(f"{feature.id}-*"):
        spec = folder / "spec.md"
        tasks = folder / "tasks.md"
        if spec.exists():
            chunks.append(spec.read_text(encoding="utf-8")[:2500])
        if tasks.exists():
            text = tasks.read_text(encoding="utf-8")
            marker = f"## {task.id}"
            start = text.find(marker)
            chunks.append(text[start:start + 1200] if start >= 0 else text[:800])
        break
    return "\n\n".join(chunks)[:3500]


def _contracts(feature: Feature) -> str:
    parts = [
        f"Invariants: {'; '.join(feature.invariants) or 'none'}",
        f"Non-goals: {'; '.join(feature.non_goals) or 'none'}",
        f"Test matrix: {'; '.join(feature.test_matrix) or 'none'}",
        f"API contract: {feature.api_contract or 'none'}",
        f"UX contract: {feature.ux_contract or 'none'}",
    ]
    return "\n".join(parts)


def _graph_files(paths: SDDPaths, task: Task, feature: Feature) -> list[str]:
    question = f"{feature.id} {task.id} {task.title} {' '.join(task.verification)}"
    excerpt = query_knowledge_graph(paths.root, question)
    found: list[str] = []
    for token in excerpt.replace("(", " ").replace(")", " ").replace(",", " ").split():
        if ".." in token or token.startswith("/"):
            continue
        if any(token.endswith(suffix) for suffix in (".py", ".ts", ".tsx", ".js", ".md", ".yml", ".yaml", ".json")):
            found.append(token.strip("`\"'"))
    return found[:MAX_FILES]


def build_context_pack(paths: SDDPaths, task: Task, feature: Feature) -> ContextPack:
    skill, extra = skills_for_task(task)
    graph_excerpt = query_knowledge_graph(
        paths.root,
        f"{feature.id} {feature.name} {task.id} {task.title}. Acceptance: {' '.join(task.verification)}",
    )
    files = _existing_paths(
        paths.root,
        [
            *task.working_set,
            *feature.target_files,
            *_graph_files(paths, task, feature),
            "AGENTS.md",
            f".agents/skills/{skill}/SKILL.md",
            *[f".agents/skills/{name}/SKILL.md" for name in extra],
        ],
    )
    tests = [rel for rel in files if "test" in rel]
    related = _existing_paths(paths.root, task.check_paths) + tests
    unique_files = list(dict.fromkeys(files))[:MAX_FILES]
    unique_tests = list(dict.fromkeys(related))[:MAX_FILES]
    return ContextPack(
        task_id=task.id,
        feature_id=feature.id,
        skill=skill,
        extra_skills=extra,
        acceptance_criteria=_acceptance_criteria(paths, task),
        files=unique_files,
        related_tests=unique_tests,
        adr_ids=[p.stem.upper().split("-")[0] for p in paths.decisions.glob("*.md")][:12],
        last_findings=list(task.last_findings or []),
        spec_excerpt=_spec_excerpt(paths, feature, task),
        contracts=_contracts(feature),
        graph_excerpt=graph_excerpt,
    )


def persist_working_set(task: Task, pack: ContextPack, extra: list[str] | None = None) -> None:
    task.working_set = list(dict.fromkeys([*pack.files, *(extra or [])]))[:MAX_FILES]
