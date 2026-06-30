# Agent Instructions Template

Use this template in your own homelab repository as `AGENTS.md`, `CLAUDE.md`,
`.cursorrules`, or the equivalent instruction file for your agent client.

It gives agents a practical operating contract:

- read inventory and policy first;
- observe before planning;
- never treat a plan as approval;
- gate writes, restarts, credential access, firewall exposure, and destructive
  actions;
- verify changes with external signals;
- keep secrets out of chat and files.

Copy `AGENTS.md` into your homelab repo and replace placeholder paths with your
actual inventory, diagnostics, and policy locations.
