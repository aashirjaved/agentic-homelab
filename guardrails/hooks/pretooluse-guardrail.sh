#!/bin/sh
# Claude Code PreToolUse hook: turn the guardrail checker into a real gate.
# All logic lives in `guardrail_check.py --hook`, which reads the hook JSON
# from stdin and prints a permissionDecision (allow / ask / deny), inspecting
# both the tool name and command-shaped tool arguments.
#
# Install in your homelab-agent-context .claude/settings.json:
#   {"hooks": {"PreToolUse": [{"matcher": "mcp__agentic-homelab.*",
#     "hooks": [{"type": "command",
#       "command": "/path/to/agentic-homelab/guardrails/hooks/pretooluse-guardrail.sh"}]}]}}
#
# Fail-closed contract: if the checker cannot run at all (missing venv,
# missing PyYAML, crash), this wrapper emits a deny decision itself rather
# than exiting non-zero, because non-2 exit codes are treated as non-blocking.

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3

if ! "$PYTHON" "$REPO_DIR/scripts/guardrail_check.py" --hook; then
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"guardrail checker failed to run (missing .venv/PyYAML?); failing closed. Run make validate in the agentic-homelab repo."}}'
fi
exit 0
