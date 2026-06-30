# Ansible Playbooks

These playbooks are designed for agent-assisted homelab work where discovery should
come before change.

## Read-Only Audit

Copy the inventory example and point it at one or more homelab hosts:

```bash
cp playbooks/ansible/inventory.example.ini inventory.ini
ansible-playbook -i inventory.ini playbooks/ansible/read-only-audit.yml
```

The audit playbook:

- gathers Ansible facts;
- checks uptime, disk usage, memory, failed systemd units, listening ports, and
  Docker containers when Docker is present;
- uses `changed_when: false` for every shell command;
- does not use `become` by default;
- does not install packages, write files, restart services, or delete anything.

For agent use, ask the agent to summarize findings and propose separate remediation
steps. Any remediation should be reviewed as a new plan with explicit approval.
