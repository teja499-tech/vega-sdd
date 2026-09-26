# Agent instructions for the Vega SDD source repository

This is the framework's own source repository. Read README.md, pyproject.toml and the relevant document in docs/ before modifying code.

- Keep `sdd` as the public command. The Python module `universal_sdd` remains for compatibility until a deliberate migration.
- Keep changes scoped to an issue or user request. Preserve stable IDs, recovery state and append-only journal semantics.
- Test controller changes with the mock adapter. Do not call a real agent provider in CI.
- Preserve approvals for requirement and architecture changes. Project-specific checks and deployment mechanisms stay configurable.
- Update CHANGELOG.md and human-facing docs when behavior changes; do not imply live-agent or hosted delivery is verified unless tested.
- Never commit tokens, generated audit workspaces, build artifacts or project runtime state.
