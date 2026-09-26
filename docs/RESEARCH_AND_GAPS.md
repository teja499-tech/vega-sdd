# Cross-project research and disposition — 2026-09-26

This is a synthesis of current primary guidance and the original framework audit. The common lifecycle is portable; execution, validation and governance differ by project. The 0.1.2 controller already produced human design documents, specs, traceability, changelog and commit links; the main gaps were executable cross-project contracts, repo review controls, CI export and release/operation recovery.

| Area | Reference | Implemented consequence | Project-specific work |
| --- | --- | --- | --- |
| Git review and branch rules | [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [gh PR merge](https://cli.github.com/manual/gh_pr_merge) | Guard integration branches; require fresh status/review and exact head | Set real branch/ruleset/owner policies |
| Delivery approvals | [GitHub environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments) | Explicit environment approvals and artifact promotion | Provision secrets, identities, host restrictions |
| Monorepos | [Nx affected](https://nx.dev/docs/features/ci-features/affected) | Ordered component graph and conservative full release checks | Large graph optimization and distributed versioning |
| Library/SDK | [PyPA recommendations](https://packaging.python.org/en/latest/guides/tool-recommendations/) | API compatibility check and immutable package artifact | Supported runtime matrix/publishing |
| Data pipelines | [Airflow best practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html), [dbt data tests](https://docs.getdbt.com/docs/build/data-tests) | Replay/data-quality gates, explicit idempotency | Lineage, schema drift, backfills, data retention |
| Infrastructure | [Terraform plan/apply](https://developer.hashicorp.com/terraform/cli/commands/plan) | Plan check and saved artifact contract | State locking, drift, destructiveness/approval |
| ML | [MLflow model registry](https://mlflow.org/docs/latest/ml/model-registry/) | Evaluation gate and release version | Data/model/prompt provenance, threshold monitoring |
| Mobile and desktop | [Android release preparation](https://developer.android.com/studio/publish/preparing), [Electron code signing](https://www.electronjs.org/docs/latest/tutorial/code-signing) | Device/platform profiles | Device/OS matrix, signing, store/installer distribution |
| Alternate hosts | [GitLab MR pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/), [Azure branch policies](https://learn.microsoft.com/en-us/azure/devops/repos/git/branch-policies) | Include/template export plus provider command hooks | Build/merge rule administration and actual host adapter tests |
| Coding agents | [Codex CLI](https://developers.openai.com/codex/cli/reference/), [Cursor permissions](https://cursor.com/docs/cli/reference/permissions), [Claude CLI](https://code.claude.com/docs/en/cli-reference) | Explicit Codex sandbox flags, bounded runs, protected state | Qualify current authenticated agent and OS sandbox |

Web/service, CLI, documentation and embedded profiles require browser/contract, exit-code, rendered-link and target-hardware checks respectively. These categories are enforced as executable project commands or visible waivers; a label alone cannot certify a stack.

Open obligations remain deliberate: no native GitLab/Azure PR implementation, no automatic cloud setup or signing keys, no complete mobile/desktop/embedded/ML platform certification, no fleet polling/cost governor, no signed audit attestations, no generic migration/backup/observability or compliance certification. The project owner must select meaningful toolchains, check coverage, reviewers, incident ownership, vulnerability contacts, retention and rollback. A populated Markdown design document is a reading aid, not proof the architecture was independently validated.

See [the lifecycle guide](PROJECT_LIFECYCLE.md) for operation and [verification evidence](VERIFICATION_0.2.0.md) for tested boundaries.
