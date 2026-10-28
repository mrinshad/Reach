# ADR 0001: Adoption of Byten Agentic Engineering & Design System

## Status
Accepted

## Context
As Reach scales its autonomous outreach and screening capabilities, development involves multiple specialized workflows including UI/UX enhancements, background crawler services, relational database storage, and AI prompts. To maintain high code discipline, eliminate generic "AI slop", prevent architecture bloat, keep an auditable change history, and preserve codebase comprehension across AI coding sessions, a standardized engineering and design governance system is required.

## Decision
We adopt the **Byten Agentic Engineering & Design System** across the entire Reach repository:

1. **UX Strategy (Intent)**: Guide user journeys, wireframing, and content articulation before UI execution.
2. **UI & UX Craftsmanship (Impeccable)**: Eliminate unjustified gradients, prevent card clutter, enforce WCAG AA contrast compliance, and align with design tokens.
3. **Code Discipline (Ponytail)**: Apply the 7-Step Necessity Ladder (YAGNI, codebase reuse, standard library, native platform features, dependency reuse, clean minimalism). Mark deliberate technical simplifications with `shortcut:` or `ponytail:`.
4. **Knowledge Graph (Graphify)**: Maintain an AST knowledge graph at `graphify-out/` to rapidly understand cross-module dependencies and architecture.
5. **Change Tracking & Auditability**: Maintain `CHANGELOG.md` under `## [Unreleased]`, maintain `PROJECT_STATE.md` with active milestone statuses and technical debt, and document structural changes via Architecture Decision Records (`docs/adr/`).
6. **IDE / Codex Hooks**: Enforce UI design checks on file edits and agent completion via `.codex/hooks.json`.

## Consequences
- **Positive**:
  - Consistent, high-signal UI design adhering to design tokens.
  - Minimalist, maintainable code avoiding premature abstractions or redundant dependencies.
  - Clear auditability of architectural shifts and project milestones.
  - Fast context retrieval via the AST knowledge graph.
- **Negative / Trade-offs**:
  - Additional governance overhead requiring agents to synchronize changelogs, project state, and knowledge graphs.
