"""vp_generate_trial_file — generate a Kaldi-style ASV trial file from a WAV directory.

Practitioners working with custom datasets (medical, call-center, podcasts) must create
trial files before running vp_run_attacker. Creating them by hand is error-prone; this
tool automates the process from any directory of WAVs organised either as:

  Option A — flat directory, filename convention:  {speaker_id}_{utterance_id}.wav
  Option B — subdirectory-per-speaker:             {speaker_id}/{utterance_id}.wav

Output format (one line per pair, space-separated):
    {enrollment_utt_id} {trial_utt_id} {target|nontarget}

where utterance IDs are relative paths from *audio_dir*, without the .wav extension —
matching the Kaldi / SpeechBrain trial-list convention used by vp_run_attacker.

Pair generation is reproducible from *seed* via random.Random (no numpy dependency).

Failure surfaces: DATA_MISSING, INVALID_CONFIG, DISK_FULL, PERMISSION_DENIED, INTERNAL.
"""

from __future__ import annotations

import errno
import logging
import os
import random
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _find_wavs_bounded(root: Path, max_depth: int = 8, max_dirs: int = 5000) -> list[Path]:
    """Bounded directory walk returning all .wav paths under *root*.

    Never follows symlinks. Stops after *max_dirs* directories visited or
    *max_depth* levels of nesting, whichever comes first.
    """
    found: list[Path] = []
    dirs_visited = [0]

    def _walk(path: Path, depth: int) -> None:
        if depth < 0 or dirs_visited[0] >= max_dirs:
            return
        dirs_visited[0] += 1
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


def _infer_speaker_id(wav: Path, audio_root: Path, source: str) -> str | None:
    """Return the speaker ID string for *wav*, or None if it cannot be inferred.

    Parameters
    ----------
    wav:
        Absolute path to the WAV file.
    audio_root:
        Root directory passed as *audio_dir*.
    source:
        "subdirectory" — speaker ID is the name of the first directory component
        below *audio_root* (e.g. audio_root/spk001/utt1.wav -> "spk001").
        "filename_prefix" — speaker ID is the part of the filename before the
        first underscore (e.g. spk001_utt1.wav -> "spk001").
    """
    rel = wav.relative_to(audio_root)
    if source == "subdirectory":
        # rel.parts[0] is the speaker subdirectory; parts[1:] is the utterance path.
        if len(rel.parts) < 2:
            return None  # WAV is directly in audio_root — no subdirectory speaker label.
        return rel.parts[0]
    elif source == "filename_prefix":
        stem = wav.stem  # filename without extension
        if "_" not in stem:
            return None  # No underscore — cannot split speaker from utterance.
        return stem.split("_", 1)[0]
    return None


def _utt_id(wav: Path, audio_root: Path) -> str:
    """Return the utterance ID: relative path from *audio_root*, without .wav extension."""
    rel = wav.relative_to(audio_root)
    # Drop the .wav suffix from the final component.
    parts = list(rel.parts)
    parts[-1] = wav.stem
    return "/".join(parts)


# --------------------------------------------------------------------------- #
# Public handle()
# --------------------------------------------------------------------------- #

