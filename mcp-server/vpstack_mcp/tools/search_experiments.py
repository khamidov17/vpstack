"""vp_search_experiments — search the user's logged experiments at ~/.vpstack/projects/{slug}/experiments/.

v0.1: jsonl scan (fast for ~1000 experiments per researcher).
v0.2: Qdrant-backed semantic search if corpus grows past ~1k.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok


def _project_slug() -> str:
    """Project identifier for ~/.vpstack/projects/{slug}/.

    Must match log_experiment._project_slug() so search finds what was logged.
    F10 fix: name + 8-char hash of toplevel path to prevent collision between
    two repos with the same basename.
    """
    import hashlib
    try:
        import subprocess
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


def handle(query: str, limit: int = 10) -> ToolResult:
    """Substring-match query against experiment summaries. Returns matching entries."""
    slug = _project_slug()
    exp_root = Path.home() / ".vpstack" / "projects" / slug / "experiments"

    if not exp_root.exists():
        return ok({"matches": [], "total_searched": 0, "project_slug": slug,
                   "note": f"No experiments logged yet at {exp_root}"})

    matches: list[dict] = []
    total = 0
    q_lower = query.lower()

    # Each experiment is a directory with summary.json + raw outputs
    for exp_dir in sorted(exp_root.iterdir(), reverse=True):  # newest first
        if not exp_dir.is_dir():
            continue
        total += 1
        summary_file = exp_dir / "summary.json"
        if not summary_file.exists():
            continue
        try:
            with open(summary_file) as f:
                summary = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Search across id, hypothesis, method, system_name fields. Substring + case-insensitive.
        searchable = " ".join(str(summary.get(k, "")) for k in ("id", "hypothesis", "method", "system_name", "tags"))
        if q_lower in searchable.lower():
            matches.append({
                "id": summary.get("id", exp_dir.name),
                "summary": summary.get("summary", "")[:200],
                "eer": summary.get("metrics", {}).get("eer"),
                "wer": summary.get("metrics", {}).get("wer"),
                "linkability": summary.get("metrics", {}).get("linkability"),
                "config_hash": summary.get("config_hash"),
                "date": summary.get("date"),
            })
            if len(matches) >= limit:
                break

    return ok({
        "matches": matches,
        "total_searched": total,
        "project_slug": slug,
        "backend": "jsonl-scan",
    })
