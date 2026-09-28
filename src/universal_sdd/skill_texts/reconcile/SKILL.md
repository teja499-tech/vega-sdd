---
name: reconcile
description: Apply an approved change across the spec bundle, tasks, and design documents while preserving stable ids and journal history. The controller validates and writes state.
---

# Reconcile

## Directory map
- Input: staged files under `.sdd/runtime/reconcile/<cr-id>/bundle.yaml` and `decisions.yaml`
- Output: slice JSON the controller merges, validates, and writes
- History: `.sdd/journal/events.jsonl` is append-only. Do not delete it.

## Procedure
1. Read the staged bundle and decisions. Do not dump them back in your reply.
2. Return only mutated slices (`requirement_updates`, `architecture_decision_updates`, `feature_updates`, `design_document_updates`, optional `product_update` / `architecture_summary`).
3. Preserve requirement, feature, task, and ADR ids unless the item is truly replaced.
4. Add ids only for new items.
5. Update traceability edges and the affected design documents.
6. List every previously verified task whose evidence is no longer valid in `invalidate_tasks`.
7. Leave new and changed tasks unverified.
8. The controller, not this skill, merges slices and writes `.sdd/state` after traceability validation.

## Failure modes
- Returning a full SpecBundle or full ADR list (token burn / hang risk).
- Renumbering stable ids.
- Marking invalidated work verified.
- Dropping design-document gaps that are still unknown.

## Checklist
- [ ] Reply is slice JSON only
- [ ] Unaffected items omitted from the reply
- [ ] Invalidation list covers dependents
- [ ] Open questions created by the change are recorded
