---
name: verify-feature
description: Verify a finished feature against acceptance criteria and deterministic evidence at a feature boundary. Use when the controller runs the feature suite, not for a single task nit.
---

# Verify Feature

## Directory map
- Feature spec and tasks under `.sdd/specs/`
- Evidence under `.sdd/evidence/` and `.sdd/state/verification.yaml`
- Full test command from `.sdd/config.yaml` `test_command` or workspace checks with `run_at: release`

## Procedure
1. Confirm every task in the feature is verified before trusting the feature suite.
2. Run the feature-level suite the controller schedules. Task runs use narrow tests; this pass uses the broader command.
3. Map each requirement to a passing check. Missing evidence is a finding.
4. Low nits stay warnings.

## Failure modes
- Re-running the suite on every task and pasting the green log into the next prompt.
- Marking the feature verified when one task is still failed.

## Checklist
- [ ] Requirement ids map to evidence ids
- [ ] The suite command is the configured one
- [ ] No spec files were edited to force a pass
