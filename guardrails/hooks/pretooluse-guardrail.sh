#!/bin/sh
# Claude Code PreToolUse hook: turn the guardrail checker into a real gate.
# Reads the hook JSON on stdin, extracts the tool name, and blocks the call
# unless the checker classifies it allow_readonly (exit 0).
#
# Install in your homelab-agent-context .claude/settings.json:
#   {"hooks": {"PreToolUse": [{"matcher": "mcp__agentic-homelab.*",
#     "hooks": [{"type": "command",
#       "command": "/path/to/agentic-homelab/guardrails/hooks/pretooluse-guardrail.sh"}]}]}}
#
# Exit codes: 0 lets the tool call proceed; 2 blocks it and feeds the
# checker's decision back to the agent as the reason.

set -eu

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3

TOOL_NAME=$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')
# MCP tool names arrive as mcp__<server>__<tool>; classify the bare tool name.
ACTION=${TOOL_NAME##*__}
[ -n "$ACTION" ] || exit 0

if OUTPUT=$("$PYTHON" "$REPO_DIR/scripts/guardrail_check.py" "$ACTION" 2>&1); then
    exit 0
else
    echo "guardrail_check blocked '$ACTION':" >&2
    echo "$OUTPUT" >&2
    exit 2
fi
