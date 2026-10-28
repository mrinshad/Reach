# Agent Orchestration & Coordination Guide

This guide establishes how Intent, Impeccable, Ponytail, Graphify, and Change Tracking coordinate across the product development lifecycle.

## 1. The 5-Phase Coordination Lifecycle

```
[Phase 1: Strategy & Structure] (Intent UX: /strategize, /wireframe, /articulate)
               │
               ▼
[Phase 2: Visual Craft & Design Tokens] (Impeccable UI: /polish, /audit, design tokens)
               │
               ▼
[Phase 3: Minimalist Implementation] (Ponytail Code: 7-Step Ladder, /ponytail)
               │
               ▼
[Phase 4: Knowledge Graph Synchronization] (Graphify: AST update, dependency extraction)
               │
               ▼
[Phase 5: Change Audit & Decision Records] (Track Changes: CHANGELOG.md, PROJECT_STATE.md, ADRs)
```

## 2. Specialized Subagents

| Subagent | Role | Framework | Focus Area |
| :--- | :--- | :--- | :--- |
| **`ux-strategist`** | UX Strategist | Intent | User journeys, wireframing, content articulation |
| **`ui-craftsman`** | UI Craftsman | Impeccable | Visual polish, typography, tokens, contrast check |
| **`ponytail-engineer`** | Minimalist Dev | Ponytail | 7-step Necessity Ladder, clean code, native APIs |
| **`system-auditor`** | Change Auditor | Change Tracking + Graphify | Git diff audit, CHANGELOG.md, PROJECT_STATE.md, ADRs |
