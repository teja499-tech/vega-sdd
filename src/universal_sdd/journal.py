from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import utcnow


class Journal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: str, **payload: Any) -> dict[str, Any]:
        # Store task intent at event time so later spec edits cannot rewrite history.
        from .storage import SDDPaths, load_yaml
        from .history import git_context, render_history
        paths = SDDPaths(self.path.parent.parent.parent)
        if self.path == paths.event_log and event in {"project_initialized", "task_started", "task_verified", "change_applied", "implementation_repair_created"}:
            payload.setdefault("git", git_context(paths.root))
            for feature in load_yaml(paths.features_file, []) or []:
                for task in feature.get("tasks", []):
                    if task["id"] == payload.get("task"):
                        payload.setdefault("task_title", task["title"])
                        payload.setdefault("task_description", task.get("description", ""))
                        payload.setdefault("requirements", task.get("implements", []))
        if self.path == paths.event_log and event in {"project_initialized", "change_applied", "documentation_updated", "task_verified"}:
            revisions = load_yaml(paths.state / "spec-history.yaml", []) or []
            if revisions:
                payload.setdefault("spec_revision", revisions[-1]["revision"])
                payload.setdefault("spec_transition", revisions[-1]["transition"])
        record = {"timestamp": utcnow(), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.path == paths.event_log:
            if event == "task_verified":
                from .history import discover_task_commits
                started = next((row for row in reversed(self.read()) if row.get("event") == "task_started" and row.get("task") == payload.get("task")), {})
                discover_task_commits(paths, payload["task"], started.get("git", {}).get("head"))
            render_history(paths)
            if event in {"task_verified", "implementation_repair_created", "change_applied"} and paths.spec_bundle_file.exists():
                from .documentation import render_docs
                render_docs(paths)
        return record

    def read(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"event": "malformed", "raw": line})
        return rows[-limit:] if limit else rows
