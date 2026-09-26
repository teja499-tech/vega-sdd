from __future__ import annotations

import json
from pathlib import Path

from .models import ArchitectureDecision, Feature, SDDConfig, Task



def product_discovery_prompt(prd: str, repo_summary: str = "") -> str:
    return f"""
You are the Product Analyst for Vega SDD.
Analyze the PRD before architecture decisions are made.
Return ONLY JSON. No markdown fences.
Marker: PRODUCT_DISCOVERY_JSON

{{
  "name":"...",
  "summary":"...",
  "users":["..."],
  "capabilities":["..."],
  "workflows":["..."],
  "constraints":["..."],
  "assumptions":["..."],
  "open_questions":["questions that materially affect product behavior or architecture"]
}}

Rules:
- Do not turn assumptions into requirements.
- Ask only questions whose answers can materially change product behavior, data model, security, architecture, deployment, or scope.
- Avoid questions that an engineering team can safely resolve autonomously later.
- For an existing repository, flag conflicts between PRD intent and obvious existing behavior as open questions.

<PRD>
{prd}
</PRD>
<EXISTING_REPOSITORY_CONTEXT>
{repo_summary or 'No existing codebase context supplied.'}
</EXISTING_REPOSITORY_CONTEXT>
""".strip()

def architecture_prompt(prd: str, repo_summary: str = "") -> str:
    return f"""
You are the Product Architect for Vega SDD.
Analyze the PRD and identify ONLY architecture decisions that materially matter to this project.
Do not silently choose technologies. Research-aware options should be current and realistic, but the user decides.
Return ONLY JSON. No markdown fences.
Marker: ARCHITECTURE_DECISIONS_JSON

For each decision return:
[
  {{
    "id": "ARCH-001",
    "category": "frontend|backend|database|object_storage|identity|workers|messaging|cache|secrets|deployment|observability|cicd|iac|other",
    "question": "...",
    "rationale": "why this decision matters",
    "requirements": ["requirement/constraint inferred from PRD"],
    "options": [
      {{"name":"...","summary":"...","strengths":["..."],"tradeoffs":["..."],"fit":"high|medium|low"}}
    ],
    "recommendation": "one option name or null",
    "recommendation_reason": "...",
    "researched_at": "current date if known"
  }}
]

Rules:
- Include 2-5 credible options when a decision genuinely has alternatives.
- Do not ask about infrastructure the PRD does not need.
- If the repository already constrains a decision, record that as an option and explain it.
- Prefer official, maintainable, production-grade technologies.
- Do not invent product requirements.

<PRD>
{prd}
</PRD>

<EXISTING_REPOSITORY_CONTEXT>
{repo_summary or 'No existing codebase context supplied.'}
</EXISTING_REPOSITORY_CONTEXT>
""".strip()


