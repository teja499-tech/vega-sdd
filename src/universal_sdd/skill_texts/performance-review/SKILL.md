---
name: performance-review
description: Establish and verify measurable latency, throughput, memory, token, or cost budgets. Use for performance-sensitive paths and optimization work. Do not optimize without a representative baseline.
routing:
  phases: [implement, repair, review]
  any: [performance, latency, throughput, benchmark, load test, memory, token efficiency, cost budget, cache, bottleneck]
---

# Performance Review

## Workflow

1. Name the workload, environment, input size, concurrency, and metric before changing code.
2. Capture a reproducible baseline and retain the command/output as evidence.
3. Change the smallest relevant path; preserve correctness and failure semantics.
4. Re-run the same benchmark and deterministic regression tests.
5. Report distributions where possible (at least median and tail), not a single best run.

## Guardrails

- No invented speedup, cost, or capacity claim.
- No unbounded cache, queue, result set, prompt, or log.
- No benchmark that excludes the actual bottleneck or uses a different workload after the change.
- A performance win that breaks acceptance criteria fails review.
