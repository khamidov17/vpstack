"""vp_get_context — one-call session restore for voice-privacy researchers.

Returns a compact summary of the project's current state: best experiment,
active hypothesis, last spike verdict, EER trajectory, and days to deadline
(if configured). Replaces 3-5 individual tool calls at the start of each session.

Token target: < 600 tokens of output for a typical project with 10 experiments.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok




from vpstack_mcp._utils import project_slug as _project_slug

def _load_experiments(exp_root: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Load the most recent N experiments, newest first."""
    exps = []
    if not exp_root.exists():
        return exps
    dirs = sorted(exp_root.iterdir(), reverse=True)
    for d in dirs:
        if not d.is_dir():
            continue
        f = d / "summary.json"
        if not f.exists():
            continue
        try:
            with open(f) as fp:
                exps.append(json.load(fp))
        except (json.JSONDecodeError, OSError):
            continue
        if len(exps) >= limit:
            break
    return exps


def _eer_trend(exps: list[dict]) -> str:
    """Describe EER trajectory from oldest to newest (only experiments with EER)."""
    eers = [(e.get("date", ""), e["metrics"].get("eer")) for e in reversed(exps)
            if isinstance(e.get("metrics", {}).get("eer"), (int, float))]
    eers = [(d, v) for d, v in eers if v == v]  # drop NaN
    if len(eers) < 2:
        return "not enough data"
    first, last = eers[0][1], eers[-1][1]
    delta = last - first
    direction = "improving" if delta > 0 else "declining" if delta < 0 else "flat"
    return f"{first:.1f}% → {last:.1f}% ({'+' if delta > 0 else ''}{delta:.1f}pp, {direction})"


def _best_experiment(exps: list[dict]) -> dict | None:
    """Return the experiment with the highest EER (most private)."""
    valid = [(e, e["metrics"].get("eer", float("-inf")))
             for e in exps if isinstance(e.get("metrics", {}).get("eer"), (int, float))
             and e["metrics"]["eer"] == e["metrics"]["eer"]]  # drop NaN
    if not valid:
        return None
    return max(valid, key=lambda x: x[1])[0]


def _load_latest_hypothesis(hyp_dir: Path) -> dict | None:
    """Load the most recently modified hypothesis."""
    if not hyp_dir.exists():
        return None
    files = sorted(hyp_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        text = files[0].read_text(errors="replace")
        lines = text.splitlines()
        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), files[0].stem)
        # Extract status and one-liner
        status = next((l.replace("## Status", "").strip() for l in lines if "Status" in l), "")
        one_liner = next((l for l in lines[1:6] if l.strip()), "")
        return {"file": files[0].name, "title": title, "status": status, "preview": one_liner}
    except OSError:
        return None


def _load_latest_spike(spike_dir: Path) -> dict | None:
    """Load the most recently modified spike."""
    if not spike_dir.exists():
        return None
    files = sorted(spike_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        text = files[0].read_text(errors="replace")
        lines = text.splitlines()
        title = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), files[0].stem)
        # Find verdict lines
        verdicts = [l.strip() for l in lines if "CONFIRMED" in l or "REFUTED" in l or "INCONCLUSIVE" in l]
        return {"file": files[0].name, "title": title, "verdicts": verdicts[:3]}
    except OSError:
        return None


def _days_to_deadline(config_path: Path) -> int | None:
    """Return days until submission_deadline if set in ~/.vpstack/config.json."""
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        dl = cfg.get("submission_deadline")
        if not dl:
            return None
        deadline = datetime.fromisoformat(dl).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (deadline - now).days
    except Exception:
        return None


def _load_learnings(learnings_path: Path, limit: int = 5) -> list[dict]:
    """Load the most recent learnings, newest first."""
    if not learnings_path.exists():
        return []
    learnings = []
    try:
        lines = learnings_path.read_text().strip().splitlines()
        for line in reversed(lines):
            try:
                learnings.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(learnings) >= limit:
                break
    except OSError:
        pass
    return learnings


def handle(include_learnings: bool = True) -> ToolResult:
    """Return a compact session-restore context for the current project.

    One call replaces:
    - vp_search_experiments (to find best run)
    - reading hypothesis files (to know what's being tested)
    - reading spike files (to know last verdict)
    - computing EER trend manually

    Output is intentionally terse — under 600 tokens for a typical project.
    """
    slug = _project_slug()
    base = Path.home() / ".vpstack" / "projects" / slug

    exp_root = base / "experiments"
    hyp_dir = base / "hypotheses"
    spike_dir = base / "spikes"
    learnings_path = base / "learnings.jsonl"
    config_path = Path.home() / ".vpstack" / "config.json"

    # Experiments
    exps = _load_experiments(exp_root, limit=20)
    best = _best_experiment(exps)
    trend = _eer_trend(exps) if len(exps) >= 2 else "not enough experiments"

    best_summary = None
    if best:
        best_summary = {
            "id": best.get("id"),
            "date": best.get("date"),
            "eer": best["metrics"].get("eer"),
            "wer": best["metrics"].get("wer"),
            "method": best.get("method", ""),
            "hypothesis": best.get("hypothesis", ""),
        }

    recent = []
    for e in exps[:5]:
        recent.append({
            "id": e.get("id"),
            "date": e.get("date", "")[:10],
            "eer": e["metrics"].get("eer"),
            "wer": e["metrics"].get("wer"),
            "method": e.get("method", ""),
        })

    hypothesis = _load_latest_hypothesis(hyp_dir)
    spike = _load_latest_spike(spike_dir)
    deadline_days = _days_to_deadline(config_path)
    learnings = _load_learnings(learnings_path, limit=5) if include_learnings else []

    # EER reference frame — only 50% is hardcoded (mathematical constant, not challenge-specific).
    # B1/B2 baseline EER numbers are VP2026-specific and must come from running the actual baselines
    # on your VP2026 data. Do not use numbers from previous challenge years.
    # Run /vp-baseline-compare, then log with vp_log_experiment(exp_id='b1-reference', ...).
    reference = {
        "50_pct_random": "50% EER — random attacker. Mathematical constant. This is the goal.",
        "eer_direction": "HIGHER EER = more private. Lower EER = attacker succeeds more often.",
        "attacker_conditions": {
            "semi_informed": "Official VP2026 ranking metric. Attacker retrains ECAPA on your anonymized train-clean-360. Hardest to fool.",
            "lazy_informed": "Intermediate. Attacker uses pretrained model with anonymized enrollment.",
            "ignorant": "Easiest to fool — attacker doesn't know anonymization was applied. NOT the ranking metric.",
        },
        "how_to_get_vp2026_baselines": "Run /vp-baseline-compare on your VP2026 data, then log the results with vp_log_experiment so they appear in vp_get_leaderboard.",
        "warning": "B1/B2 EER numbers from VP2020/VP2022 do not transfer to VP2026 — different data, trial lists, and possibly updated models.",
    }

    result: dict[str, Any] = {
        "project_slug": slug,
        "total_experiments": len(exps),
        "eer_trend": trend,
        "best_experiment": best_summary,
        "recent_experiments": recent,
        "active_hypothesis": hypothesis,
        "last_spike": spike,
        "reference_baselines": reference,
    }

    if deadline_days is not None:
        result["days_to_deadline"] = deadline_days
        if deadline_days < 14:
            result["deadline_warning"] = f"DEADLINE IN {deadline_days} DAYS — prioritize /vp-eval over ablations"

    if learnings:
        result["recent_learnings"] = [
            {"key": l.get("key", ""), "insight": l.get("insight", ""), "confidence": l.get("confidence")}
            for l in learnings
        ]

    return ok(result)