def spec_bundle_prompt(prd: str, decisions: list[ArchitectureDecision], repo_summary: str = "") -> str:
    selected = [d.model_dump(mode="json") for d in decisions]
    return f"""
You are the Specification Lead for Vega SDD.
Create the durable specification bundle from the PRD and approved architecture decisions.
Return ONLY one JSON object. No markdown fences.
Marker: SPEC_BUNDLE_JSON

Required shape:
{{
  "product": {{
    "name":"...", "summary":"...", "users":["..."], "capabilities":["..."],
    "workflows":["..."], "constraints":["..."], "assumptions":["..."], "open_questions":["..."]
  }},
  "requirements": [
    {{
      "id":"REQ-AREA-001", "title":"...", "statement":"The system shall ...",
      "kind":"functional|non_functional|constraint", "priority":"must|should|could",
      "source":"PRD|ADR-...", "acceptance_criteria":["AC-AREA-001: ..."]
    }}
  ],
  "architecture_summary":"...",
  "design_documents": {{
    "SYSTEM_OVERVIEW": {{"status":"draft|documented|not_applicable", "summary":"...",
      "sections":{{"Purpose and scope":"...", "Users and workflows":"...", "System boundaries":"..."}},
      "sources":["PRD", "REQ-...", "repository/path:line"], "gaps":[], "not_applicable_reason":""}}
  }},
  "features": [
    {{
      "id":"F001", "name":"...", "summary":"...", "requirements":["REQ-..."],
      "depends_on":["F000"],
      "tasks":[
        {{
          "id":"TASK-F001-001", "feature_id":"F001", "title":"...", "description":"...",
          "implements":["REQ-..."], "depends_on":["TASK-..."],
          "verification":["specific deterministic check"]
        }}
      ]
    }}
  ],
  "test_strategy":["..."],
  "security_principles":["..."],
  "release_criteria":["..."]
}}

Rules:
- Produce human-readable design_documents for every contract below. Use EXACT document keys and section titles.
- SYSTEM_OVERVIEW: Purpose and scope; Users and workflows; System boundaries.
- HLD: Components and responsibilities; Interactions and data flows; Deployment topology; Quality attributes and tradeoffs.
- LLD: Modules and interfaces; Key execution flows; Validation and failure handling; Concurrency and idempotency.
- DATABASE_DESIGN: Entities and relationships; Fields and constraints; Indexes and access patterns; Migrations and retention.
- API_DESIGN: Contracts and authentication; Requests and responses; Errors and compatibility.
- SECURITY: Trust boundaries and threats; Access control and secrets; Privacy and audit.
- OPERATIONS: Configuration and deployment; Monitoring and alerts; Backup and restore; Incident response and rollback.
- TEST_PLAN: Acceptance and integration; Performance and security; Test data and environments.
- EXISTING_SYSTEM: Observed current behavior; Evidence and unknowns; Intended changes and compatibility; Migration and rollback.
- CONTRIBUTING: Local setup; Development and review workflow; Ownership and escalation.
- RELEASE_PLAN: Release criteria; Versioning and release notes; Rollout and rollback.
- Include project-specific prose, tables and Mermaid diagrams where useful. No generic filler.
- Cite supplied PRD, requirement/ADR IDs and actual inspected repository file paths. Never invent observations, commands, owners or test results.
- For greenfield label planned design; for brownfield and completed apps distinguish observed/as-is from planned/to-be. File names alone do not prove behavior. Inspect code read-only when available.
- Missing facts must go in gaps; documented requires all contract sections and sources and no gaps. not_applicable requires a substantive reason (e.g. no persistent data).
- Descriptive documents cannot authorize new architecture, product intent or deployment. Surface conflicts for sdd change.
- Preserve PRD intent. Do not create unsupported business requirements.
- Every MUST requirement must appear in at least one feature and task.
- Acceptance criteria must be testable.
- Tasks should be small enough for one bounded coding-agent run.
- Dependencies must form a sensible DAG.
- Include architecture/security/deployment/testing tasks when the project requires them.
- For existing repositories, preserve existing behavior unless PRD explicitly changes it.
- Open ambiguities belong in product.open_questions; do not resolve them silently.

<PRD>
{prd}
</PRD>

<APPROVED_ARCHITECTURE_DECISIONS>
{json.dumps(selected, indent=2)}
</APPROVED_ARCHITECTURE_DECISIONS>

<EXISTING_REPOSITORY_CONTEXT>
{repo_summary or 'No existing codebase context supplied.'}
</EXISTING_REPOSITORY_CONTEXT>
""".strip()


def implement_task_prompt(task: Task, feature: Feature, root: Path) -> str:
    return f"""
You are the primary implementation agent operating under Vega SDD.
Marker: TASK_IMPLEMENTATION

Implement exactly this bounded task in repository {root}.
Do not change product requirements or architecture decisions to make implementation easier.
Read AGENTS.md and the relevant .sdd artifacts before editing.
Use existing project conventions. Add/update tests that prove the listed verification criteria.
Run the narrowest relevant deterministic checks before finishing.
Maintain human implementation notes and relevant project-owned documentation. Include task and requirement IDs in any commits you are authorized to create. Add an exact SDD-Task: <task-id> trailer for automatic commit attribution. Do not fabricate commit IDs.
Do not mark SDD state files complete yourself; the SDD controller owns canonical state.

Feature: {feature.id} — {feature.name}
Feature summary: {feature.summary}
Task: {task.id} — {task.title}
Description: {task.description}
Implements: {', '.join(task.implements) or 'none listed'}
Verification: {json.dumps(task.verification)}
""".strip()


