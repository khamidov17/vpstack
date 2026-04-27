"""vp_run_eval — full VP2026 evaluation pipeline on a user's anonymization system.

Runs the canonical eval (EER overall + per-gender, WER, linkability, side-channels) and
returns structured results. Held-out test split is blocked unless explicit opt-in.
"""

from __future__ import annotations

from typing import Any
from vpstack_mcp.errors import ToolResult, ok, err


def handle(
    system_path: str,
    eval_set: str,
    seed: int = 42,
    official_test: bool = False,
) -> ToolResult:
    """Run the VP2026 eval pipeline. Blocks accidental test-split use."""
    if eval_set not in {"dev", "test"}:
        return err(
            "INVALID_CONFIG",
            f"eval_set must be 'dev' or 'test', got: {eval_set}",
            "Use 'dev' for development; 'test' is held-out and blocked unless official_test=True.",
        )

    if eval_set == "test" and not official_test:
        return err(
            "EVAL_BLOCKED_TEST_SPLIT",
            "running eval on the held-out 'test' split without official_test=True",
            "Test set runs are reserved for official submission. "
            "If you're preparing a submission, pass official_test=True. "
            "Otherwise use eval_set='dev'.",
        )

    # TODO: implement full eval pipeline. v0.1 first cut shells out to the recipe's
    # eval entry point, similar to run_baseline.handle.
    return err(
        "BASELINE_NOT_IMPLEMENTED",
        "vp_run_eval is not yet implemented in v0.1.0-dev",
        "Tracked in vpstack/vpstack#TODO. Until then, use vp_run_baseline for B1/B2 "
        "and run the user's system manually via speechbrain_voice_anon recipes.",
    )
