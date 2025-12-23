"""
DEPRECATED: Command-level queue persistence.

This module is deprecated. Use session.py for new code.

Only write_pending() is kept for MixSubprocess.save_pending() compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_QUEUE = Path("/tmp/shannot-pending.json")


def write_pending(commands: list[str], path: Path = DEFAULT_QUEUE):
    """Write pending commands to queue file."""
    path.write_text(json.dumps(commands, indent=2))
