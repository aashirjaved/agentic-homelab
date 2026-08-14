#!/usr/bin/env python3
"""Compatibility wrapper for the packaged homelab doctor."""

from agentic_homelab.doctor import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
