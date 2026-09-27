---
name: data-model
description: Define entities, constraints, indexes, and migrations before persistence work. Use when a task adds tables, documents, or schema changes.
---

# Data Model

## Goal
Name the stored shape so implementers do not invent columns during a task.

## Directory map
- Feature spec and `DATABASE_DESIGN` design document under `.sdd/docs/`
- Migrations live in the application tree named by `target_files`
- Find current models with `graphify explain "<entity>"`

## Required output
- Entities and relationships
- Fields: type, nullability, uniqueness
- Indexes and the query that needs each index
- PII, retention, and deletion
- Migration and rollback (expand/contract when a change is destructive)

## Procedure
1. Start from the API or UX fields that must be stored. Mark derived fields as not stored.
2. Match existing naming in the repository. Do not introduce a second notes table.
3. Write the model into the feature spec before `implement-task` runs.
4. Every mutation in the test matrix has fixture rows.
5. Destructive migrations are called out in non-goals or in an explicit migration task.

## Checklist
- [ ] Each API field is stored or explicitly derived
- [ ] Uniqueness matches the product rule
- [ ] Rollback is described for migrations
- [ ] Tests do not depend on production data

## Failure modes
- Adding a column in the handler because the spec never listed it.
- A migration with no down path presented as a routine task.
- Storing provider secrets in the same table as user content.

## Example
`Note`: `id` uuid primary key, `title` text not null, `owner_id` not null, `created_at` timestamptz. Unique none. Index `(owner_id, created_at desc)` for the list query. Delete removes the row. No soft-delete in this feature.