def review_task_prompt(task: Task, feature: Feature) -> str:
    return f"""
You are an independent SDD reviewer. Do not assume the implementation agent was correct.
Review the current git diff, relevant specification, tests, and implementation for this task.
Return ONLY JSON. No markdown fences.
Marker: TASK_REVIEW_JSON

{{
  "status":"pass|fail|warning",
  "findings":[
    {{"severity":"critical|high|medium|low","summary":"...","evidence":"file/test/spec reference","repair":"..."}}
  ],
  "summary":"..."
}}

Feature: {feature.id} — {feature.name}
Task: {task.id} — {task.title}
Implements: {json.dumps(task.implements)}
Verification: {json.dumps(task.verification)}
""".strip()


def repair_task_prompt(task: Task, findings: list[dict]) -> str:
    return f"""
You are the implementation agent repairing a failed SDD review.
Fix the implementation defects below without changing approved requirements or architecture.
Run relevant tests after repair.
Do not edit canonical .sdd state to hide the failure.

Task: {task.id} — {task.title}
Findings:
{json.dumps(findings, indent=2)}
""".strip()


def change_analysis_prompt(description: str, project_context: str) -> str:
    return f"""
You are the SDD Architect handling an intervention.
Determine whether the user's concern is an implementation defect, spec defect, requirement change, or architecture change.
Compare the concern against current specifications and repository implementation.
Return ONLY JSON. No markdown fences.
Marker: CHANGE_ANALYSIS_JSON

{{
  "classification":"implementation_defect|spec_defect|requirement_change|architecture_change|unknown",
  "affected_requirements":["REQ-..."],
  "affected_features":["F..."],
  "affected_tasks":["TASK-..."],
  "proposed_changes":["..."],
  "requires_approval": true
}}

Rules:
- If the spec is already correct and code violates it, classify implementation_defect and requires_approval=false.
- Requirement/spec/architecture mutations require explicit user approval.
- Never rewrite a valid spec to match incorrect code.

<UserConcern>{description}</UserConcern>
<ProjectContext>{project_context}</ProjectContext>
""".strip()


def ask_architect_prompt(question: str, project_context: str) -> str:
    return f"""
You are the project's SDD Architect in an interactive intervention session.
Marker: ASK_ARCHITECT
Answer using the approved PRD, ADRs, specs, and current implementation state. Distinguish facts, approved decisions, assumptions, and proposed changes. If the user requests a change, explain impact before suggesting mutation.

<ProjectContext>{project_context}</ProjectContext>
<UserQuestion>{question}</UserQuestion>
""".strip()


def reconcile_change_prompt(description: str, classification: str, bundle_json: str, decisions_json: str) -> str:
    return f"""
You are the SDD reconciliation architect. An explicitly approved change must be applied to canonical structured specs.
Return ONLY JSON. No markdown fences. Marker: RECONCILE_CHANGE_JSON

Return:
{{
  "bundle": <complete SpecBundle object using the same schema supplied>,
  "architecture_decisions": <complete architecture decision list>,
  "invalidate_tasks": ["TASK-..."],
  "notes": ["what changed and why"]
}}

Rules:
- Preserve all stable requirement, feature, task and architecture IDs unless an item is truly removed or replaced.
- Add new IDs only for genuinely new items.
- Preserve unaffected content verbatim where practical.
- Update all traceability links and dependency edges.
- Update affected design_documents, preserving the same document contract and distinguishing current implementation from approved target design. Record unresolved details as gaps.
- List every previously completed task whose evidence is no longer valid in invalidate_tasks.
- Do not mark new or changed work verified.

Approved change classification: {classification}
Approved change: {description}

<CURRENT_SPEC_BUNDLE>{bundle_json}</CURRENT_SPEC_BUNDLE>
<CURRENT_ARCHITECTURE_DECISIONS>{decisions_json}</CURRENT_ARCHITECTURE_DECISIONS>
""".strip()
