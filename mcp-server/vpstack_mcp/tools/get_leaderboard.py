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

# VP2026 reference rows — EER direction: HIGHER = more private. 50% = random = goal.
#
# We do NOT hardcode B1/B2 EER numbers here. Reasons:
#   1. VP2026 numbers are challenge-year-specific — different data, different trial lists.
#   2. The authoritative source is the VP2026 Eval Plan PDF from the challenge organizers.
#   3. Older years (VP2020/VP2022) had different numbers that don't transfer.
#
# The 50% row is the only safe hardcoded reference — it is a mathematical constant
# (random attacker), not a challenge-specific measurement.
#
# To get your actual B1/B2 reference values: run /vp-baseline-compare on your VP2026 data.
# Your logged experiments will then appear in the leaderboard with real baselines alongside.
_REFERENCE_ROWS = [
    {
        "id": "50% EER — random attacker (perfect anonymization goal)",
        "type": "reference",
        "eer": 50.0,
        "wer": None,
        "linkability": None,
        "method": "theoretical maximum — mathematical constant, not challenge-specific",
        "note": (
            "A completely random speaker-verification decision gives 50% EER. "
            "Perfect anonymization makes the attacker indistinguishable from random. "
            "This is the goal, not an achievable result for most current systems."
        ),
    },
    {
        "id": "B1 baseline — run /vp-baseline-compare to populate",
        "type": "reference_placeholder",
        "eer": None,
        "wer": None,
        "linkability": None,
        "method": "McAdams α=0.8, signal-processing",
        "note": (
            "VP2026-specific B1 EER not hardcoded — numbers are challenge-year-specific. "
            "Run: /vp-baseline-compare to get the actual B1 number on your VP2026 data. "
            "Log it with vp_log_experiment(exp_id='b1-reference', ...) to anchor this table."
        ),
    },
    {
        "id": "B2 baseline — run /vp-baseline-compare to populate",
        "type": "reference_placeholder",
        "eer": None,
        "wer": None,
        "linkability": None,
        "method": "HuBERT + ECAPA-TDNN + HiFi-GAN, neural",
        "note": (
            "VP2026-specific B2 EER not hardcoded — numbers are challenge-year-specific. "
            "Run: /vp-baseline-compare to get the actual B2 number on your VP2026 data. "
            "B2 EER should be significantly higher than B1 (neural is harder to break)."
        ),
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
        # beats_B1 / beats_B2: only computable if a logged experiment is named "b1-reference"
        # or "b2-reference" (i.e., the researcher ran /vp-baseline-compare and logged it).
        # We do NOT use hardcoded approximate numbers — VP2026 baselines are challenge-specific.
        b1_ref = next((e for e in rows if "b1" in (e.get("id") or "").lower()), None)
        b2_ref = next((e for e in rows if "b2" in (e.get("id") or "").lower()), None)
        b1_eer = b1_ref["eer"] if b1_ref and _is_valid_float(b1_ref.get("eer")) else None
        b2_eer = b2_ref["eer"] if b2_ref and _is_valid_float(b2_ref.get("eer")) else None
        for r in rows:
            if r.get("type") in ("reference", "reference_placeholder"):
                continue
            eer = r.get("eer")
            if _is_valid_float(eer):
                if b1_eer is not None:
                    r["beats_B1"] = float(eer) > b1_eer
                if b2_eer is not None:
                    r["beats_B2"] = float(eer) > b2_eer
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
