# Example: Multi-Node Monitoring

Goal: let an agent correlate alerts across several nodes.

## Flow

1. Read alert state.
2. Query recent metrics and logs.
3. Identify affected services and likely blast radius.
4. Prepare a remediation plan.

Machine-readable workflow: `workflow.yaml`.

Do not let the first pass silence alerts or change scrape configuration. The
first useful output is a cited incident summary with affected services,
confidence, and verification steps.
