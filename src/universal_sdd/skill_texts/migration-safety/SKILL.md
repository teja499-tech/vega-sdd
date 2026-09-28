---
name: migration-safety
description: Design and verify forward-safe data or API migrations with compatibility, backfill, rollback, and observability. Use when schemas, persistent formats, or public contracts change. Do not use for a new isolated table with no compatibility risk.
routing:
  phases: [implement, repair, review]
  any: [migration, backfill, schema change, data conversion, compatibility window, rollback]
---

# Migration Safety

## Workflow

1. Record the old and new contracts and the compatibility window.
2. Prefer expand/migrate/contract for live systems.
3. Make backfills resumable, idempotent, bounded, and observable.
4. Separate application rollback from irreversible data rollback; prefer forward repair when needed.
5. Test mixed-version behavior, partial progress, restart, and large-data bounds.

## Evidence

Name the migration command, dry-run or fixture, compatibility test, and recovery procedure. Never treat a generated migration file as proof it is safe on production-scale data.
