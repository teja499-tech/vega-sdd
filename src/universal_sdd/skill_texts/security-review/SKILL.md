---
name: security-review
description: Review one bounded change for auth, secrets, injection, and data exposure. Use when the task touches security. Return findings with severity. Do not redesign the threat model.
routing:
  phases: [implement, repair, review]
  any: [auth, authenticated, authorization, authentication, secret, security, injection, tenant, permission, credential, token]
---

# Security Review

## Scope
The working set and the trust boundary in the threat-model skill or `.sdd/docs/SECURITY.md`. Do not audit the whole repository.

## Directory map
- Diff and working-set files
- Threat model in the feature spec
- `graphify path` from the new entry point to the sink (database, provider, shell)

## Checklist
1. Authn and authz on new routes and jobs, matching `api_contract`
2. Secrets only in env or the approved secret store
3. Input validation and injection (SQL, command, path, SSRF)
4. Data exposure in errors, logs, and traces
5. Dependency and privilege changes

## Severity
Same as review-task. Medium and above that break the security principle or an acceptance criterion fail the task. Style comments do not.

## Procedure
1. Read the threat model. If it is missing for a secret- or auth-touching task, the finding is that the spec is incomplete, not a new design you invent.
2. Trace the diff with Graphify from entry to sink.
3. Return JSON findings with evidence and a repair.

## Failure modes
- Demanding a new identity provider during review.
- Ignoring a logged API key because tests passed.
- Expanding the review to unrelated modules.

## Example
The notes handler logs the OpenRouter request body. Severity high. Evidence `app/provider.py` log line. Repair: log the status code and request id only.
