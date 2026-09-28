"""Review findings fail a task only when they break acceptance criteria."""
from __future__ import annotations

from typing import Any

BLOCKING_SEVERITIES = {"critical", "high", "medium"}
ALWAYS_BLOCKING_SEVERITIES = {"critical", "high"}
NON_BLOCKING_SEVERITIES = {"low", "warning", "info", "nit"}
ALWAYS_BLOCKING_CATEGORIES = {
    "security",
    "data-loss",
    "data_loss",
    "integrity",
    "required-verification",
    "required_verification",
}


def _severity(finding: dict[str, Any]) -> str:
    return str(finding.get("severity") or "").strip().lower()


def _category(finding: dict[str, Any]) -> str:
    for key in ("category", "kind", "type"):
        value = str(finding.get(key) or "").strip().lower()
        if value:
            return value
    blob = " ".join(
        str(finding.get(key) or "")
        for key in ("summary", "evidence", "repair")
    ).lower()
    for token in ALWAYS_BLOCKING_CATEGORIES:
        if token.replace("_", " ") in blob or token.replace("-", " ") in blob:
            return token
    return ""


def _explicit_false(value: Any) -> bool:
    return value is False or str(value).strip().lower() in {"false", "no", "0"}


def finding_blocks(finding: Any) -> bool:
    """Return True when a finding must fail the task."""
    if not isinstance(finding, dict):
        return True
    severity = _severity(finding)
    if severity in ALWAYS_BLOCKING_SEVERITIES:
        return True
    if _category(finding) in ALWAYS_BLOCKING_CATEGORIES:
        return True
    if severity in NON_BLOCKING_SEVERITIES:
        return False
    if _explicit_false(finding.get("violates_ac")):
        return False
    if severity in BLOCKING_SEVERITIES:
        return True
    # Missing severity: treat as blocking so deterministic check failures still fail.
    return True


def apply_review_policy(review_data: dict[str, Any]) -> dict[str, Any]:
    """Downgrade AC-met low/warning nits so they cannot fail a task."""
    findings = [f for f in (review_data.get("findings") or [])]
    blocking = [f for f in findings if finding_blocks(f)]
    warnings = [f for f in findings if not finding_blocks(f)]
    status = str(review_data.get("status") or "fail")
    if blocking:
        status = "fail"
    elif status == "fail" and findings and not blocking:
        status = "warning"
    elif status == "fail" and not findings:
        status = "fail"
    elif warnings and status == "pass":
        status = "warning"
    result = dict(review_data)
    result["status"] = status
    result["findings"] = blocking
    result["warnings"] = warnings
    return result


def review_allows_progress(review_data: dict[str, Any]) -> bool:
    return str(review_data.get("status") or "") in {"pass", "warning"}