def handle(
    audio_dir: str,
    output_path: str,
    speaker_id_source: str = "subdirectory",
    n_target_pairs_per_speaker: int = 5,
    n_nontarget_pairs_per_speaker: int = 5,
    seed: int = 42,
    enrollment_fraction: float = 0.3,
    min_utterances_per_speaker: int = 2,
) -> ToolResult:
    """Generate a Kaldi-style ASV trial file from a directory of WAV files.

    Parameters
    ----------
    audio_dir:
        Root directory of WAV files. Two layouts are supported:

        * **subdirectory** (default): ``{speaker_id}/{utterance_id}.wav``
        * **filename_prefix**: ``{speaker_id}_{utterance_id}.wav`` (flat dir)

    output_path:
        Destination path for the trial file. Parent directories are created if
        absent.
    speaker_id_source:
        ``"subdirectory"`` or ``"filename_prefix"``. Controls how speaker IDs
        are extracted. See above.
    n_target_pairs_per_speaker:
        Maximum number of same-speaker (target) pairs to emit per speaker.
        Actual count may be lower for speakers with few utterances.
    n_nontarget_pairs_per_speaker:
        Maximum number of cross-speaker (nontarget) pairs to emit per speaker.
    seed:
        Random seed for reproducible pair sampling.
    enrollment_fraction:
        Fraction of each speaker's utterances reserved for enrollment. The
        remainder forms the trial (test) pool. Rounded down; at least 1 utterance
        is always placed in enrollment.
    min_utterances_per_speaker:
        Speakers with fewer utterances than this threshold are skipped. Minimum
        useful value is 2 (1 enrollment + 1 trial).

    Returns
    -------
    ToolResult with::

        {
            "n_speakers":           int,
            "n_skipped_speakers":   int,
            "n_target_pairs":       int,
            "n_nontarget_pairs":    int,
            "output_path":          str,
            "enrollment_utterances": int,
            "trial_utterances":     int
        }
    """
    # ------------------------------------------------------------------
    # 1. Validate speaker_id_source
    # ------------------------------------------------------------------
    valid_sources = {"subdirectory", "filename_prefix"}
    if speaker_id_source not in valid_sources:
        return err(
            "INVALID_CONFIG",
            f"speaker_id_source must be one of {sorted(valid_sources)}, got: {speaker_id_source!r}",
            "Use 'subdirectory' for {speaker_id}/{utt}.wav layout, "
            "or 'filename_prefix' for {speaker_id}_{utt}.wav flat layout.",
        )

    # ------------------------------------------------------------------
    # 2. Validate numeric parameters
    # ------------------------------------------------------------------
    if enrollment_fraction <= 0.0 or enrollment_fraction >= 1.0:
        return err(
            "INVALID_CONFIG",
            f"enrollment_fraction must be in (0.0, 1.0), got: {enrollment_fraction}",
            "Typical values: 0.3 (30 % enrollment, 70 % trial).",
        )
    if min_utterances_per_speaker < 2:
        return err(
            "INVALID_CONFIG",
            f"min_utterances_per_speaker must be >= 2, got: {min_utterances_per_speaker}",
            "Need at least 1 enrollment utterance and 1 trial utterance per speaker.",
        )
    if n_target_pairs_per_speaker < 0 or n_nontarget_pairs_per_speaker < 0:
        return err(
            "INVALID_CONFIG",
            "n_target_pairs_per_speaker and n_nontarget_pairs_per_speaker must be >= 0",
            "",
        )

    # ------------------------------------------------------------------
    # 3. Resolve and validate audio_dir
    # ------------------------------------------------------------------
    adir = Path(audio_dir).expanduser().resolve()
    if not adir.exists():
        return err(
            "DATA_MISSING",
            f"audio_dir does not exist: {adir}",
            "Provide an absolute path to a directory containing WAV files.",
        )
    if not adir.is_dir():
        return err(
            "DATA_MISSING",
            f"audio_dir is not a directory: {adir}",
            "Pass a directory, not a file path.",
        )

    wav_files = _find_wavs_bounded(adir)
    if not wav_files:
        return err(
            "DATA_MISSING",
            f"audio_dir contains no .wav files within 8 directory levels: {adir}",
            "Ensure the directory contains WAV audio. Other formats are not scanned.",
        )

    # ------------------------------------------------------------------
    # 4. Group utterances by speaker
    # ------------------------------------------------------------------
    speaker_to_wavs: dict[str, list[Path]] = {}
    for wav in wav_files:
        spk = _infer_speaker_id(wav, adir, speaker_id_source)
        if spk is None:
            logger.debug("vp_generate_trial_file: cannot infer speaker for %s — skipping", wav)
            continue
        speaker_to_wavs.setdefault(spk, []).append(wav)

    if not speaker_to_wavs:
        source_hint = (
            "directory layout ({speaker_id}/{utt}.wav)"
            if speaker_id_source == "subdirectory"
            else "filename convention ({speaker_id}_{utt}.wav)"
        )
        return err(
            "DATA_MISSING",
            f"Could not infer any speaker IDs from audio_dir using speaker_id_source={speaker_id_source!r}",
            f"Expected {source_hint}. "
            "Check that WAV files follow the expected naming or directory structure.",
        )

    # ------------------------------------------------------------------
    # 5. Split enrollment / trial per speaker, drop speakers with too few utts
    # ------------------------------------------------------------------
    rng = random.Random(seed)

    # Deterministic sort before shuffling so results are seed-reproducible
    # regardless of filesystem iteration order.
    for spk in speaker_to_wavs:
        speaker_to_wavs[spk].sort(key=lambda p: str(p))

    enrollment: dict[str, list[str]] = {}   # speaker -> list of utt_id
    trial_pool: dict[str, list[str]] = {}   # speaker -> list of utt_id
    n_skipped = 0

    for spk, wavs in sorted(speaker_to_wavs.items()):
        if len(wavs) < min_utterances_per_speaker:
            n_skipped += 1
            logger.debug(
                "vp_generate_trial_file: speaker %s has only %d utterances (< %d) — skipping",
                spk, len(wavs), min_utterances_per_speaker,
            )
            continue

        shuffled = list(wavs)
        rng.shuffle(shuffled)

        n_enroll = max(1, int(len(shuffled) * enrollment_fraction))
        # Leave at least 1 utterance for the trial pool.
        n_enroll = min(n_enroll, len(shuffled) - 1)

        enroll_wavs = shuffled[:n_enroll]
        trial_wavs = shuffled[n_enroll:]

        enrollment[spk] = [_utt_id(w, adir) for w in enroll_wavs]
        trial_pool[spk] = [_utt_id(w, adir) for w in trial_wavs]

    if not enrollment:
        return err(
            "DATA_MISSING",
            f"All speakers were skipped (all had fewer than {min_utterances_per_speaker} utterances)",
            f"Lower min_utterances_per_speaker (currently {min_utterances_per_speaker}) "
            "or supply a dataset with more utterances per speaker.",
        )

    speakers = sorted(enrollment.keys())

    # ------------------------------------------------------------------
    # 6. Generate target pairs (same speaker)
    # ------------------------------------------------------------------
    target_pairs: list[tuple[str, str]] = []  # (enrollment_utt, trial_utt)

    for spk in speakers:
        e_utts = enrollment[spk]
        t_utts = trial_pool[spk]
        # Cartesian product of enrollment × trial for this speaker.
        all_pairs = [(e, t) for e in e_utts for t in t_utts]
        rng.shuffle(all_pairs)
        target_pairs.extend(all_pairs[:n_target_pairs_per_speaker])

    # ------------------------------------------------------------------
    # 7. Generate nontarget pairs (cross-speaker)
    # ------------------------------------------------------------------
    nontarget_pairs: list[tuple[str, str]] = []  # (enrollment_utt, trial_utt)

    for spk in speakers:
        e_utts = enrollment[spk]
        # Cross-speaker: pick trial utterances from other speakers.
        other_speakers = [s for s in speakers if s != spk]
        if not other_speakers:
            continue

        # Build a pool of cross-speaker trial utterances.
        cross_pool: list[str] = []
        for other in other_speakers:
            cross_pool.extend(trial_pool[other])

        rng.shuffle(cross_pool)

        # Sample (enrollment × cross_pool) pairs up to the per-speaker cap.
        candidates: list[tuple[str, str]] = []
        for e in e_utts:
            for t in cross_pool:
                candidates.append((e, t))
                if len(candidates) >= n_nontarget_pairs_per_speaker * 10:
                    break  # Avoid huge cartesian explosion; we'll shuffle and slice.
            if len(candidates) >= n_nontarget_pairs_per_speaker * 10:
                break

        rng.shuffle(candidates)
        nontarget_pairs.extend(candidates[:n_nontarget_pairs_per_speaker])

    # ------------------------------------------------------------------
    # 8. Combine and shuffle all pairs
    # ------------------------------------------------------------------
    all_lines: list[str] = []
    for enr, trl in target_pairs:
        all_lines.append(f"{enr} {trl} target")
    for enr, trl in nontarget_pairs:
        all_lines.append(f"{enr} {trl} nontarget")

    rng.shuffle(all_lines)

    # ------------------------------------------------------------------
    # 9. Write trial file
    # ------------------------------------------------------------------
    out = Path(output_path).expanduser().resolve()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno == errno.ENOSPC:
            return err("DISK_FULL", "no space left on device while creating output directory", "Free disk space.")
        if e.errno == errno.EACCES:
            return err("PERMISSION_DENIED", f"cannot create parent directory for {out}", "Check permissions.")
        return err("INTERNAL", f"mkdir failed: {e}", "")

    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(all_lines))
            if all_lines:
                f.write("\n")
    except OSError as e:
        if e.errno == errno.ENOSPC:
            return err("DISK_FULL", f"disk full while writing trial file: {out}", "Free disk space.")
        if e.errno == errno.EACCES:
            return err("PERMISSION_DENIED", f"cannot write trial file: {out}", "Check file permissions.")
        return err("INTERNAL", f"write failed: {e}", "")

    # ------------------------------------------------------------------
    # 10. Compute summary statistics
    # ------------------------------------------------------------------
    total_enrollment_utts = sum(len(v) for v in enrollment.values())
    total_trial_utts = sum(len(v) for v in trial_pool.values())

    return ok({
        "n_speakers": len(speakers),
        "n_skipped_speakers": n_skipped,
        "n_target_pairs": len(target_pairs),
        "n_nontarget_pairs": len(nontarget_pairs),
        "output_path": str(out),
        "enrollment_utterances": total_enrollment_utts,
        "trial_utterances": total_trial_utts,
    })
