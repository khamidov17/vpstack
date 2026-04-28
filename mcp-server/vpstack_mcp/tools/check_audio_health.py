"""vp_check_audio_health — pre-flight quality check on a directory of WAV files.

Practitioners running VP2026 pipelines repeatedly hit silent failures caused by
wrong sample rate, clipping, excessive silence, or stereo files. This tool scans
a bounded sample of WAV files before expensive GPU pipelines start, surfacing those
issues early with an actionable verdict.

Failure surfaces: DATA_MISSING, INTERNAL.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)

# Scan bounds — mirror run_baseline._check_data_path to stay consistent.
_MAX_DEPTH = 8
_MAX_DIRS = 1000

# Audio quality thresholds.
_CLIP_THRESHOLD = 0.999       # abs(sample) >= this → clipping
_SILENCE_RMS_THRESHOLD = 0.001  # RMS below this → mostly silent
_SHORT_DURATION_S = 0.5       # shorter → too short for voice models
_LONG_DURATION_S = 300.0      # longer → may OOM


def _collect_wav_files(root: Path, max_dirs: int, max_depth: int) -> list[Path]:
    """Collect WAV file paths via a bounded walk.

    Mirrors the bounded-walk pattern from run_baseline._check_data_path.
    Returns a list (possibly empty) rather than a bool; does not raise.
    """
    found: list[Path] = []
    dirs_scanned = [0]

    def _walk(current: Path, depth: int) -> None:
        if depth < 0 or dirs_scanned[0] >= max_dirs:
            return
        dirs_scanned[0] += 1
        try:
            entries = list(os.scandir(current))
        except (OSError, PermissionError):
            return
        # Files first — gather WAVs.
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".wav"):
                    found.append(Path(entry.path))
            except OSError:
                continue
        # Then recurse into subdirectories.
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    _walk(Path(entry.path), depth - 1)
            except OSError:
                continue

    _walk(root, max_depth)
    return found


def handle(
    audio_path: str,
    expected_sr: int = 16000,
    max_files_to_scan: int = 100,
) -> ToolResult:
    """Pre-flight quality check on a directory of WAV files.

    Args:
        audio_path: Path to directory containing WAV files.
        expected_sr: Expected sample rate in Hz (default 16000).
        max_files_to_scan: Maximum number of files to inspect (default 100).
            Caps scan time on large directories — a representative sample is
            drawn from whatever the bounded walk finds first.

    Returns:
        ok() with summary statistics and a PASS / WARN / FAIL verdict, or
        err() if the path is missing/not-a-directory, or soundfile is absent.
    """
    # Import soundfile early — give a clear error if it's missing.
    try:
        import soundfile as sf  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
    except ImportError as exc:
        return err(
            "INTERNAL",
            f"soundfile (and/or numpy) not installed: {exc}",
            "pip install soundfile numpy",
        )

    # --- Path validation -------------------------------------------------------
    p = Path(audio_path).expanduser().resolve()
    if not p.exists():
        return err(
            "DATA_MISSING",
            f"audio_path does not exist: {p}",
            "Pass the absolute path to a directory that contains .wav files.",
        )
    if not p.is_dir():
        return err(
            "DATA_MISSING",
            f"audio_path is not a directory: {p}",
            "Pass a directory, not an individual file.",
        )

    # --- Collect WAV files (bounded) ------------------------------------------
    all_wav_files = _collect_wav_files(p, _MAX_DIRS, _MAX_DEPTH)
    total_files = len(all_wav_files)

    if total_files == 0:
        return err(
            "DATA_MISSING",
            f"No .wav files found within {_MAX_DEPTH} directory levels of {p}",
            "Verify the path points to a directory with WAV files. "
            "Ensure filenames end in .wav (case-insensitive).",
        )

    # Cap to max_files_to_scan — take the first N from the walk order.
    sample = all_wav_files[:max(1, max_files_to_scan)]
    files_scanned = len(sample)

    # --- Per-file inspection ---------------------------------------------------
    issues: list[dict[str, str]] = []
    durations: list[float] = []
    sr_mismatches = 0
    stereo_count = 0
    clipped_count = 0
    silent_count = 0
    short_count = 0
    long_count = 0

    for wav_path in sample:
        rel = str(wav_path.relative_to(p))
        try:
            info = sf.info(wav_path)
            actual_sr: int = info.samplerate
            channels: int = info.channels
            duration_s: float = info.duration

            # Sample-rate check — the most dangerous mismatch (silent wrong results).
            if actual_sr != expected_sr:
                sr_mismatches += 1
                issues.append({
                    "file": rel,
                    "issue_type": "sr_mismatch",
                    "detail": f"expected {expected_sr} Hz, got {actual_sr} Hz",
                })

            # Stereo check.
            if channels > 1:
                stereo_count += 1
                issues.append({
                    "file": rel,
                    "issue_type": "stereo",
                    "detail": f"{channels} channels — downmix to mono required",
                })

            # Duration checks.
            durations.append(duration_s)
            if duration_s < _SHORT_DURATION_S:
                short_count += 1
                issues.append({
                    "file": rel,
                    "issue_type": "too_short",
                    "detail": f"{duration_s:.3f}s — below {_SHORT_DURATION_S}s minimum for voice models",
                })
            elif duration_s > _LONG_DURATION_S:
                long_count += 1
                issues.append({
                    "file": rel,
                    "issue_type": "very_long",
                    "detail": f"{duration_s:.1f}s — over {_LONG_DURATION_S}s, may cause GPU OOM",
                })

            # Read audio samples for clipping and silence checks.
            # Read at most 30 s to avoid loading huge files into RAM.
            max_frames = min(info.frames, actual_sr * 30)
            audio, _ = sf.read(wav_path, frames=max_frames, dtype="float32", always_2d=False)

            # Clipping: any sample near ±1.0.
            if np.any(np.abs(audio) >= _CLIP_THRESHOLD):
                clipped_count += 1
                issues.append({
                    "file": rel,
                    "issue_type": "clipping",
                    "detail": (
                        f"max abs amplitude {float(np.max(np.abs(audio))):.4f} "
                        f">= {_CLIP_THRESHOLD} — normalize or re-capture"
                    ),
                })

            # Silence: RMS below threshold.
            rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
            if rms < _SILENCE_RMS_THRESHOLD:
                silent_count += 1
                issues.append({
                    "file": rel,
                    "issue_type": "mostly_silent",
                    "detail": f"RMS {rms:.6f} < {_SILENCE_RMS_THRESHOLD} — likely silent or near-empty",
                })

        except Exception as exc:  # noqa: BLE001
            # Corrupt / unreadable file — note it but continue.
            issues.append({
                "file": rel,
                "issue_type": "unreadable",
                "detail": f"could not read file: {exc}",
            })

    # --- Compute summary stats -------------------------------------------------
    if durations:
        min_dur = float(min(durations))
        max_dur = float(max(durations))
        mean_dur = float(sum(durations) / len(durations))
    else:
        min_dur = max_dur = mean_dur = 0.0

    stats: dict[str, Any] = {
        "min_duration_s": round(min_dur, 3),
        "max_duration_s": round(max_dur, 3),
        "mean_duration_s": round(mean_dur, 3),
        "sr_mismatches": sr_mismatches,
        "stereo_count": stereo_count,
        "clipped_count": clipped_count,
        "silent_count": silent_count,
        "short_count": short_count,
        "long_count": long_count,
    }

    # --- Verdict ---------------------------------------------------------------
    if sr_mismatches > 0:
        verdict = "FAIL"
        recommendation = (
            f"{sr_mismatches} file(s) have wrong sample rate "
            f"(expected {expected_sr} Hz). This causes silent wrong results in VP pipelines. "
            f"Resample all audio to {expected_sr} Hz before running, e.g.: "
            f"`sox input.wav -r {expected_sr} output.wav`."
        )
    elif clipped_count > 0 or silent_count > 0 or stereo_count > 0 or short_count > 0 or long_count > 0:
        verdict = "WARN"
        parts: list[str] = []
        if clipped_count:
            parts.append(f"{clipped_count} clipped file(s) — normalize amplitude")
        if silent_count:
            parts.append(f"{silent_count} mostly-silent file(s) — check recording quality")
        if stereo_count:
            parts.append(f"{stereo_count} stereo file(s) — downmix to mono before running")
        if short_count:
            parts.append(
                f"{short_count} file(s) shorter than {_SHORT_DURATION_S}s — "
                "voice models may produce garbage on sub-half-second utterances"
            )
        if long_count:
            parts.append(
                f"{long_count} file(s) longer than {_LONG_DURATION_S}s — "
                "consider chunking to avoid GPU OOM"
            )
        recommendation = ". ".join(parts) + "."
    else:
        verdict = "PASS"
        recommendation = (
            f"All {files_scanned} sampled file(s) passed audio health checks. "
            "Safe to proceed with VP pipeline."
        )

    return ok({
        "total_files": total_files,
        "files_scanned": files_scanned,
        "verdict": verdict,
        "recommendation": recommendation,
        "stats": stats,
        "issues": issues,
    })
