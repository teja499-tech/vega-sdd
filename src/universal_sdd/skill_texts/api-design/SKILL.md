---
name: api-design
description: Lock HTTP or RPC contracts before implementation. Use when a feature adds routes, request bodies, or error codes. Reviewers check this contract; they do not invent one.
---

# API Design

## Goal
Write a route table the implementer can code and the reviewer can diff against.

## Directory map
- Feature field: `api_contract` on the feature in `.sdd/state/spec-bundle.yaml` and `.sdd/specs/<feature>/spec.md`
- Human projection: `.sdd/docs/API_DESIGN.md` (descriptive; it does not approve new routes)
- Callers and handlers: find them with `graphify query "route <path>"` after the graph exists

## Required output
- Method and path
- Authn and authz (named role or "public", never "add later")
- Request fields, types, required, validation
- Success status and response fields
- Closed error catalog: status, stable code, when it is returned
- Idempotency and pagination when the operation needs them
- Compatibility note if an existing client would break

## Procedure
1. Start from the requirement acceptance criteria, not from a framework tutorial.
2. Prefer resources that already exist. `graphify explain` the current handler before adding a parallel one.
3. Write the table into `api_contract`. Include one realistic example, not `foo`.
4. Map each error to a test in the feature test matrix.
5. Hand the table to implement-task. Implementation does not rename fields.

## Checklist
- [ ] Every new route has authz
- [ ] Errors are a closed set
- [ ] Breaking changes name the compatibility window
- [ ] Examples use the project's real identifiers

## Failure modes
- A reviewer inventing a JSON shape during repair because this section was empty.
- Documenting a route that no requirement asked for.
- Using 200 for every failure.

## Example
`POST /notes` authn user. Body `title` string required, 1–200 chars. `201` `{id,title,created_at}`. `400` code `title_required` when title is empty. `401` when the session is missing.
