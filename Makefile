.PHONY: validate test doctor readiness diagnostics-smoke diagnostics-local guardrail-smoke mcp-config bootstrap-smoke workflow-chooser-smoke release-audit

validate:
	python3 -m venv .venv
	. .venv/bin/activate && python -m pip install -r requirements-dev.txt
	. .venv/bin/activate && python scripts/validate_repo.py
	. .venv/bin/activate && python -m unittest discover -s tests -q
	. .venv/bin/activate && python scripts/smoke_mcp.py

test:
	. .venv/bin/activate && python -m unittest discover -s tests -v

doctor:
	. .venv/bin/activate && python scripts/homelab_doctor.py

readiness:
	python3 scripts/doctor.py --inventory templates/inventory/homelab.inventory.example.json

diagnostics-smoke:
	python3 scripts/create_diagnostics_bundle.py --output diagnostics/smoke --inventory templates/inventory/homelab.inventory.example.yaml

diagnostics-local:
	python3 scripts/create_diagnostics_bundle.py --inventory templates/inventory/homelab.inventory.example.yaml --include-commands

guardrail-smoke:
	. .venv/bin/activate && python scripts/guardrail_check.py list_nodes --format json
	. .venv/bin/activate && python scripts/guardrail_check.py delete_guest --server proxmox --format json || test $$? -eq 2
	. .venv/bin/activate && python scripts/guardrail_check.py network-exposure --format json || test $$? -eq 2
	. .venv/bin/activate && python scripts/guardrail_check.py destructive --format json || test $$? -eq 2

mcp-config:
	python3 scripts/generate_mcp_config.py --inventory templates/inventory/homelab.inventory.example.json --output generated/mcp-config.json

bootstrap-smoke:
	python3 scripts/bootstrap_homelab_repo.py generated/bootstrap-smoke

workflow-chooser-smoke:
	. .venv/bin/activate && python scripts/choose_workflow.py --inventory templates/inventory/homelab.inventory.example.yaml

release-audit:
	. .venv/bin/activate && python scripts/release_audit.py --run-validate
