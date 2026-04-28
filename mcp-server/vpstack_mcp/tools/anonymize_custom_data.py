"""vp_anonymize_custom_data — apply B1 McAdams anonymization to any WAV directory.

Unlike vp_run_baseline (which expects VP2026 Kaldi-layout data), this tool accepts ANY
directory of WAV files — medical speech, call-center audio, podcasts, etc. Output
preserves the input directory tree so downstream tools see the same relative paths.

Failure surfaces: BASELINE_NOT_IMPLEMENTED (B2 requested), DATA_MISSING, DISK_FULL,
PERMISSION_DENIED, INTERNAL.

Single corrupt or unreadable file never aborts the batch — per-file errors are
collected and returned in the result. The tool streams a progress heartbeat to stderr
every 30 seconds for long-running batches (MCP long-running-tool contract).
"""

from __future__ import annotations

import errno
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _find_wavs(root: Path, max_depth: int = 8, max_dirs: int = 5000) -> list[Path]:
    """Bounded directory walk. Returns all .wav files within *root*.

    Bounded to *max_depth* directory levels and *max_dirs* total directories to
    prevent runaway I/O when a caller accidentally passes a filesystem root.
    Symlinked entries are never followed (follow_symlinks=False) to avoid cycles.
    """
    found: list[Path] = []

    def _walk(path: Path, depth: int) -> None:
        if depth < 0 or len(found) > max_dirs:
            return
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except (OSError, PermissionError):
            return

        subdirs: list[Path] = []
        for entry in entries:
            try:
                if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".wav"):
                    found.append(Path(entry.path))
                elif entry.is_dir(follow_symlinks=False):
                    subdirs.append(Path(entry.path))
            except OSError:
                continue

        for sub in subdirs:
            _walk(sub, depth - 1)

    _walk(root, max_depth)
    return found


def _output_path_for(wav: Path, input_root: Path, output_root: Path) -> Path:
    """Map an input wav path to its mirrored output path under *output_root*."""
    rel = wav.relative_to(input_root)
    return output_root / rel


# --------------------------------------------------------------------------- #
# Public handle()
# --------------------------------------------------------------------------- #

