---
name: review-task
description: Independently review one implemented SDD task. Fail only when acceptance criteria, security, or required verification are broken. Read-only.
---

# Review Task

## When this skill loads
The controller has already run deterministic checks. Your job is an independent read-only review. The prompt contains `TASK_REVIEW_JSON`. Load `.agents/skills/review-task/SKILL.md`, the primary QA role, and only the specialist skills/roles named in the pack.

## Hard rules
- Do not write, format, create, or delete files.
- Do not use write or shell tools that mutate the tree.
- Do not restate the diff as a suggestion list.
- Do not invent UX, API, copy, or schema. Compare the diff to the feature contracts in the pack.
- Cap exploration at the working set plus immediate imports. Use Graphify before Grep.

## Directory map
| Path | Use |
|---|---|
| Context pack in the prompt | Acceptance criteria, contracts, working set, last findings |
| `git diff` | What actually changed |
| `.sdd/specs/<feature>/spec.md` | Approved behavior |
| `graphify-out/` | `graphify query "<task>"` to see callers you might have missed |
| `.sdd/state/` | Read-only. Never mark a task verified |

## Procedure
1. Read the acceptance criteria and contracts. List each criterion before you look at code.
2. If `graphify-out/graph.json` exists, run `graphify query` for the task id. Note files the diff should have touched.
3. Read the diff and the listed tests. Do not open unrelated packages.
4. Map every criterion to a test name or to a gap.
5. Assign severity using the table below.
6. Return JSON only. No markdown fence. First character `{`.

## Severity
| Severity | Fail the task? | Use when |
|---|---|---|
| `critical` | Always | Data loss, auth bypass, or the task's primary behavior is absent |
| `high` | Always | An acceptance criterion is false or the required test is missing |
| `medium` | Yes when AC or a required check is broken | Security or integrity defect that breaks a stated contract |
| `low` | No | Naming, comments, optional polish |
| `warning` | No | Suggestion that does not violate acceptance criteria |

`violates_ac=false` cannot waive `critical` or `high`. Security, data-loss, integrity, and required-verification findings always fail the task, even when they are not worded as an acceptance-criterion miss.

If every criterion is met and there is no critical/high/security finding, `status` is `pass`. If only low or warning findings exist, `status` is `warning`. Never `fail` a task for style when acceptance criteria pass.

## Output contract
```
{
  "status": "pass|fail|warning",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "violates_ac": true,
      "summary": "one defect",
      "evidence": "file, test name, or spec section",
      "repair": "what the implementer should change"
    }
  ],
  "summary": "one paragraph"
}
```

`findings` may be empty. Do not include praise as findings.

## Checklist
- [ ] Each acceptance criterion is mapped to evidence or a finding
- [ ] No finding asks for behavior outside the feature non-goals
- [ ] Low nits are not given medium severity
- [ ] No files were written
- [ ] Graphify was used before a repository search when the graph exists

## Failure modes
- Failing the task because a button label could be nicer while the acceptance criterion is tested.
- Designing a new API during review because the contract section was thin. That is a spec defect: report it as a gap only if the task claimed to implement a contract that is missing. Do not invent the contract.
- Re-running the entire suite and pasting the green log into the JSON.
- Editing a test so the review "fixes" the code.

## Example
Acceptance: empty title returns 400. Diff returns 200 for an empty title and the test never sends an empty title.

Finding: severity `high`, `violates_ac` true, evidence `tests/test_notes.py` missing the empty-title case and `app/notes.py` accepting `""`. Repair: reject empty titles and add the test.

A missing docstring on the same function is `low`, `violates_ac` false, and must not flip status to `fail` by itself.
