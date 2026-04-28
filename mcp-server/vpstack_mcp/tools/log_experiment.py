"""vp_log_experiment — atomically log an experiment to ~/.vpstack/projects/{slug}/experiments/{exp_id}/.

CRITICAL contract (CG7 in TEST-PLAN.md):
  Atomic write — no half-state on kill -9.

Strategy: write to {target}.tmp, fsync, atomic os.replace to {target}. Either you
get a complete summary.json or you get nothing — never a half-written file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err


_VALID_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")




from vpstack_mcp._utils import project_slug as _project_slug

def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON to path atomically. Survives kill -9 mid-write — file is either
    fully present or absent, never partially present."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    # Fsync the parent dir so the rename itself is durable on power loss.
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def handle(
    exp_id: str,
    metrics: dict,
    config_hash: str,
    hypothesis: str = "",
    method: str = "",
    system_name: str = "",
    tags: list | None = None,
) -> ToolResult:
    """Log an experiment atomically. Returns the path it was written to.

    Optional metadata fields (hypothesis, method, system_name, tags) are indexed by
    vp_search_experiments — populate them so search works beyond exact ID matching.
    """
    if not _VALID_ID.match(exp_id):
        return err(
            "INVALID_CONFIG",
            f"exp_id must match {_VALID_ID.pattern}",
            "Use only [a-zA-Z0-9._-], 1-128 chars. Skills typically use ISO timestamps.",
        )

    if not isinstance(metrics, dict):
        return err("INVALID_CONFIG", f"metrics must be a dict, got {type(metrics).__name__}", "")

    slug = _project_slug()
    exp_dir = Path.home() / ".vpstack" / "projects" / slug / "experiments" / exp_id
    try:
        exp_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno == 28:  # ENOSPC — disk full
            return err("DISK_FULL", "no space left on device", "Free up disk and retry.")
        if e.errno == 13:  # EACCES — permission
            return err("PERMISSION_DENIED",
                       f"cannot write to {exp_dir}",
                       "Check ~/.vpstack ownership.")
        return err("INTERNAL", f"mkdir failed: {e}", "")

    summary = {
        "id": exp_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_hash": config_hash,
        "metrics": metrics,
        "vpstack_version_note": "Per design, vpstack version is researcher-tracked, not stored here.",
        # Optional search-indexed fields — omit from summary if empty to keep files clean.
    }
    if hypothesis:
        summary["hypothesis"] = hypothesis
    if method:
        summary["method"] = method
    if system_name:
        summary["system_name"] = system_name
    if tags:
        summary["tags"] = tags if isinstance(tags, list) else [str(tags)]

    summary_path = exp_dir / "summary.json"
    try:
        _atomic_write_json(summary_path, summary)
    except OSError as e:
        if e.errno == 28:
            return err("DISK_FULL", "no space left on device during write", "")
        return err("INTERNAL", f"atomic write failed: {e}", "")

    return ok({
        "logged": True,
        "path": str(summary_path),
        "exp_id": exp_id,
        "project_slug": slug,
    })
