"""vp_check_submission — validate a VP2026 submission directory against the official format.

REWRITTEN 2026-04-28 after audit: the prior version (JSON files, linkability.json, etc.)
described an INVENTED format that did not match the VP2026 plan. This version targets the
actual layout from VP2026 Eval Plan v1 (HAL hal-05561895, released 2026-03-17), Tables 8-9.

VP2026 submission layout (per the plan, §7.1):

  exp/
    asr/results*<suffix>.csv                          # WER (utility, both tracks)
    ser/results*<suffix>.csv                          # SER UAR (Track 1 utility)
    asv_ssl/results*<suffix>.csv                      # ASV lazy-informed EER (Track 1 privacy floor)
    asv_anon<suffix>/...                              # ASV semi-informed EER (Track 1 ranking)

    # Track 2 (multilingual) adds:
    openai/whisper-large-v3/results*<suffix>.csv      # Track 2 WER
    ser_emotion2vec/results*<suffix>.csv              # Track 2 SER (emotion2vec)
    asv_anon_track2*/results*<suffix>.csv             # Track 2 semi-informed ASV

    results_summary/track1/result_for_rank<suffix>           # rank-format text
    results_summary/track1/result_for_submission<suffix>.zip # the actual submission archive

CSV column convention (per audit of result_for_rank_mcadams reference output):
  dataset, split, gender, enrollment, trial, EER

Gender conditions VP2026 evaluates: F-F, M-M, **and Mixed** (F-F + M-M + F-M + M-F).
"The EER is calculated using the Mixed trials" (plan §7.1, line 193).

Audio: 16 kHz 16-bit signed-integer PCM WAVs, packaged as a single compressed archive.

NOTE: This validator is best-effort against a recently-published spec. The 2026 plan was
released only 2026-03-17. Re-verify against the latest plan PDF (and the official baseline
repo at github.com/Voice-Privacy-Challenge when published) before relying on this for a
real submission.

Failure surfaces: DATA_MISSING, INVALID_CONFIG, MALFORMED_SUBMISSION.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from vpstack_mcp.errors import ToolResult, ok, err


# Required CSV files for a Track 1 submission. Glob patterns used because the
# challenge spec allows for an optional <suffix> qualifier on the filename.
TRACK1_REQUIRED_CSVS = (
    ("exp/asr", "results*.csv"),                # WER
    ("exp/ser", "results*.csv"),                # SER UAR
    ("exp/asv_ssl", "results*.csv"),            # ASV lazy-informed EER
)
# ASV semi-informed has a parameterized dirname (asv_anon<suffix>); we just check
# that at least one such directory exists with results inside.
TRACK1_ASV_ANON_PATTERN = "asv_anon*"

# Track 2 (multilingual) additions.
TRACK2_REQUIRED_CSVS = (
    ("exp/openai/whisper-large-v3", "results*.csv"),   # multilingual WER
    ("exp/ser_emotion2vec", "results*.csv"),           # multilingual SER
)
TRACK2_ASV_ANON_PATTERN = "asv_anon_track2*"

# Required CSV column set (per result_for_rank_mcadams convention).
EER_CSV_COLUMNS = {"dataset", "split", "gender", "enrollment", "trial", "EER"}


def _find_csv(root: Path, subdir: str, glob: str) -> Path | None:
    """Find the first CSV matching subdir/glob inside root. Returns None if none."""
    target_dir = root / subdir
    if not target_dir.exists():
        return None
    matches = list(target_dir.glob(glob))
    return matches[0] if matches else None


def _validate_eer_csv(path: Path) -> list[str]:
    """Return a list of issues with this CSV's columns. Empty list = OK."""
    issues: list[str] = []
    try:
        with open(path) as f:
            header = f.readline().strip()
    except OSError as e:
        return [f"unreadable: {path}: {e}"]
    cols = {c.strip() for c in header.split(",")}
    missing = EER_CSV_COLUMNS - cols
    if missing:
        issues.append(f"{path.name}: missing columns {sorted(missing)} (expected {sorted(EER_CSV_COLUMNS)})")
    return issues


def _detect_track(root: Path) -> Tuple[str, list[str]]:
    """Best-effort track detection. Returns (track_name, evidence_list)."""
    has_track1 = (root / "exp" / "asv_ssl").exists()
    has_track2 = (root / "exp" / "openai" / "whisper-large-v3").exists()

    evidence = []
    if has_track1: evidence.append("found exp/asv_ssl/ — Track 1 indicator")
    if has_track2: evidence.append("found exp/openai/whisper-large-v3/ — Track 2 indicator")

    if has_track2 and has_track1:
        return "track1+track2", evidence
    if has_track2:
        return "track2", evidence
    if has_track1:
        return "track1", evidence
    return "unknown", evidence


