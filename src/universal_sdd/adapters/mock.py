from __future__ import annotations

import json

from .base import AgentAdapter
from ..models import AgentCapabilities, AgentEvent, AgentResult


class MockAdapter(AgentAdapter):
    name = "mock"

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            installed=True,
            authenticated=True,
            interactive=True,
            structured_output=True,
            streaming=True,
            resume=True,
            interrupt=True,
            command="mock",
            version="1.0",
        )

    def build_command(self, prompt: str, *, writable: bool, mode: str = "agent") -> list[str]:
        return ["mock", prompt]

    def run(self, prompt: str, *, writable: bool = False, mode: str = "agent", on_event=None, env=None) -> AgentResult:
        if "PRODUCT_DISCOVERY_JSON" in prompt:
            text = json.dumps({"name":"Demo Product","summary":"Generated from the PRD as a notes service a user can create and list against.","users":["User"],"capabilities":["Core workflow"],"workflows":["User completes workflow"],"constraints":[],"assumptions":[],"open_questions":[]})
        elif "ARCHITECTURE_DECISIONS_JSON" in prompt:
            payload = [
                {
                    "id": "ARCH-001",
                    "category": "backend",
                    "question": "Which backend framework should the project use?",
                    "rationale": "Choose a maintainable application backend.",
                    "requirements": ["API", "testing"],
                    "options": [
                        {"name": "FastAPI", "summary": "Python async API framework", "strengths": ["Python ecosystem"], "tradeoffs": ["Less opinionated"], "fit": "high"},
                        {"name": "Django", "summary": "Batteries-included Python framework", "strengths": ["Admin and ORM"], "tradeoffs": ["Heavier"], "fit": "medium"},
                    ],
                    "recommendation": "FastAPI",
                    "recommendation_reason": "Good fit for a Python-first service.",
                }
            ]
            text = json.dumps(payload)
        elif "SPEC_BUNDLE_JSON" in prompt:
            payload = {
                "product": {
                    "name": "Demo Product",
                    "summary": "Generated from the PRD as a notes service a user can create and list against.",
                    "users": ["User"],
                    "capabilities": ["Core workflow"],
                    "workflows": ["User completes core workflow"],
                    "constraints": [],
                    "assumptions": [],
                    "open_questions": [],
                },
                "requirements": [
                    {
                        "id": "REQ-001",
                        "title": "Core workflow",
                        "statement": "The system shall support the core workflow so a user can complete the primary notes path.",
                        "kind": "functional",
                        "priority": "must",
                        "source": "PRD",
                        "acceptance_criteria": ["AC-001: Core workflow succeeds."],
                    }
                ],
                "architecture_summary": "FastAPI service using the selected architecture decisions.",
                "features": [
                    {
                        "id": "F001",
                        "name": "Foundation",
                        "summary": "Stand up the service foundation so a user can create and list notes through a tested HTTP API.",
                        "requirements": ["REQ-001"],
                        "depends_on": [],
                        "invariants": ["Notes persist for the lifetime of the process and list returns created records."],
                        "non_goals": ["Multi-user auth and search are out of scope for this foundation."],
                        "test_matrix": ["Create note happy path", "List empty then populated", "Invalid payload rejected"],
                        "api_contract": "POST /notes {title} -> 201; GET /notes -> 200 list. Errors: 400 validation.",
                        "ux_contract": "",
                        "target_files": ["app.py", "tests/test_notes.py"],
                        "tasks": [
                            {
                                "id": "TASK-F001-001",
                                "feature_id": "F001",
                                "title": "Implement foundation",
                                "description": "Add the notes HTTP handlers, persistence, and unit tests that prove create/list plus invalid payload rejection.",
                                "implements": ["REQ-001"],
                                "depends_on": [],
                                "verification": ["Tests pass for create, list, and invalid payload"],
                            }
                        ],
                    }
                ],
                "test_strategy": ["Unit tests", "Integration tests"],
                "security_principles": ["Least privilege"],
                "release_criteria": ["All must requirements verified"],
            }
            text = json.dumps(payload)
        elif "RECONCILE_CHANGE_JSON" in prompt:
            import re
            # Deterministic test fixture: preserve current spec payload if present.
            bundle = {
                "product": {"name":"Demo Product","summary":"Generated from the PRD as a notes service a user can create and list against.","users":["User"],"capabilities":["Core workflow"],"workflows":["User completes core workflow"],"constraints":[],"assumptions":[],"open_questions":[]},
                "requirements": [{"id":"REQ-001","title":"Core workflow","statement":"The system shall support the core workflow so a user can complete the primary notes path.","kind":"functional","priority":"must","source":"PRD","acceptance_criteria":["AC-001: Core workflow succeeds."]}],
                "architecture_summary":"FastAPI service using the selected architecture decisions.",
                "features": [{"id":"F001","name":"Foundation","summary":"Stand up the service foundation so a user can create and list notes through a tested HTTP API.","requirements":["REQ-001"],"depends_on":[],"invariants":["Notes persist for the lifetime of the process and list returns created records."],"non_goals":["Multi-user auth and search are out of scope for this foundation."],"test_matrix":["Create note happy path","List empty then populated","Invalid payload rejected"],"api_contract":"POST /notes {title} -> 201; GET /notes -> 200 list.","tasks":[{"id":"TASK-F001-001","feature_id":"F001","title":"Implement foundation","description":"Add the notes HTTP handlers, persistence, and unit tests that prove create/list plus invalid payload rejection.","implements":["REQ-001"],"depends_on":[],"verification":["Tests pass for create, list, and invalid payload"]}]}],
                "test_strategy":["Unit tests","Integration tests"],"security_principles":["Least privilege"],"release_criteria":["All must requirements verified"]
            }
            arch = [{"id":"ARCH-001","category":"backend","question":"Which backend framework should the project use?","rationale":"Choose a maintainable application backend.","requirements":["API","testing"],"options":[{"name":"FastAPI","summary":"Python async API framework","strengths":["Python ecosystem"],"tradeoffs":["Less opinionated"],"fit":"high"}],"recommendation":"FastAPI","recommendation_reason":"Good fit for a Python-first service.","selected":"FastAPI","selected_reason":"Approved","status":"selected"}]
            text = json.dumps({"bundle": bundle, "architecture_decisions": arch, "invalidate_tasks": ["TASK-F001-001"], "notes": ["Applied approved change"]})
        elif "CHANGE_ANALYSIS_JSON" in prompt:
            text = json.dumps({
                "classification": "implementation_defect",
                "affected_requirements": ["REQ-001"],
                "affected_features": ["F001"],
                "affected_tasks": ["TASK-F001-001"],
                "proposed_changes": ["Repair implementation to satisfy existing acceptance criteria"],
                "requires_approval": False,
            })
        elif "TASK_REVIEW_JSON" in prompt:
            text = json.dumps({"status": "pass", "findings": [], "summary": "Implementation satisfies the task."})
        elif "TASK_IMPLEMENTATION" in prompt:
            text = "Task implementation completed."
        elif "ASK_ARCHITECT" in prompt:
            text = "Architect response based on the current PRD, selected architecture, specs, and repository state."
        else:
            text = "Mock agent response"
        event = AgentEvent(type="mock", message=text)
        if on_event:
            on_event(event)
        return AgentResult(success=True, text=text, events=[event])
