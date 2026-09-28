---
name: agent-system-review
description: Audit an LLM or agent change across prompts, retrieval, tools, memory, orchestration, evaluation, and output handling. Use for AI agents, MCP tools, RAG, model providers, or long-running agent workflows. Do not use for unrelated deterministic code.
routing:
  phases: [implement, repair, review]
  any: [llm, agent, prompt, tool call, mcp, rag, retrieval, model provider, memory, eval, structured output]
---

# Agent System Review

## Layered contract

Inspect only the layers touched by the bounded task, but trace the behavior end to end:

1. Input and identity: tenant, user, session, and request boundaries.
2. Prompt assembly: approved instructions remain distinct from untrusted retrieved content.
3. Retrieval and memory: provenance, freshness, authorization, retention, and deletion.
4. Model boundary: versioned prompt/schema, timeout, cancellation, budget, and provider fallback.
5. Tool boundary: allowlist, argument validation, least privilege, idempotency, and human approval.
6. Orchestration: bounded loops, durable state, restart semantics, and explicit unknown outcomes.
7. Output: schema validation, safe rendering, citations/evidence, and refusal/fallback behavior.
8. Evaluation: deterministic fakes in CI plus adversarial and opt-in live qualification.

## Blocking failures

- The model can grant itself authority or write controller-owned state.
- Retrieved content can override governing instructions.
- Cross-user/session data can enter prompts, memory, tools, or output.
- A repair loop hides persistent failure or exceeds its budget.
- Unvalidated model output triggers a state-changing operation.
