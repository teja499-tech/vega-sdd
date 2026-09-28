---
name: threat-model
description: Record assets, trust boundaries, and mitigations for one feature before security-sensitive implementation. Use for auth, secrets, uploads, or external model calls.
routing:
  phases: [implement, repair, review]
  any: [auth, secret, threat, security, upload, external model, llm, tenant, permission]
---

# Threat Model

## Goal
A short model of this feature's boundary. Not a generic STRIDE essay.

## Directory map
- Feature spec section and `.sdd/docs/SECURITY.md`
- Secrets never go in git. Point at env or the secret manager the ADR selected.
- Related code: `graphify query "auth"` or the asset named in the feature.

## Required output
- Assets and actors
- Trust boundaries (browser to API, API to model provider, API to database)
- Threats that matter here, each with impact
- Mitigations already required by the security principles
- Residual risk and what is out of scope

## Procedure
1. Limit the model to the feature or change.
2. Reuse mitigations from the approved SECURITY principles. Do not add a control the ADR rejected.
3. Map each mitigation to a test or a config check.
4. Hand the model to security-review. Review verifies mitigations; it does not invent a new model mid-repair.

## Checklist
- [ ] Boundaries are named
- [ ] Secrets have a home that is not the repo
- [ ] Each in-scope threat has a mitigation or an explicit residual risk
- [ ] Out-of-scope threats are listed so reviewers do not expand the task

## Failure modes
- A ten-page threat model that does not name this feature's endpoint.
- Reviewers adding a new auth scheme during a copy fix.
- Logging prompts or tokens to debug a provider call.

## Example
Asset: note body. Boundary: API to OpenRouter. Threat: note text leaves the machine. Mitigation: local Ollama path does not send the note; hosted path is explicit in config and documented. Residual: the operator who selects OpenRouter accepts that send.
