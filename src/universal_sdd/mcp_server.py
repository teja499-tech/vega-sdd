"""Optional stdio MCP server so `sdd ask` / `sdd change` work inside an IDE."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import __version__


def _root() -> Path:
    return Path.cwd()


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "sdd_ask",
            "description": "Read-only project copilot grounded in SDD specs, ADRs, and the project graph.",
            "inputSchema": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
        {
            "name": "sdd_status",
            "description": "Show current SDD run and task progress.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "sdd_change",
            "description": "Analyze an ad-hoc request and preview invalidated tasks. Never applies a change; approval is a separate human CLI step.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                },
                "required": ["description"],
            },
        },
    ]


def _call(name: str, arguments: dict[str, Any]) -> str:
    root = _root()
    if name == "sdd_ask":
        from .orchestrator import ask_project
        return ask_project(root, str(arguments.get("question") or ""))
    if name == "sdd_status":
        from .status import metrics, render_status
        from .storage import SDDPaths
        paths = SDDPaths(root)
        m = metrics(paths)
        return render_status(paths) + f"\nverified={m.tasks_verified}/{m.tasks_total}"
    if name == "sdd_change":
        from .orchestrator import analyze_change
        cr = analyze_change(root, str(arguments.get("description") or ""))
        preview = {
            "id": cr.id,
            "classification": cr.classification,
            "affected_tasks": cr.affected_tasks,
            "affected_features": cr.affected_features,
            "requires_approval": cr.requires_approval,
            "proposed_changes": cr.proposed_changes,
            "status": cr.status,
            "applied": False,
            "next_step": "Review the preview, then run `sdd change --approve` from a human-controlled terminal if you accept the mutation.",
        }
        return json.dumps(preview, indent=2)
    raise ValueError(f"Unknown tool: {name}")


def _respond(message_id: Any, result: Any) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}) + "\n")
    sys.stdout.flush()


def _error(message_id: Any, code: int, message: str) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()


def serve() -> None:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        message_id = message.get("id")
        if method == "initialize":
            _respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "vega-sdd", "version": __version__}})
            continue
        if method == "tools/list":
            _respond(message_id, {"tools": _tools()})
            continue
        if method == "tools/call":
            params = message.get("params") or {}
            try:
                text = _call(params.get("name"), params.get("arguments") or {})
                _respond(message_id, {"content": [{"type": "text", "text": text}]})
            except Exception as exc:
                _error(message_id, 0, str(exc))
            continue
        if message_id is not None:
            _respond(message_id, {})


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
