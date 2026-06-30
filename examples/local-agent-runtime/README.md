# Example: Local Agent Runtime

Goal: let an agent maintain OpenClaw, Hermes, or similar local runtimes.

## Flow

1. Inspect service status and logs.
2. Check model/runtime configuration.
3. Plan restart or update if needed.
4. Require approval before modifying service files or restarting the runtime.

Machine-readable workflow: `workflow.yaml`.

Service templates live in `templates/agent-runtime/`. Treat the agent runtime as
part of the homelab: observable, least-privileged, and guarded by the same
approval rules as the services it can affect.
