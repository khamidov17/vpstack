"""vp_check_submission — validate a submission directory against the VP2026 expected format."""

from __future__ import annotations

from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err


# Required files in a VP2026 submission directory. Updated as the 2026 organizer
# spec stabilizes. As of audit 2026-04-27 the 2026 plan was just published; verify
# against the latest plan PDF before relying on this.
REQUIRED_FILES_VP2026_DEV = (
    "trial_results/dev/eer.json",
    "trial_results/dev/wer.json",
    "trial_results/dev/linkability.json",
    "system_description.md",
    "anonymized_audio/dev",  # directory
)


def handle(submission_path: str) -> ToolResult:
    """Validate the submission. Returns structured errors and warnings."""
    p = Path(submission_path).expanduser()
    if not p.exists():
        return err("DATA_MISSING", f"submission path does not exist: {p}", "")
    if not p.is_dir():
        return err("INVALID_CONFIG", f"submission path is not a directory: {p}", "")

    errors: list[str] = []
    warnings: list[str] = []

    for required in REQUIRED_FILES_VP2026_DEV:
        target = p / required
        if not target.exists():
            errors.append(f"missing required: {required}")

    # Validate JSON shapes (light touch — full schema TBD when 2026 organizers publish)
    eer_path = p / "trial_results/dev/eer.json"
    if eer_path.exists():
        import json
        try:
            with open(eer_path) as f:
                data = json.load(f)
            for key in ("male", "female", "overall"):
                if key not in data:
                    errors.append(f"eer.json missing key: {key}")
                elif not isinstance(data[key], (int, float)):
                    errors.append(f"eer.json[{key}] must be numeric, got {type(data[key]).__name__}")
        except json.JSONDecodeError as e:
            errors.append(f"eer.json is not valid JSON: {e}")

    if not errors:
        return ok({
            "valid": True,
            "warnings": warnings,
            "validated_against": "VP2026 (audit 2026-04-27 — verify against current plan PDF before submission)",
        })
    return err(
        "MALFORMED_SUBMISSION",
        f"submission has {len(errors)} structural error(s)",
        f"Errors: {'; '.join(errors[:5])}",
    )
