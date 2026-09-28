---
name: e2e-testing
description: Prove critical user journeys at the system boundary with stable assertions and retained failure artifacts. Use for browser, mobile, CLI, or cross-service flows. Do not replace unit tests with E2E tests.
routing:
  phases: [implement, repair, review]
  any: [e2e, end-to-end, browser, user journey, playwright, mobile flow, cli flow]
---

# End-to-End Testing

## Workflow

1. Map each selected acceptance criterion to a user-observable journey.
2. Use the project's approved E2E command and existing conventions.
3. Prefer semantic selectors and condition-based waits; never add fixed sleeps to hide races.
4. Isolate state per test and cover the authorization boundary for multi-user flows.
5. Retain screenshots, traces, logs, or equivalent artifacts on failure without leaking secrets.

## Review rules

- A skipped or quarantined critical journey is a gap, not a pass.
- Retries may diagnose flakiness but may not redefine success.
- Do not claim a live integration passed when only a fake provider ran.
