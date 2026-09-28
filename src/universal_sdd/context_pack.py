"""Bounded working-set packs so agents do not re-crawl the repository."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .graphify_index import query_knowledge_graph
from .models import Feature, Task
from .skill_library import lifecycle_skill, skill_catalog
from .storage import SDDPaths, load_yaml


MAX_FILES = 15
MAX_FILE_CHARS = 1800
MAX_PACK_CHARS = 12000
RESERVED_AC_CHARS = 2200
RESERVED_FINDINGS_CHARS = 2200


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
    changed_files: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)

    def render(self, limit: int = MAX_PACK_CHARS) -> str:
        skills = [self.skill, *self.extra_skills]
        sections = {
            "intro": "Before Read, Grep, or Glob, run `graphify query` (or `graphify path` / `graphify explain`) when graphify-out/graph.json exists.",
            "skills": "Skill catalog (name + when-to-load only):\n" + skill_catalog(*skills),
            "acceptance": "Acceptance criteria:\n" + _bounded_json(self.acceptance_criteria, RESERVED_AC_CHARS),
            "files": "Working set:\n" + _bounded_json(self.files[:MAX_FILES], 1500),
            "tests": "Related tests:\n" + _bounded_json(self.related_tests, 800),
            "adrs": "Relevant ADRs: " + (", ".join(self.adr_ids) or "none"),
            "changed": "Changed files this task (tracked + untracked):\n" + (
                json.dumps(self.changed_files, indent=2) if self.changed_files else _bounded_json(self.files, 1200)
            ),
            "oos": "Out-of-scope writes (reviewer must approve or fail):\n" + _bounded_json(self.out_of_scope, 800),
            "contracts": "Feature contracts:\n" + _truncate_field(self.contracts or "none recorded", 1500),
            "spec": "Spec excerpt:\n" + _truncate_field(self.spec_excerpt or "none", 2000),
            "graph": "Graphify subgraph:\n" + _truncate_field(self.graph_excerpt or "No scoped subgraph yet. Run sdd graph refresh.", 1500),
            "findings": "Last review findings:\n" + _bounded_json(self.last_findings, RESERVED_FINDINGS_CHARS),
        }
        shrinkable = ["spec", "graph", "contracts", "files", "oos", "tests", "skills"]
        reserved = {"acceptance", "findings"}
        if self.changed_files:
            reserved.add("changed")
        else:
            shrinkable.insert(3, "changed")
        body = _join_sections(sections)
        while len(body) > limit and shrinkable:
            key = shrinkable.pop(0)
            if key in reserved:
                continue
            sections[key] = _truncate_field(sections[key], max(80, len(sections[key]) // 2))
            body = _join_sections(sections)
        if len(body) > limit:
            keep = ("intro", "skills", "acceptance", "findings", "oos")
            if self.changed_files:
                keep = (*keep, "changed")
            body = _join_sections({k: sections[k] for k in keep})
        if self.changed_files:
            missing = [name for name in self.changed_files if name not in sections["changed"]]
            if missing:
                raise RuntimeError(
                    "Review pack omitted changed files: "
                    + ", ".join(missing)
                    + ". Split the task or raise max_review_files."
                )
        return body


def _join_sections(sections: dict[str, str]) -> str:
    return "\n".join(part for part in sections.values() if part)


def _truncate_field(text: str, budget: int) -> str:
    raw = text or ""
    if len(raw) <= budget:
        return raw
    marker = "\n…[truncated]"
    return raw[: max(0, budget - len(marker))].rstrip() + marker


def _bounded_json(value: Any, budget: int) -> str:
    if isinstance(value, list):
        kept: list[Any] = list(value)
        dumped = json.dumps(kept, indent=2)
        while kept and len(dumped) > budget:
            kept.pop()
            dumped = json.dumps(kept, indent=2)
        if len(json.dumps(value, indent=2)) > budget:
            if dumped.startswith("[") and dumped.endswith("]"):
                inner = dumped[1:-1].rstrip()
                suffix = ', "...truncated"]' if inner else '["...truncated"]'
                candidate = "[" + inner + suffix if inner else suffix
                if len(candidate) <= budget:
                    return candidate
        return dumped if len(dumped) <= budget else _truncate_field(dumped, budget)
    dumped = json.dumps(value, indent=2)
    return dumped if len(dumped) <= budget else _truncate_field(dumped, budget)


def skills_for_phase(phase: str, task: Task | None = None) -> tuple[str, list[str]]:
    extra: list[str] = []
    blob = ""
    if task is not None:
        blob = f"{task.title} {task.description} {' '.join(task.verification)}".lower()
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
    return lifecycle_skill(phase), extra


def skills_for_task(task: Task, phase: str = "implement") -> tuple[str, list[str]]:
    return skills_for_phase(phase, task)


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


def adr_id_from_path(path: Path) -> str:
    stem = path.stem
    match = re.match(r"(?i)((?:ADR|ARCH|DEC)[-_]?\d+)", stem)
    if match:
        return match.group(1).upper().replace("_", "-")
    parts = stem.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return f"{parts[0].upper()}-{parts[1]}"
    return stem.upper()


def _adr_ids(paths: SDDPaths) -> list[str]:
    ids = [adr_id_from_path(p) for p in sorted(paths.decisions.glob("*.md"))]
    return list(dict.fromkeys(ids))[:12]


def build_context_pack(paths: SDDPaths, task: Task, feature: Feature, *, phase: str = "implement") -> ContextPack:
    skill, extra = skills_for_phase(phase, task)
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
        adr_ids=_adr_ids(paths),
        last_findings=list(task.last_findings or []),
        spec_excerpt=_spec_excerpt(paths, feature, task),
        contracts=_contracts(feature),
        graph_excerpt=graph_excerpt,
    )


def rebuild_review_pack(
    paths: SDDPaths,
    task: Task,
    feature: Feature,
    changed_files: list[str],
    pack: ContextPack | None = None,
) -> ContextPack:
    """Rebuild the review pack from files that actually changed, including untracked."""
    base = pack or build_context_pack(paths, task, feature, phase="review")
    skill, extra = skills_for_phase("review", task)
    declared = {
        *task.working_set,
        *feature.target_files,
        *task.check_paths,
        *base.files,
        *base.related_tests,
        f".agents/skills/{skill}/SKILL.md",
        *[f".agents/skills/{name}/SKILL.md" for name in extra],
        "AGENTS.md",
    }
    cleaned = []
    for rel in changed_files:
        if not rel or ".." in rel or Path(rel).is_absolute():
            continue
        if rel.startswith(".sdd/") or rel.startswith(".git/"):
            continue
        cleaned.append(rel)
    try:
        from .storage import load_config
        limit = max(1, int(load_config(paths).max_review_files))
    except Exception:
        limit = MAX_FILES
    if len(cleaned) > limit:
        raise RuntimeError(
            f"Task changed {len(cleaned)} files; review limit is {limit}. "
            "Split the task or set max_review_files in .sdd/config.yaml."
        )
    out_of_scope = [rel for rel in cleaned if rel not in declared]
    extras = [rel for rel in base.files if rel not in cleaned]
    files = list(dict.fromkeys([*cleaned, *extras]))
    if len(files) > max(limit, len(cleaned)):
        files = list(dict.fromkeys([*cleaned, *extras]))[: max(limit, len(cleaned))]
    tests = list(dict.fromkeys([rel for rel in files if "test" in rel] + base.related_tests))
    return base.model_copy(
        update={
            "skill": skill,
            "extra_skills": extra,
            "files": files,
            "related_tests": tests,
            "changed_files": cleaned,
            "out_of_scope": out_of_scope,
            "last_findings": list(task.last_findings or []),
        }
    )


def persist_working_set(task: Task, pack: ContextPack, extra: list[str] | None = None) -> None:
    names = list(dict.fromkeys([*pack.files, *(extra or [])]))
    if pack.changed_files:
        task.working_set = names
    else:
        task.working_set = names[:MAX_FILES]
