# Reach Project Documentation Agent Guide (`docs/`)

This directory contains high-level architecture designs, system workflow diagrams, account safety guidelines, and milestone tracking documentation for Reach.

---

## Documentation Directory Matrix

| Document | Description | Key Content Areas |
|---|---|---|
| [`file_architecture.md`](file:///Users/apple/Byten/linkedInScrapper/docs/file_architecture.md) | Comprehensive structural map of the entire repository. | Full directory tree, subsystem tables, backend routers, database schemas, frontend asset mappings, and architectural diagrams. |
| [`workflows.md`](file:///Users/apple/Byten/linkedInScrapper/docs/workflows.md) | End-to-end user workflows and operational lifecycle diagrams. | Multi-platform crawling, sequential task queuing, AI Custom GPT email drafting, interactive review, Gmail dispatch, spam flagging, and mobile push notifications. |
| [`implementation_plan.md`](file:///Users/apple/Byten/linkedInScrapper/docs/implementation_plan.md) | Development roadmap, milestone tracker, and safety standards. | Account safety pacing rules, Headless mode configuration, completed architectural milestones (1 through 7), and ongoing enhancement roadmaps. |

---

## Agent Directives for Documentation

1. **Accuracy with Codebase**: Whenever directories, endpoints, database fields, or UI partials change, immediately update [`docs/file_architecture.md`](file:///Users/apple/Byten/linkedInScrapper/docs/file_architecture.md) and [`README.md`](file:///Users/apple/Byten/linkedInScrapper/README.md).
2. **Apply Link Directives**: The user explicitly rolled back the apply link button. Do NOT document application link buttons as active UI components.
