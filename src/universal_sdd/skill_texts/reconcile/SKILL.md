---
name: reconcile
description: Apply an approved change across the spec bundle, tasks, and design documents while preserving stable ids and journal history. The controller validates and writes state.
---

# Reconcile

## Directory map
- Input: current spec bundle and architecture decisions
- Output: a full bundle JSON the controller validates before it replaces files
- History: `.sdd/journal/events.jsonl` is append-only. Do not delete it.

## Procedure
1. Preserve requirement, feature, task, and ADR ids unless the item is truly replaced.
2. Add ids only for new items.
3. Update traceability edges and the affected design documents.
4. List every previously verified task whose evidence is no longer valid in `invalidate_tasks`.
5. Leave new and changed tasks unverified.
6. The controller, not this skill, writes `.sdd/state` after traceability validation.

## Failure modes
- Renumbering stable ids.
- Marking invalidated work verified.
- Dropping design-document gaps that are still unknown.

## Checklist
- [ ] Unaffected task text is unchanged
- [ ] Invalidation list covers dependents
- [ ] Open questions created by the change are recorded
