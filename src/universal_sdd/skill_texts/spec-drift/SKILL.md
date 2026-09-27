---
name: spec-drift
description: Classify a mismatch between approved specs and the code as an implementation defect, a stale spec, or a new change request. Use from sdd change, not to silently rewrite specs.
---

# Spec Drift

## Directory map
- Approved text: `.sdd/product/`, `.sdd/specs/`, ADRs
- Code: Graphify query for the symbol, then the diff
- Change records: `.sdd/changes/`

## Procedure
1. Quote the requirement or contract that disagrees with the code.
2. If the spec is already testable and the code violates it, classification is `implementation_defect`.
3. If the spec is stale relative to an approved ADR, classification is `spec_defect`.
4. If the user wants new behavior, classification is `requirement_change` or `architecture_change` and approval is required.
5. Never edit the spec to match incorrect code.

## Failure modes
- Calling a product change an implementation defect to skip approval.
- Updating tasks to verified inside the proposal.

## Checklist
- [ ] The classification matches the rule above
- [ ] Affected task ids are listed for the invalidation preview