def handle(submission_path: str) -> ToolResult:
    """Validate the submission against VP2026 Eval Plan v1 (Tables 8-9)."""
    p = Path(submission_path).expanduser().resolve()
    if not p.exists():
        return err("DATA_MISSING", f"submission path does not exist: {p}", "")
    if not p.is_dir():
        return err(
            "INVALID_CONFIG",
            f"submission path is not a directory: {p}",
            "Pass the directory containing exp/ — typically your project root after running /vp-eval --official.",
        )

    errors: list[str] = []
    warnings: list[str] = []
    track, track_evidence = _detect_track(p)

    if track == "unknown":
        return err(
            "MALFORMED_SUBMISSION",
            "could not detect Track 1 or Track 2 — neither exp/asv_ssl/ nor exp/openai/whisper-large-v3/ found",
            "VP2026 submissions live under exp/ at the submission root. "
            "If you ran /vp-eval --official, check its output directory.",
        )

    # ---- Track 1 (always present in track1 or track1+track2) ---------------------
    if "track1" in track:
        for subdir, glob in TRACK1_REQUIRED_CSVS:
            csv_path = _find_csv(p, subdir, glob)
            if csv_path is None:
                errors.append(f"missing required Track 1 CSV: {subdir}/{glob}")
            else:
                errors.extend(_validate_eer_csv(csv_path))

        # asv_anon<suffix> directory check
        asv_anon_dirs = list((p / "exp").glob(TRACK1_ASV_ANON_PATTERN))
        if not asv_anon_dirs:
            errors.append(
                f"missing required Track 1 ASV semi-informed directory: exp/{TRACK1_ASV_ANON_PATTERN}/ "
                "(this is the official ranking attacker output)"
            )
        elif not any(d.is_dir() and any(d.glob("results*.csv")) for d in asv_anon_dirs):
            errors.append(
                f"exp/{TRACK1_ASV_ANON_PATTERN}/ exists but contains no results*.csv files"
            )

    # ---- Track 2 (multilingual) -----------------------------------------------
    if "track2" in track:
        for subdir, glob in TRACK2_REQUIRED_CSVS:
            csv_path = _find_csv(p, subdir, glob)
            if csv_path is None:
                errors.append(f"missing required Track 2 CSV: {subdir}/{glob}")
            else:
                errors.extend(_validate_eer_csv(csv_path))

        asv_anon_t2_dirs = list((p / "exp").glob(TRACK2_ASV_ANON_PATTERN))
        if not asv_anon_t2_dirs:
            errors.append(
                f"missing required Track 2 ASV directory: exp/{TRACK2_ASV_ANON_PATTERN}/"
            )

    # ---- Submission archive (the actual upload artifact) ----------------------
    expected_zip_dirs = []
    if "track1" in track:
        expected_zip_dirs.append("exp/results_summary/track1")
    if "track2" in track:
        expected_zip_dirs.append("exp/results_summary/track2")

    for zip_dir in expected_zip_dirs:
        d = p / zip_dir
        if not d.exists():
            warnings.append(
                f"results summary directory missing: {zip_dir}/ "
                "(should contain result_for_rank<suffix> + result_for_submission<suffix>.zip)"
            )
            continue
        rank_files = list(d.glob("result_for_rank*"))
        sub_zips = list(d.glob("result_for_submission*.zip"))
        if not rank_files:
            errors.append(f"missing rank file: {zip_dir}/result_for_rank<suffix>")
        if not sub_zips:
            errors.append(f"missing submission archive: {zip_dir}/result_for_submission<suffix>.zip")

    # ---- Note about audio format we cannot fully validate from here -----------
    warnings.append(
        "audio archive contents not validated by this tool: VP2026 requires 16 kHz 16-bit "
        "signed-integer PCM WAVs. Verify your anonymized output matches before zipping."
    )

    if errors:
        return err(
            "MALFORMED_SUBMISSION",
            f"submission has {len(errors)} structural error(s) against VP2026 Eval Plan v1",
            f"Errors: {'; '.join(errors[:6])}"
            + ("..." if len(errors) > 6 else "")
            + " | Reference: VP2026 Eval Plan §7.1, Tables 8-9 "
            "(https://www.voiceprivacychallenge.org/vp2026/docs/VPC_2026_march15.pdf)",
        )

    return ok({
        "valid": True,
        "track": track,
        "track_evidence": track_evidence,
        "warnings": warnings,
        "validated_against": "VP2026 Eval Plan v1 (HAL hal-05561895, audit 2026-04-28). "
                             "Re-verify against latest plan revision before relying on this for a real submission.",
    })
