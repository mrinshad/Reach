# Change Tracking Rules

Every AI agent working in this repository MUST maintain an auditable track of changes:

1. **Keep `CHANGELOG.md` Updated**:
   - For every feature, refactor, UI redesign, or fix, add a bullet point under the `## [Unreleased]` section of `CHANGELOG.md`.
   - Categorize entries accurately (`Added`, `Changed`, `Fixed`, `Removed`, `Security`).

2. **Maintain `PROJECT_STATE.md`**:
   - Keep the milestone statuses and feature matrix updated to reflect the true state of the repository.
   - Record any deliberate technical shortcuts in the debt section.

3. **Record Architectural Decisions**:
   - For non-trivial structural decisions, state management choices, or new external services, write an Architecture Decision Record (ADR) under `docs/adr/`.

4. **Synchronize AST Knowledge Graph**:
   - If files or exports are added, modified, or removed, run:
     ```bash
     graphify update .
     ```
