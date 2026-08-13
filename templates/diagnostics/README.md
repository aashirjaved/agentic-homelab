# Diagnostics Bundle Template

Diagnostics bundles should help an agent debug without leaking secrets.

## Include

- timestamp
- node inventory
- service status
- recent task/job status
- relevant logs
- version information
- config fingerprints
- redacted environment variable names

## Exclude

- passwords
- private keys
- API tokens
- full `.env` files
- personal messages
- unrelated browser/session history

## Suggested Bundle Layout

```text
diagnostics/
├── manifest.yaml
├── inventory.yaml
├── services/
├── logs/
├── tasks/
└── redactions.txt
```

## Generate A Bundle

Metadata-only bundle:

```bash
python3 scripts/create_diagnostics_bundle.py --inventory homelab.inventory.yaml
```

Include bounded read-only local command output:

```bash
python3 scripts/create_diagnostics_bundle.py --inventory homelab.inventory.yaml --include-commands
```

The generator does not include raw environment values. It records relevant environment variable names only, with secret-like names marked as redacted.
