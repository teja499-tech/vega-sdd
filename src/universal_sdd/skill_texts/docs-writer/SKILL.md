---
name: docs-writer
description: Write the project README and developer guide from compose files, env examples, routes, and approved operations design. Use for documentation tasks, not for feature implementation.
routing:
  phases: [implement, repair, review]
  any: [readme, docs, guide, documentation, runbook]
---

# Docs Writer

## Goal
A new engineer can set up, run, test, and call the system using the README and `.sdd/docs/DEVELOPER_GUIDE.md`.

## Directory map
- Project README at the repository root (do not overwrite an existing enterprise README; the controller only creates one when missing)
- `.sdd/docs/DEVELOPER_GUIDE.md`, `OPERATIONS.md`, `CONTRIBUTING.md`
- Sources you may cite: `compose.yml` or `docker-compose.yml`, `.env.example`, package manifests, route tables, ADRs
- Quality gate: `sdd docs check` fails a thin README and incomplete design sections

## Required README sections
1. What the system is (the product summary, not a slogan)
2. Prerequisites
3. Local setup, including compose when a compose file exists
4. Configuration, including local Ollama and hosted OpenRouter when those providers are in scope
5. How to run tests
6. How to call the API or open the UI
7. Where to read more (developer guide, status)

## Procedure
1. Inspect the sources. Do not invent commands, ports, or owners.
2. Quote commands that exist in the repo. If a command is unknown, write the gap into the design document `gaps` list and keep status `draft`.
3. Distinguish observed behavior from the approved target.
4. `documented` requires every contract heading, sources, and no gaps.
5. Do not put new product scope in a document. Scope changes go through `sdd change`.

## Checklist
- [ ] Setup and test sections exist and are specific
- [ ] Env vars match `.env.example`
- [ ] No "this document does not claim" paragraph standing in for the design
- [ ] Gaps are explicit

## Failure modes
- A reading list instead of setup steps.
- Claiming a filename proves runtime behavior.
- Replacing a README the project already owned.

## Example
README says: copy `.env.example`, `docker compose up`, `pytest -q`, then `POST /notes` with a title. The developer guide points at the same commands and at `sdd ask` for questions.
