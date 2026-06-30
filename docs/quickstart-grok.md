# Quickstart: Grok

Use this repo as a reference catalog for homelab tasks and safety policy. Start
with read-only inventory, then use the examples to shape exact prompts and
approval boundaries.

## Recommended Flow

1. Read `docs/quickstart.md`.
2. Read `docs/safety-model.md` and `docs/action-risk-matrix.md`.
3. Use `docs/workflow-chooser.md` to pick a workflow from the inventory shape.
4. Ask for a plan with uncertainty, risks, rollback, and verification.
5. Run any actual tool execution through a client with MCP guardrails and human
   approval gates.

## Starter Prompt

```text
Use this repo as a safety reference for homelab maintenance. Do not assume write
permission. Given my inventory summary and chosen workflow, produce a read-only
triage plan, approval gates, and external verifiers. Do not include secrets.
```

## Grok-Specific Notes

- Treat Grok as planning/reference unless connected through a guarded runtime.
- Do not paste secrets, private diagnostics, or full config dumps.
- Convert advice into an explicit change plan before any other agent executes it.
