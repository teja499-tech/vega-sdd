from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Feature, ItemStatus, Requirement
from .storage import SDDPaths, load_project_state, load_yaml


@dataclass
class StatusMetrics:
    requirements_total: int = 0
    requirements_implemented: int = 0
    requirements_verified: int = 0
    requirements_specified: int = 0
    features_total: int = 0
    features_verified: int = 0
    tasks_total: int = 0
    tasks_implemented: int = 0
    tasks_verified: int = 0

    @property
    def implementation_pct(self) -> float:
        return 100.0 * self.requirements_implemented / self.requirements_total if self.requirements_total else 0.0

    @property
    def verification_pct(self) -> float:
        return 100.0 * self.requirements_verified / self.requirements_total if self.requirements_total else 0.0

    @property
    def spec_pct(self) -> float:
        return 100.0 * self.requirements_specified / self.requirements_total if self.requirements_total else 0.0

    @property
    def overall_pct(self) -> float:
        # Requirements are not counted twice; overall is deliberately conservative.
        return (self.implementation_pct * 0.45) + (self.verification_pct * 0.55)


def load_features(paths: SDDPaths) -> list[Feature]:
    return [Feature.model_validate(x) for x in (load_yaml(paths.features_file, []) or [])]


def load_requirements(paths: SDDPaths) -> list[Requirement]:
    return [Requirement.model_validate(x) for x in (load_yaml(paths.requirements_file, []) or [])]


def metrics(paths: SDDPaths) -> StatusMetrics:
    features = load_features(paths)
    requirements = load_requirements(paths)
    tasks = [t for f in features for t in f.tasks]
    mapped = {r.id: [t for t in tasks if r.id in t.implements] for r in requirements}
    implemented_req_ids = {rid for rid, ts in mapped.items() if ts and all(
        t.status in {ItemStatus.implemented, ItemStatus.verified} for t in ts)}
    verified_req_ids = {rid for rid, ts in mapped.items() if ts and all(
        t.status == ItemStatus.verified for t in ts)}
    return StatusMetrics(
        requirements_total=len(requirements),
        requirements_specified=sum(bool(r.acceptance_criteria and mapped[r.id]) for r in requirements),
        requirements_implemented=len(implemented_req_ids),
        requirements_verified=len(verified_req_ids),
        features_total=len(features),
        features_verified=sum(1 for f in features if f.status == ItemStatus.verified),
        tasks_total=len(tasks),
        tasks_implemented=sum(1 for t in tasks if t.status in {ItemStatus.implemented, ItemStatus.verified}),
        tasks_verified=sum(1 for t in tasks if t.status == ItemStatus.verified),
    )


def render_status(paths: SDDPaths) -> str:
    state = load_project_state(paths)
    features = load_features(paths)
    m = metrics(paths)
    lines = [
        "# SDD Project Status",
        "",
        f"- Run status: **{state.run_status.value}**",
        f"- Overall: **{m.overall_pct:.1f}%**",
        f"- Specification completeness: **{m.spec_pct:.1f}%**",
        f"- Implementation completeness: **{m.implementation_pct:.1f}%**",
        f"- Verification completeness: **{m.verification_pct:.1f}%**",
        f"- Current feature: `{state.current_feature or '-'} `",
        f"- Current task: `{state.current_task or '-'} `",
        "",
        "## Traceability",
        f"- Requirements: {m.requirements_total}",
        f"- Requirements implemented: {m.requirements_implemented}",
        f"- Requirements verified: {m.requirements_verified}",
        f"- Tasks: {m.tasks_total}",
        f"- Tasks implemented: {m.tasks_implemented}",
        f"- Tasks verified: {m.tasks_verified}",
        "",
        "## Features",
    ]
    for feature in features:
        total = len(feature.tasks)
        done = sum(1 for t in feature.tasks if t.status == ItemStatus.verified)
        pct = 100.0 * done / total if total else 0.0
        lines.append(f"- {feature.id} — {feature.name}: **{feature.status.value}** ({pct:.0f}%)")
    return "\n".join(lines) + "\n"


def publish_status(paths: SDDPaths) -> str:
    text = render_status(paths)
    paths.status_file.write_text(text, encoding="utf-8")
    return text
