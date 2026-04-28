"""vp_get_leaderboard — rank all logged experiments by a metric.

Returns a sorted comparison table with B1/B2 reference rows baked in.
Replaces N individual experiment reads with one tool call.

Typical use: "Which of my 15 experiments had the best EER?"
Before: 15 reads × ~300 tokens = 4500 tokens.
After: 1 tool call, ~400 tokens of output.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok

# B1/B2 approximate reference numbers — SEMI-INFORMED attacker condition.
#
# EER direction: HIGHER = more private. 50% = random (perfect anonymization).
# Original (no anonymization) EER: ~3-5% (ASV works perfectly, zero privacy).
#
# Under SEMI-INFORMED condition (official VP2026 ranking attacker), which retrains
# ECAPA on anonymized data:
#   B1 (McAdams): ~13-14% EER — low, because the adapted attacker easily sees through LPC
#   B2 (neural):  ~35-45% EER — much higher, neural anonymization is harder to adapt against
#
# Under IGNORANT condition, both baselines give ~50%+ EER because the attacker has no
# knowledge of anonymization — but ignorant EER is NOT the ranking metric.
#
# These are approximate VP2020/VP2022 numbers; VP2026 numbers may differ slightly.
# Run /vp-baseline-compare on your actual data to get project-specific reference values.
# Do NOT report these illustrative numbers in a paper — run the real baselines.
_REFERENCE_ROWS = [
    {
        "id": "50% (random — perfect anonymization goal)",
        "type": "reference",
        "eer": 50.0,
        "wer": None,
        "linkability": None,
        "method": "theoretical maximum",
        "note": "An attacker doing random guessing. This is what you're trying to approach.",
    },
    {
        "id": "B2 (HuBERT+ECAPA+HiFi-GAN) — semi-informed ~approx",
        "type": "reference",
        "eer": 40.0,
        "wer": 8.1,
        "linkability": 0.42,
        "method": "neural",
        "note": "Approximate. Semi-informed attacker. Run /vp-baseline-compare for actual number.",
    },
    {
        "id": "B1 (McAdams α=0.8) — semi-informed ~approx",
        "type": "reference",
        "eer": 13.5,
        "wer": 8.4,
        "linkability": 0.45,
        "method": "signal-processing",
        "note": "Approximate. Semi-informed attacker adapts easily to McAdams. "
                "Ignorant condition gives ~50%+.",
    },
    {
        "id": "Original speech (no anonymization)",
        "type": "reference",
        "eer": 4.0,
        "wer": 5.0,
        "linkability": 0.05,
        "method": "no anonymization",
        "note": "Approximate. ASV works well, zero privacy. Your system must be significantly above this.",
    },
]


def _project_slug() -> str:
    """Must match log_experiment._project_slug()."""
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


def _is_valid_float(v: Any) -> bool:
    """Return True if v is a real float (not NaN, not None)."""
    return isinstance(v, (int, float)) and not math.isnan(float(v))


def handle(
    sort_by: str = "eer",
    sort_order: str = "desc",
    limit: int = 50,
    include_references: bool = True,
) -> ToolResult:
    """Return all logged experiments ranked by the chosen metric.

    Args:
        sort_by: Metric to sort by — "eer", "wer", or "linkability". Default "eer".
            EER is sorted descending (higher = more private = better).
            WER is sorted ascending (lower = better utility).
        sort_order: "asc" or "desc". If omitted, the natural direction for the metric is used.
        limit: Max experiments to return. Default 50.
        include_references: Include B1/B2 reference rows. Default True.

    Returns:
        Ranked list with rank, id, date, metrics, method, and beats_b1/beats_b2 flags.
    """
    if sort_by not in ("eer", "wer", "linkability"):
        from vpstack_mcp.errors import err
        return err(
            "INVALID_CONFIG",
            f"sort_by must be 'eer', 'wer', or 'linkability', got: {sort_by}",
            "",
        )

    # Natural sort direction: EER higher=better (desc), WER lower=better (asc)
    natural_desc = {"eer": True, "linkability": True, "wer": False}
    effective_desc = sort_order == "desc" if sort_order in ("asc", "desc") else natural_desc[sort_by]

    slug = _project_slug()
    exp_root = Path.home() / ".vpstack" / "projects" / slug / "experiments"

    rows: list[dict[str, Any]] = []
    if exp_root.exists():
        for exp_dir in exp_root.iterdir():
            if not exp_dir.is_dir():
                continue
            f = exp_dir / "summary.json"
            if not f.exists():
                continue
            try:
                with open(f) as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, OSError):
                continue
            metrics = data.get("metrics") or {}
            rows.append({
                "id": data.get("id", exp_dir.name),
                "type": "experiment",
                "date": (data.get("date") or "")[:10],
                "eer": metrics.get("eer"),
                "wer": metrics.get("wer"),
                "linkability": metrics.get("linkability"),
                "config_hash": data.get("config_hash", ""),
                "method": data.get("method", ""),
                "system_name": data.get("system_name", ""),
                "hypothesis": (data.get("hypothesis") or "")[:80],
                "tags": data.get("tags") or [],
            })

    # Sort: experiments with valid metric value first, then None/NaN
    def sort_key(r: dict) -> tuple:
        v = r.get(sort_by)
        has_value = _is_valid_float(v)
        val = float(v) if has_value else (float("-inf") if effective_desc else float("inf"))
        # Negate for descending sort
        return (0 if has_value else 1, -val if effective_desc else val)

    rows.sort(key=sort_key)
    rows = rows[:limit]

    # Add reference rows for comparison context
    if include_references:
        ref_rows = _REFERENCE_ROWS[:]
        # beats_B1 / beats_B2: does this experiment exceed the reference EER?
        # B1 semi-informed ≈ 13.5% EER (weak, attacker adapts easily to McAdams)
        # B2 semi-informed ≈ 40% EER (neural, harder to adapt against)
        # Both are approximate — run /vp-baseline-compare for project-specific values.
        b1_eer_approx = 13.5
        b2_eer_approx = 40.0
        for r in rows:
            eer = r.get("eer")
            if _is_valid_float(eer):
                r["beats_B1_approx"] = float(eer) > b1_eer_approx
                r["beats_B2_approx"] = float(eer) > b2_eer_approx
        rows = ref_rows + rows  # references at top for easy comparison

    # Add rank numbers (skip reference rows)
    rank = 1
    for r in rows:
        if r.get("type") == "reference":
            r["rank"] = "REF"
        else:
            r["rank"] = rank
            rank += 1

    metric_note = {
        "eer": (
            "Higher EER = more private. 50% = random (perfect anonymization goal). "
            "B1 semi-informed ≈ 13.5% (weak), B2 semi-informed ≈ 40% (strong). "
            "Run /vp-baseline-compare on your data for accurate reference values."
        ),
        "wer": "Lower WER = better utility. B2 baseline: ~8.1%.",
        "linkability": "Lower linkability = harder for attacker to link speakers. B2 ≈ 0.42.",
    }[sort_by]

    return ok({
        "project_slug": slug,
        "sorted_by": sort_by,
        "sort_order": "descending" if effective_desc else "ascending",
        "total_experiments": len([r for r in rows if r.get("type") != "reference"]),
        "metric_note": metric_note,
        "rows": rows,
    })
