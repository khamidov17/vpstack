"""Shared utilities for vpstack MCP tools.

Keep this module import-safe: no heavy dependencies, no side effects on import.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def project_slug() -> str:
    """Return the project slug used by all vpstack storage paths.

    Format: {repo-basename}-{sha256[:8] of absolute toplevel path}

    The hash suffix (F10 fix) prevents collision between two repos with the
    same basename (e.g. ~/work/vp2026 and ~/forks/vp2026). Every tool that
    reads or writes to ~/.vpstack/projects/{slug}/ MUST use this function —
    never reimplement it locally — so that experiments, hypotheses, learnings,
    and leaderboard entries all land in the same directory.

    Must stay byte-for-byte identical to bin/vpstack-slug bash implementation:
        name=$(basename "$toplevel")
        hash=$(printf '%s' "$toplevel" | sha256sum | cut -c1-8)
        echo "${name}-${hash}"
    """
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        toplevel = out.decode().strip()
    except Exception:
        toplevel = os.getcwd()
    name = Path(toplevel).name or "unknown"
    h = hashlib.sha256(toplevel.encode()).hexdigest()[:8]
    return f"{name}-{h}"
