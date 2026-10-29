---
name: track-changes
description: Use this skill when completing a feature, refactor, or architectural change to update CHANGELOG.md, synchronize PROJECT_STATE.md, or author an Architecture Decision Record (ADR).
---

# Change Tracking & Audit Skill

This skill enforces systematic tracking of project changes, maintaining an accurate audit trail as the project evolves.

## Workflow Steps:
1. **Inspect Git Diff**: Run `git status --short` and `git diff --stat`.
2. **Update CHANGELOG.md**: Add an entry under `## [Unreleased]` categorized as Added, Changed, Fixed, Removed, or Security.
3. **Synchronize PROJECT_STATE.md**: Update active milestone statuses and log any deliberate shortcuts (`shortcut:` / `ponytail:`) in the debt ledger.
4. **Record ADR (if architectural decision was made)**: Create `docs/adr/000X-title.md` following `docs/adr/README.md`.
5. **Update Knowledge Graph**: Run `graphify update .` if code files changed.
