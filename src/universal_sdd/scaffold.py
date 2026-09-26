from __future__ import annotations

from pathlib import Path

from .storage import SDDPaths

AGENTS_MD = """<!-- UNIVERSAL_SDD_START -->
# Vega SDD Project Instructions

This repository uses Spec Driven Development (SDD).

## Sources of truth
- Product intent: `.sdd/product/`
- Architecture and ADRs: `.sdd/architecture/` and `.sdd/decisions/`
- Feature specifications: `.sdd/specs/`
- Canonical execution state: `.sdd/state/`
- Reusable workflows: `.agents/skills/`

## Non-negotiable agent rules
1. Never invent product requirements.
2. Never silently change approved requirements or architecture.
3. Implement only the bounded task supplied by the SDD controller.
4. Acceptance criteria must map to deterministic verification wherever practical.
5. Do not mark SDD tasks complete yourself; the controller owns canonical state.
6. If implementation exposes a requirement or architecture ambiguity, surface it as a blocker/escalation.
7. Do not weaken tests to make a failing implementation pass.
8. Significant architecture changes require an ADR and explicit user approval.
9. Prefer repository skills for established workflows.
10. Leave the repository in a recoverable state.
<!-- UNIVERSAL_SDD_END -->
"""

ROLE_FILES = {
    "architect.md": """# Architect\nProtect product intent and architecture. Classify concerns before changing specs. Requirement and architecture changes need user approval.\n""",
    "developer.md": """# Developer\nImplement one bounded SDD task at a time. Do not mutate approved product intent. Add deterministic verification.\n""",
    "qa-engineer.md": """# QA Engineer\nIndependently verify acceptance criteria, negative paths, regressions, and evidence. Never rely solely on developer claims.\n""",
    "security-reviewer.md": """# Security Reviewer\nReview trust boundaries, authn/authz, secrets, input validation, injection, data exposure, dependencies, and least privilege.\n""",
    "spec-reviewer.md": """# Spec Reviewer\nCheck traceability from requirement to acceptance criterion to feature/task/test/evidence and detect implementation/spec drift.\n""",
    "integration-reviewer.md": """# Integration Reviewer\nCheck contracts across modules/services, migrations, backward compatibility, deployment, and operational behavior.\n""",
}

SKILLS = {
    "create-feature-spec/SKILL.md": """---\nname: create-feature-spec\ndescription: Convert approved product intent into testable requirements and feature specifications.\n---\n# Create Feature Spec\nPreserve PRD intent. Separate fact, requirement, assumption, decision, and question. Assign stable IDs. Make acceptance criteria testable.\n""",
    "architecture-design/SKILL.md": """---\nname: architecture-design\ndescription: Research and compare architecture options without silently choosing for the user.\n---\n# Architecture Design\nIdentify only material decisions. Present credible current options, tradeoffs, fit, and a recommendation. Record approved selections as ADRs.\n""",
    "implement-task/SKILL.md": """---\nname: implement-task\ndescription: Implement one bounded task against approved specs and verification criteria.\n---\n# Implement Task\nRead relevant spec and ADRs. Make minimal cohesive changes. Add tests. Run checks. Never edit specs to hide implementation defects.\n""",
    "verify-feature/SKILL.md": """---\nname: verify-feature\ndescription: Independently verify implementation against acceptance criteria and deterministic evidence.\n---\n# Verify Feature\nInspect diff, tests and runtime behavior. Map evidence to requirements. Return actionable findings and severity.\n""",
    "spec-drift/SKILL.md": """---\nname: spec-drift\ndescription: Detect divergence between approved specifications and current implementation.\n---\n# Spec Drift\nCompare requirements, APIs, schema, behavior, tests and docs. Classify whether code is wrong, spec is stale, or a new change request is needed.\n""",
    "security-review/SKILL.md": """---\nname: security-review\ndescription: Review a bounded change for security regressions and policy violations.\n---\n# Security Review\nReview trust boundaries, authn/authz, secret handling, input validation, injection, data exposure, dependencies and least privilege.\n""",
    "reconcile/SKILL.md": """---\nname: reconcile\ndescription: Safely reconcile approved changes across specs, tasks, state, tests, and evidence.\n---\n# Reconcile\nInvalidate stale evidence, update dependency graph, regenerate affected tasks and preserve history. Never erase prior journal events.\n""",
}

TEMPLATES = {
    "feature-spec.md": "# {feature_id} — {feature_name}\n\n## Summary\n\n## Requirements\n\n## Acceptance Criteria\n\n## Dependencies\n\n## Tasks\n",
    "adr.md": "# {adr_id} — {title}\n\n## Status\nAccepted\n\n## Context\n\n## Options Considered\n\n## Decision\n\n## Consequences\n",
    "evidence.md": "# Verification Evidence\n\n## Requirement / Acceptance Criterion\n\n## Evidence\n\n## Result\n",
}


def write_scaffold(root: Path) -> SDDPaths:
    paths = SDDPaths(root)
    paths.ensure()
    agents_file = root / "AGENTS.md"
    if not agents_file.exists():
        agents_file.write_text(AGENTS_MD, encoding="utf-8")
    else:
        current = agents_file.read_text(encoding="utf-8")
        if "<!-- UNIVERSAL_SDD_START -->" not in current:
            agents_file.write_text(current.rstrip() + "\n\n" + AGENTS_MD, encoding="utf-8")
    for name, content in ROLE_FILES.items():
        target = paths.roles / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
        # Thin vendor adapters: canonical role text remains in .agents/roles.
        for vendor_dir in [root / ".cursor" / "agents", root / ".claude" / "agents", root / ".codex" / "agents"]:
            vendor_dir.mkdir(parents=True, exist_ok=True)
            adapter = vendor_dir / name
            if not adapter.exists():
                adapter.write_text(content + "\nCanonical SDD sources: `AGENTS.md`, `.sdd/`, and `.agents/`.\n", encoding="utf-8")

    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("# Claude Code SDD Adapter\n\nFollow `AGENTS.md`. Canonical product/spec/state lives under `.sdd/`; reusable workflows live under `.agents/skills/`. Do not create Claude-only product requirements.\n", encoding="utf-8")
    cursor_rule = root / ".cursor" / "rules" / "vega-sdd.mdc"
    cursor_rule.parent.mkdir(parents=True, exist_ok=True)
    if not cursor_rule.exists():
        cursor_rule.write_text("---\ndescription: Vega SDD repository contract\nalwaysApply: true\n---\nFollow `AGENTS.md`. Treat `.sdd/state/` as canonical execution state and `.sdd/specs/` as approved feature intent. Load only task-relevant skills from `.agents/skills/`.\n", encoding="utf-8")

    for rel, content in SKILLS.items():
        target = paths.skills / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    for name, content in TEMPLATES.items():
        target = paths.templates / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    return paths
