"""Structured error contract for vpstack MCP tools.

Every tool returns:
    {"ok": bool, "result": Optional[Dict], "error": Optional[ErrorDict]}

where ErrorDict has:
    {"code": str (UPPER_SNAKE_CASE), "message": str (human), "hint": str (actionable)}

This prevents stack traces leaking through MCP and gives clients a stable
error code they can branch on without parsing prose.
"""

from typing import Any, Optional, TypedDict


class ErrorDict(TypedDict):
    code: str
    message: str
    hint: str


class ToolResult(TypedDict, total=False):
    ok: bool
    result: Optional[dict]
    error: Optional[ErrorDict]


# Allowlist of error codes. Add new codes here, do not invent ad-hoc strings in tools.
ERROR_CODES = frozenset({
    "GPU_OOM",
    "DATA_MISSING",
    "MODEL_DOWNLOAD_FAILED",
    "INVALID_CONFIG",
    "MALFORMED_SUBMISSION",
    "BASELINE_NOT_IMPLEMENTED",
    "RECIPE_FAILED",
    "DISK_FULL",
    "PERMISSION_DENIED",
    "TIMEOUT",
    "EXP_NOT_FOUND",
    "UNKNOWN_COMPONENT",
    "EVAL_BLOCKED_TEST_SPLIT",
    "INTERNAL",
    # Added for /vp-attack (vp_run_attacker tool)
    "ATTACKER_TRAINING_FAILED",   # ECAPA loss diverged / NaN'd during semi-informed retrain
    "ATTACKER_DATA_MISMATCH",     # trial list / enrollment layout mismatch
})


def ok(result: dict[str, Any]) -> ToolResult:
    """Build a successful tool result."""
    return {"ok": True, "result": result, "error": None}


def err(code: str, message: str, hint: str = "") -> ToolResult:
    """Build a structured error result. Code must be in ERROR_CODES."""
    if code not in ERROR_CODES:
        # Defensive — never let an unknown code slip through.
        # In dev we'd assert, but in prod we coerce to INTERNAL with the bogus code in the hint.
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": "INTERNAL",
                "message": f"unknown error code: {code}",
                "hint": f"original message: {message}",
            },
        }
    return {
        "ok": False,
        "result": None,
        "error": {"code": code, "message": message, "hint": hint},
    }
