# Agent Runtime Service Templates

These templates help run local agents as ordinary, observable services. They are
examples, not drop-in unit files.

Recommended defaults:

- create a dedicated non-root service user;
- store secrets outside the unit file, usually in a protected env file or runtime
  secret store;
- start with read-only MCP servers and the default guardrail policy;
- keep logs in the host service manager so another agent can inspect failures;
- require manual approval for agent restarts, policy edits, credential access, and
  any host write.

Templates:

- `systemd/openclaw.service.example`
- `systemd/hermes.service.example`
- `launchd/com.agentic-homelab.agent.example.plist`
