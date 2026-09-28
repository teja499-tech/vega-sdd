---
name: reliability-review
description: Verify timeouts, retries, idempotency, cancellation, concurrency, and degraded operation. Use when a task changes external calls, queues, background work, or recovery behavior. Do not use for ordinary pure functions.
routing:
  phases: [implement, repair, review]
  any: [timeout, retry, retries, circuit breaker, cancellation, idempotency, concurrency, queue, recovery, fallback, failover]
---

# Reliability Review

## Contract

Review the bounded task against its approved acceptance criteria and architecture. Do not add infrastructure the feature does not need.

1. Put an explicit timeout on every network, process, queue, and model call.
2. Bound retries and define which failures are retryable. Use jittered backoff where synchronized retries are a risk.
3. Make retried mutations idempotent with a stable operation key or durable state transition.
4. Preserve cancellation and deadlines across nested calls.
5. Define partial-failure, restart, and degraded-mode behavior.
6. Emit evidence that distinguishes success, rejection, timeout, retry exhaustion, and unknown outcome.

## Failure modes

- Infinite retry or repair loops.
- Retrying non-idempotent writes without a key.
- Catch-all fallbacks that silently return stale or unsafe data.
- Marking an external operation failed when its outcome is actually unknown.

Return concrete file/test evidence. Never claim resilience that was not exercised.
