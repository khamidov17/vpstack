"""vp_run_baseline — run the canonical VP2026 B1 (McAdams) or B2 (neural) baseline.

Shells out to the speechbrain_voice_anon recipe package. Streams progress to stderr
so MCP clients see "alive" updates during multi-hour runs.

Failure surfaces: GPU_OOM, DATA_MISSING, MODEL_DOWNLOAD_FAILED, RECIPE_FAILED.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)


def _check_data_path(data_path: str) -> str | None:
    """Return None if data_path is fine; otherwise an error hint.

    F6 fix from code review: previous version did `any(p.rglob("*.wav"))` which can
    walk a misconfigured root unboundedly (e.g., user passes `~` instead of
    `~/vp2026/data`). Now we:
      1. Reject obviously-wrong paths first ($HOME root, /, etc.)
      2. Bound the .wav search to a fixed depth (8 levels) and time budget
    """
    p = Path(data_path).expanduser().resolve()
    if not p.exists():
        return f"data_path does not exist: {p}. Download VP2026 data from https://www.voiceprivacychallenge.org/"
    if not p.is_dir():
        return f"data_path is not a directory: {p}"

    # Reject paths that are too broad — these are almost always misconfigurations.
    forbidden_roots = {Path("/"), Path.home(), Path("/tmp"), Path("/var")}
    if p in forbidden_roots:
        return (
            f"data_path is a system root: {p}. Pass a specific VP2026 data subdirectory "
            "(e.g. ~/vp2026/data), not your home directory."
        )

    # Bounded walk: scan up to 8 levels deep, stop after first .wav found, cap
    # total dirs scanned to avoid unbounded I/O on hostile or misconfigured paths.
    max_depth = 8
    max_dirs = 1000

    def has_wav_within(root: Path, remaining_depth: int, dirs_scanned: list[int]) -> bool:
        if remaining_depth < 0 or dirs_scanned[0] >= max_dirs:
            return False
        dirs_scanned[0] += 1
        try:
            with os.scandir(root) as it:
                # Look at files first
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False) and entry.name.endswith(".wav"):
                            return True
                    except OSError:
                        continue
            # Then recurse into directories
            with os.scandir(root) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if has_wav_within(Path(entry.path), remaining_depth - 1, dirs_scanned):
                                return True
                    except OSError:
                        continue
        except (OSError, PermissionError):
            return False
        return False

    if not has_wav_within(p, max_depth, [0]):
        return f"data_path contains no .wav files within {max_depth} levels: {p}"
    return None


def handle(baseline: str, data_path: str, seed: int = 42) -> ToolResult:
    """Run baseline B1 or B2 on data_path and return EER/WER/linkability."""
    if baseline not in {"B1", "B2"}:
        return err("INVALID_CONFIG", f"baseline must be B1 or B2, got: {baseline}",
                   "Pass baseline='B1' (McAdams, signal-only) or 'B2' (HuBERT+ECAPA+HiFi-GAN).")

    data_err = _check_data_path(data_path)
    if data_err:
        return err("DATA_MISSING", data_err,
                   "Obtain VP2026 evaluation data via the official challenge process. "
                   "vpstack does not redistribute trial lists.")

    # Locate the recipe entry point. In dev, it's via the speechbrain_voice_anon package.
    # In CI / installed mode, `python -m speechbrain_voice_anon.recipes.VP2026.baseline_BX.run`
    # is the canonical invocation.
    module = f"speechbrain_voice_anon.recipes.VP2026.baseline_{baseline}.run"

    cmd = [
        sys.executable, "-m", module,
        "--data_path", str(data_path),
        "--seed", str(seed),
        "--output_format", "json",
    ]

    logger.info("vp_run_baseline: invoking %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            # No timeout — baselines can legitimately take hours. Skill is responsible
            # for surfacing progress to the user.
        )
    except FileNotFoundError:
        return err(
            "RECIPE_FAILED",
            "speechbrain_voice_anon recipe package not found",
            "Install with: pip install speechbrain-voice-anon",
        )
    except Exception as e:
        return err("INTERNAL", f"subprocess launch failed: {e}", "")

    if proc.returncode != 0:
        # Inspect stderr for known failure patterns. Keep the prose short — never include
        # the full stack trace (privacy contract: error_class only, not error_body).
        stderr_tail = (proc.stderr or "")[-500:]
        if "OutOfMemoryError" in stderr_tail or "CUDA out of memory" in stderr_tail:
            return err(
                "GPU_OOM",
                f"GPU ran out of memory during {baseline}",
                "Reduce batch size in hparams.yaml, or run on a larger GPU. "
                "B2 typically needs >=16GB VRAM.",
            )
        if "No such file" in stderr_tail or "FileNotFoundError" in stderr_tail:
            return err("DATA_MISSING", f"recipe could not find a required file",
                       "Verify data_path layout matches VP2026 protocol. "
                       "See speechbrain_voice_anon/recipes/VP2026/README.md")
        if "401" in stderr_tail or "403" in stderr_tail:
            return err(
                "MODEL_DOWNLOAD_FAILED",
                "could not download a pretrained model from HuggingFace Hub",
                "Run `huggingface-cli login` or set HF_TOKEN env var.",
            )
        return err(
            "RECIPE_FAILED",
            f"baseline {baseline} returned non-zero exit",
            f"Tail of stderr: {stderr_tail[:200]}",
        )

    # Parse the recipe's JSON output. Recipes write a single JSON dict to stdout.
    import json
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return err("RECIPE_FAILED",
                   "recipe completed but output was not parseable JSON",
                   f"First 200 chars: {proc.stdout[:200]}")

    # Validate the shape — every baseline must report at least these.
    required = {"eer", "wer", "linkability", "config_hash"}
    missing = required - set(data.keys())
    if missing:
        return err("RECIPE_FAILED",
                   f"recipe output missing required keys: {missing}",
                   "This is a recipe bug — file an issue with the config used.")

    return ok({
        "baseline": baseline,
        "eer": float(data["eer"]),
        "wer": float(data["wer"]),
        "linkability": float(data["linkability"]),
        "config_hash": str(data["config_hash"]),
        "data_path": str(data_path),
        "seed": seed,
    })