def handle(
    input_path: str,
    output_path: str,
    method: str = "B1",
    alpha: float = 0.8,
    seed: int = 42,
    preserve_structure: bool = True,
    overwrite: bool = False,
) -> ToolResult:
    """Apply voice anonymization to every WAV file inside *input_path*.

    Parameters
    ----------
    input_path:
        Root directory containing WAV files (any nesting, any layout).
    output_path:
        Destination root. Anonymized WAVs are written here, mirroring the
        relative sub-paths of the originals when *preserve_structure* is True.
    method:
        Anonymization method. "B1" (McAdams LPC pole scaling) is implemented.
        "B2" is planned for v0.2 and returns BASELINE_NOT_IMPLEMENTED now.
    alpha:
        McAdams coefficient (B1 only). Typical range 0.5 – 1.0; default 0.8
        matches the VP2026 B1 baseline.
    seed:
        Random seed passed to the McAdams anonymizer for reproducible pole
        perturbation (when the implementation draws per-file jitter).
    preserve_structure:
        If True (default), output files mirror the input directory tree.
        If False, all output WAVs are written directly into *output_path* with
        a flattened name derived from the full relative path.
    overwrite:
        If False (default), files whose output counterpart already exists are
        skipped. Skipped files are counted in *n_files_skipped*.

    Returns
    -------
    ToolResult with::

        {
            "n_files_processed": int,
            "n_files_skipped":   int,
            "n_errors":          int,
            "output_path":       str,
            "method":            str,
            "alpha":             float,
            "seed":              int,
            "errors":            [{"file": str, "error": str}, ...]  # max 10
        }
    """
    # ------------------------------------------------------------------
    # 0. Early import check for soundfile
    # ------------------------------------------------------------------
    try:
        import soundfile as sf  # noqa: F401
    except ImportError:
        return err(
            "INTERNAL",
            "soundfile is not installed",
            "pip install soundfile  (also requires libsndfile on Linux: apt install libsndfile1)",
        )

    # ------------------------------------------------------------------
    # 1. Validate method
    # ------------------------------------------------------------------
    if method == "B2":
        return err(
            "BASELINE_NOT_IMPLEMENTED",
            "B2 neural anonymization is not yet implemented in vp_anonymize_custom_data",
            "Use method='B1' for signal-processing anonymization. "
            "B2 (HuBERT+ECAPA+HiFi-GAN) is tracked for v0.2.",
        )
    if method != "B1":
        return err(
            "INVALID_CONFIG",
            f"unknown method: {method!r}",
            "Supported methods: 'B1'. 'B2' is planned for v0.2.",
        )

    # ------------------------------------------------------------------
    # 2. Resolve and validate input_path
    # ------------------------------------------------------------------
    inp = Path(input_path).expanduser().resolve()
    if not inp.exists():
        return err(
            "DATA_MISSING",
            f"input_path does not exist: {inp}",
            "Provide an absolute path to a directory containing WAV files.",
        )
    if not inp.is_dir():
        return err(
            "DATA_MISSING",
            f"input_path is not a directory: {inp}",
            "Pass a directory, not a single file.",
        )

    wav_files = _find_wavs(inp)
    if not wav_files:
        return err(
            "DATA_MISSING",
            f"input_path contains no .wav files within 8 directory levels: {inp}",
            "Check that the directory contains WAV audio files. "
            "Other formats (mp3, flac) are not processed.",
        )

    # ------------------------------------------------------------------
    # 3. Resolve and validate output_path — must not be inside input_path
    # ------------------------------------------------------------------
    out = Path(output_path).expanduser().resolve()
    try:
        out.relative_to(inp)
        # If this succeeded, output is inside input — prevent self-overwrite.
        return err(
            "INVALID_CONFIG",
            "output_path is inside input_path — this would overwrite source files",
            f"Choose an output_path that is not a subdirectory of {inp}.",
        )
    except ValueError:
        pass  # Good — output is outside input.

    # ------------------------------------------------------------------
    # 4. Create output root
    # ------------------------------------------------------------------
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno == errno.ENOSPC:
            return err("DISK_FULL", "no space left on device while creating output_path", "Free disk space and retry.")
        if e.errno == errno.EACCES:
            return err("PERMISSION_DENIED", f"cannot create output directory: {out}", "Check directory permissions.")
        return err("INTERNAL", f"mkdir failed: {e}", "")

    # ------------------------------------------------------------------
    # 5. Import the McAdams anonymizer from the recipe package
    # ------------------------------------------------------------------
    try:
        from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import (
            mcadams_anonymize,
        )
    except ImportError as e:
        return err(
            "INTERNAL",
            f"Could not import mcadams_anonymize: {e}",
            "Install the recipe package: pip install -e speechbrain_voice_anon/",
        )

    import numpy as np
    import soundfile as sf

    # ------------------------------------------------------------------
    # 6. Process files
    # ------------------------------------------------------------------
    n_processed = 0
    n_skipped = 0
    error_list: list[dict[str, str]] = []
    last_heartbeat = time.monotonic()

    for wav in wav_files:
        # Heartbeat every 30 s so MCP clients know we're still alive.
        now = time.monotonic()
        if now - last_heartbeat >= 30.0:
            print(
                f"[vp_anonymize_custom_data] progress: {n_processed} processed, "
                f"{n_skipped} skipped, {len(error_list)} errors | "
                f"current: {wav.name}",
                file=sys.stderr,
                flush=True,
            )
            last_heartbeat = now

        # Determine destination path.
        if preserve_structure:
            dest = _output_path_for(wav, inp, out)
        else:
            flat_name = str(wav.relative_to(inp)).replace(os.sep, "_")
            dest = out / flat_name

        # Skip if already exists and overwrite=False.
        if not overwrite and dest.exists():
            n_skipped += 1
            continue

        try:
            # Read audio.
            audio, sr = sf.read(str(wav), always_2d=True)  # shape: (samples, channels)

            # Downmix to mono by averaging channels.
            if audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            else:
                audio = audio[:, 0]

            # Ensure float32 — McAdams operates in float.
            audio = audio.astype(np.float32)

            # Apply McAdams anonymization.
            anon_audio = mcadams_anonymize(audio, sr, alpha=alpha, seed=seed)

            # Create parent directories in output tree.
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Write output WAV at the same sample rate.
            sf.write(str(dest), anon_audio, sr, subtype="PCM_16")
            n_processed += 1

        except OSError as e:
            if e.errno == errno.ENOSPC:
                # Disk full mid-batch — surface immediately; partial output is useless.
                return err(
                    "DISK_FULL",
                    f"disk full while writing {dest}",
                    f"Processed {n_processed} files before failure. Free space and retry.",
                )
            if e.errno == errno.EACCES:
                # Record per-file, but keep going — maybe just one file is locked.
                msg = f"permission denied: {e}"
            else:
                msg = f"OSError: {e}"
            logger.warning("vp_anonymize_custom_data: %s -> %s", wav, msg)
            if len(error_list) < 10:
                error_list.append({"file": str(wav), "error": msg})
            else:
                # We still count errors beyond the max-10 cap.
                pass
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            logger.warning("vp_anonymize_custom_data: %s -> %s", wav, msg)
            if len(error_list) < 10:
                error_list.append({"file": str(wav), "error": msg})

    n_errors = len(error_list) + max(0, len(wav_files) - n_processed - n_skipped - len(error_list))

    return ok({
        "n_files_processed": n_processed,
        "n_files_skipped": n_skipped,
        "n_errors": n_errors,
        "output_path": str(out),
        "method": "B1",
        "alpha": alpha,
        "seed": seed,
        "errors": error_list,
    })
