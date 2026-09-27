---
name: architecture-design
description: Compare only material architecture options and record the user's selection. Use during the architecture workshop or an architecture change request. Do not choose for the user.
---

# Architecture Design

## Goal
Surface decisions that change data, security, deployment, or cost. Present current options. The operator selects.

## Directory map
- Workshop output: `.sdd/state/architecture-decisions.yaml` and `.sdd/decisions/<id>-<category>.md`
- Index: `.sdd/architecture/decisions.md`
- A decision is selected only when `status` is `selected` and `selected` is set. `deferred` blocks `sdd start` until clarified or explicitly accepted.

## When to open a decision
Open one when persistence, identity, compute, messaging, secrets, or observability is unconstrained, or when the existing repository already forces the choice. Record that constraint as an option. Do not open a decision for a library the PRD does not need.

## Option contract
Each option has `name`, `summary`, `strengths`, `tradeoffs`, and `fit` of high, medium, or low. Recommend one option and say why. The recommendation is not approval.

## Procedure
1. Read the PRD and clarifications.
2. Inspect the repo with `graphify explain` when a graph exists, so you do not propose a stack the code already rejected.
3. Emit only material decisions, each with 2–5 credible options.
4. After the operator selects, the controller writes the ADR. Do not invent product requirements inside the ADR.
5. Deferred decisions are recorded as clarifications. They are not treated as selected.

## Checklist
- [ ] Every option has a tradeoff
- [ ] The recommendation is labeled as a recommendation
- [ ] Existing repo constraints are an option, not a silent default
- [ ] No product requirement was created to justify a technology

## Failure modes
- Asking about Kubernetes for a single-process tool.
- Writing "Approved" on a decision the user deferred.
- Encoding the recommendation into tasks before selection.

## Example
Question: where do model calls run? Options: local Ollama for development, OpenRouter for hosted inference. Recommendation depends on the PRD. The user must select. Tasks may not assume a provider that is still deferred.
