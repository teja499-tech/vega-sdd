from __future__ import annotations

import re

from .models import ArchitectureDecision, SpecBundle
from .storage import SDDPaths, dump_yaml


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) if items else "- None"


def write_architecture(paths: SDDPaths, decisions: list[ArchitectureDecision]) -> None:
    dump_yaml(paths.architecture_decisions_file, decisions)
    index_lines = ["# Architecture Decisions", ""]
    for decision in decisions:
        selected = decision.selected or decision.recommendation or "Deferred"
        index_lines.append(f"- **{decision.id} — {decision.category}:** {selected}")
        adr = paths.decisions / f"{decision.id.lower()}-{decision.category.replace('_','-')}.md"
        option_text = []
        for option in decision.options:
            option_text.append(
                f"### {option.name}\n{option.summary}\n\n**Strengths**\n{_md_list(option.strengths)}\n\n**Tradeoffs**\n{_md_list(option.tradeoffs)}\n\nFit: {option.fit or 'not rated'}"
            )
        options_markdown = "\n\n".join(option_text)
        adr.write_text(
            f"# {decision.id} — {decision.category.replace('_',' ').title()}\n\n"
            f"## Status\n{decision.status.value}\n\n"
            f"## Context\n{decision.rationale}\n\n"
            f"## Decision Question\n{decision.question}\n\n"
            f"## Options Considered\n\n{options_markdown}\n\n"
            f"## Recommendation\n{decision.recommendation or 'None'}\n\n{decision.recommendation_reason}\n\n"
            f"## Approved Decision\n{decision.selected or 'Deferred'}\n\n"
            f"## Decision Reason\n{decision.selected_reason or 'Not recorded'}\n",
            encoding="utf-8",
        )
    (paths.architecture / "decisions.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")


def write_spec_bundle(paths: SDDPaths, bundle: SpecBundle, *, preserve_verification: bool = False) -> None:
    from .spec_quality import assert_spec_quality
    assert_spec_quality(bundle)
    product = bundle.product
    (paths.product / "vision.md").write_text(
        f"# {product.name}\n\n{product.summary}\n\n## Users\n{_md_list(product.users)}\n\n## Capabilities\n{_md_list(product.capabilities)}\n",
        encoding="utf-8",
    )
    (paths.product / "workflows.md").write_text("# Workflows\n\n" + _md_list(product.workflows) + "\n", encoding="utf-8")
    (paths.product / "constraints.md").write_text(
        "# Constraints\n\n" + _md_list(product.constraints) + "\n\n# Assumptions\n\n" + _md_list(product.assumptions) + "\n",
        encoding="utf-8",
    )
    (paths.product / "open-questions.md").write_text("# Open Questions\n\n" + _md_list(product.open_questions) + "\n", encoding="utf-8")

    req_lines = ["# Requirements", ""]
    for r in bundle.requirements:
        req_lines += [
            f"## {r.id} — {r.title}",
            "",
            r.statement,
            "",
            f"- Type: {r.kind}",
            f"- Priority: {r.priority}",
            f"- Source: {r.source}",
            "",
            "### Acceptance Criteria",
            _md_list(r.acceptance_criteria),
            "",
        ]
    (paths.product / "requirements.md").write_text("\n".join(req_lines), encoding="utf-8")

    (paths.architecture / "system.md").write_text(
        "# System Architecture\n\n" + bundle.architecture_summary + "\n\n## Security Principles\n" + _md_list(bundle.security_principles) + "\n",
        encoding="utf-8",
    )
    (paths.sdd / "test-strategy.md").write_text("# Test Strategy\n\n" + _md_list(bundle.test_strategy) + "\n", encoding="utf-8")
    (paths.sdd / "release-criteria.md").write_text("# Release Criteria\n\n" + _md_list(bundle.release_criteria) + "\n", encoding="utf-8")

    roadmap = ["# Roadmap", ""]
    for feature in bundle.features:
        feature_dir = paths.specs / f"{feature.id}-{re.sub(r'[^a-z0-9_-]+', '-', feature.name.lower())}"
        feature_dir.mkdir(parents=True, exist_ok=True)
        roadmap.append(f"- [ ] {feature.id} — {feature.name} (depends on: {', '.join(feature.depends_on) or 'none'})")
        task_lines = ["# Tasks", ""]
        for task in feature.tasks:
            task_lines += [
                f"## {task.id} — {task.title}",
                "",
                task.description,
                "",
                f"- Implements: {', '.join(task.implements) or 'none'}",
                f"- Depends on: {', '.join(task.depends_on) or 'none'}",
                f"- Verification: {', '.join(task.verification) or 'not specified'}",
                "",
            ]
        (feature_dir / "spec.md").write_text(
            f"# {feature.id} — {feature.name}\n\n{feature.summary}\n\n"
            f"## Invariants\n{_md_list(feature.invariants)}\n\n"
            f"## Non-goals\n{_md_list(feature.non_goals)}\n\n"
            f"## Requirements\n{_md_list(feature.requirements)}\n\n"
            f"## API contract\n\n{feature.api_contract or 'Not applicable'}\n\n"
            f"## UX contract\n\n{feature.ux_contract or 'Not applicable'}\n\n"
            f"## Test matrix\n{_md_list(feature.test_matrix)}\n\n"
            f"## Target files\n{_md_list(feature.target_files)}\n\n"
            f"## Dependencies\n{_md_list(feature.depends_on)}\n",
            encoding="utf-8",
        )
        (feature_dir / "tasks.md").write_text("\n".join(task_lines), encoding="utf-8")
        dump_yaml(feature_dir / "state.yaml", feature)
    (paths.sdd / "roadmap.md").write_text("\n".join(roadmap) + "\n", encoding="utf-8")

    from .project_graph import refresh_graph
    dump_yaml(paths.requirements_file, bundle.requirements)
    dump_yaml(paths.features_file, bundle.features)
    dump_yaml(paths.spec_bundle_file, bundle)
    refresh_graph(paths)
    if not preserve_verification or not paths.verification_file.exists():
        dump_yaml(paths.verification_file, [])
    from .documentation import render_docs
    from .history import snapshot_specs, render_history
    snapshot_specs(paths)
    render_docs(paths)
    render_history(paths)


def project_context(paths: SDDPaths, max_chars: int = 30000) -> str:
    chunks: list[str] = []
    candidates = [
        paths.product / "vision.md",
        paths.product / "requirements.md",
        paths.architecture / "system.md",
        paths.architecture / "decisions.md",
        paths.sdd / "roadmap.md",
        paths.status_file,
    ]
    for path in candidates:
        if path.exists():
            chunks.append(f"\n## {path.relative_to(paths.root)}\n{path.read_text(encoding='utf-8')}")
    text = "\n".join(chunks)
    return text[:max_chars]
