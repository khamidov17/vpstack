"""vp_log_learning + vp_get_learnings — persistent cross-session research memory.

Mirrors gstack's learnings.jsonl pattern applied to VP2026 research.
Discoveries from one session surface in future sessions via vp_get_context
and /vp-implement pre-flight, preventing re-discovery of the same pitfalls.

Examples of things that belong here:
  - "HuBERT layer 6 causes speaker leakage on short (< 1s) utterances"
  - "ECAPA 192ch + HiFi-GAN v1 produces phase artifacts above 4kHz"
  - "α=0.75 outperforms α=0.8 on female speakers in LibriSpeech dev"
  - "VP2026 trial list v2 has a bug in speaker 1071 enrollment"
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err


_VALID_TYPES = frozenset({"pitfall", "pattern", "preference", "architecture", "component", "data"})
_VALID_SOURCES = frozenset({"observed", "user-stated", "inferred", "cross-model"})


def _project_slug() -> str:
    import hashlib
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


def handle_log(
    key: str,
    insight: str,
    type: str = "pitfall",
    confidence: int = 8,
    source: str = "observed",
    files: list | None = None,
    component: str = "",
) -> ToolResult:
    """Append a research learning to ~/.vpstack/projects/{slug}/learnings.jsonl.

    Args:
        key: Short kebab-case identifier, e.g. "hubert-layer6-short-utterances".
        insight: One to three sentences describing the learning. Be specific.
        type: One of: pitfall, pattern, preference, architecture, component, data.
        confidence: 1-10. Observed in code/data = 8-9. Inferred = 4-5. User-stated = 10.
        source: observed | user-stated | inferred | cross-model.
        files: Optional list of relevant file paths (for staleness detection).
        component: Optional component name this relates to (e.g., "hubert", "ecapa-tdnn").
    """
    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", key):
        return err(
            "INVALID_CONFIG",
            f"key must be kebab-case [a-z0-9_-], max 64 chars, got: {key!r}",
            "Example: 'hubert-layer6-short-utterances'",
        )
    if type not in _VALID_TYPES:
        return err("INVALID_CONFIG", f"type must be one of {sorted(_VALID_TYPES)}", "")
    if source not in _VALID_SOURCES:
        return err("INVALID_CONFIG", f"source must be one of {sorted(_VALID_SOURCES)}", "")
    if not 1 <= confidence <= 10:
        return err("INVALID_CONFIG", "confidence must be 1-10", "")
    if not insight.strip():
        return err("INVALID_CONFIG", "insight cannot be empty", "")

    slug = _project_slug()
    learnings_dir = Path.home() / ".vpstack" / "projects" / slug
    try:
        learnings_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return err("INTERNAL", f"mkdir failed: {e}", "")

    entry = {
        "key": key,
        "type": type,
        "insight": insight.strip(),
        "confidence": confidence,
        "source": source,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if files:
        entry["files"] = [str(f) for f in files]
    if component:
        entry["component"] = component

    learnings_path = learnings_dir / "learnings.jsonl"
    try:
        with open(learnings_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        return err("INTERNAL", f"write failed: {e}", "")

    return ok({"logged": True, "key": key, "path": str(learnings_path)})


def handle_get(
    query: str = "",
    type: str = "",
    component: str = "",
    limit: int = 20,
) -> ToolResult:
    """Return logged learnings, optionally filtered.

    Args:
        query: Substring match against key + insight.
        type: Filter by type (pitfall, pattern, etc.).
        component: Filter by component name.
        limit: Max results. Default 20, newest first.
    """
    slug = _project_slug()
    learnings_path = Path.home() / ".vpstack" / "projects" / slug / "learnings.jsonl"

    if not learnings_path.exists():
        return ok({
            "learnings": [],
            "total": 0,
            "note": f"No learnings logged yet at {learnings_path}. Use vp_log_learning to start building memory.",
        })

    entries: list[dict] = []
    try:
        lines = learnings_path.read_text().strip().splitlines()
        for line in reversed(lines):  # newest first
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter
            if type and e.get("type") != type:
                continue
            if component and e.get("component", "") != component:
                continue
            if query:
                q = query.lower()
                searchable = f"{e.get('key', '')} {e.get('insight', '')} {e.get('component', '')}"
                if q not in searchable.lower():
                    continue

            entries.append(e)
            if len(entries) >= limit:
                break
    except OSError:
        pass

    return ok({
        "learnings": entries,
        "total": len(entries),
        "project_slug": slug,
    })
