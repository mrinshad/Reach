# Graphify Knowledge Graph Rules

This project uses an AST knowledge graph at graphify-out/.

Rules:
- For codebase or architecture questions, when `graphify-out/graph.json` exists, first run `graphify query "<question>"` (CLI) or inspect scoped subgraphs.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture reviews or when queries need deeper context.
- After modifying code files in a session, run `graphify update .` to keep the graph current.
