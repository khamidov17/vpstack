"""vp_estimate_compute — estimate GPU hours, VRAM, disk, and cost for a VP2026 run.

Practitioners planning infrastructure (cloud GPU rental, storage allocation) need
rough numbers before committing to a job. This tool returns ballpark estimates based
on empirically observed VP2026 baseline performance; it explicitly warns that actual
numbers vary and a small benchmark run should always be done first.

Failure surfaces: INVALID_CONFIG.
"""

from __future__ import annotations

import logging
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_METHODS = {"B1", "B2", "custom_neural"}
_VALID_TASKS = {
    "anonymize",
    "attacker_ignorant",
    "attacker_lazy_informed",
    "attacker_semi_informed",
    "full_eval",
}
_VALID_GPU_TYPES = {"V100", "A100", "A10G", "RTX3090", "RTX4090", "CPU"}

# GPU wall-clock multiplier relative to A100 = 1.0.
# Higher = slower than A100.
_GPU_SLOWDOWN: dict[str, float] = {
    "A100":   1.0,
    "RTX4090": 1.3,
    "A10G":   1.5,
    "RTX3090": 1.8,
    "V100":   2.0,
    "CPU":    400.0,  # B1 only; neural methods aren't feasible on CPU
}

# Rough on-demand cloud cost per hour (USD). Very approximate — spot prices vary.
_GPU_COST_USD_PER_HOUR: dict[str, float] = {
    "A100":   3.50,
    "RTX4090": 0.80,
    "A10G":   1.50,
    "RTX3090": 0.50,
    "V100":   2.50,
    "CPU":    0.05,
}

# ---------------------------------------------------------------------------
# Per-method inference reference values (all at A100 baseline, per hour of audio)
# ---------------------------------------------------------------------------

# B1 (McAdams) — CPU-only, ~8× realtime. 1h audio → 0.125h wall clock.
# GPU hours = 0 (no GPU needed). CPU wall clock drives cost.
_B1_WALL_CLOCK_PER_AUDIO_HOUR_CPU = 1.0 / 8.0   # 0.125h per audio hour
_B1_VRAM_GB = 0.0                                  # no GPU
_B1_DISK_RATIO = 1.0                               # output ≈ input size

# B2 (HuBERT + ECAPA + HiFi-GAN inference) — ~50× realtime on A100.
# 1h audio → 0.02h GPU time on A100.
_B2_GPU_HOURS_PER_AUDIO_HOUR_A100 = 1.0 / 50.0   # 0.02h per audio hour
_B2_VRAM_GB = 12.0
_B2_DISK_RATIO = 1.0

# custom_neural — conservative estimate: assume ~30× realtime on A100
# (user has a custom architecture; we don't know its profile).
_CUSTOM_VRAM_GB = 16.0
_CUSTOM_GPU_HOURS_PER_AUDIO_HOUR_A100 = 1.0 / 30.0
_CUSTOM_DISK_RATIO = 1.5  # may produce intermediate representations

# Attacker training (semi-informed condition).
# Requires anonymizing train-clean-360 (~360h) + ECAPA retraining.
_ATTACKER_ANON_HOURS = 360.0           # approximate VP train set size
_ATTACKER_ANON_GPU_HOURS_A100 = _ATTACKER_ANON_HOURS * _B2_GPU_HOURS_PER_AUDIO_HOUR_A100  # ~7.2h
_ATTACKER_ECAPA_TRAINING_GPU_HOURS_A100 = 4.0  # empirical VP2024 estimate
_ATTACKER_TOTAL_GPU_HOURS_A100 = _ATTACKER_ANON_GPU_HOURS_A100 + _ATTACKER_ECAPA_TRAINING_GPU_HOURS_A100
_ATTACKER_VRAM_GB = 16.0   # ECAPA training needs more headroom than inference
_ATTACKER_DISK_RATIO = 3.0  # original + anonymized + checkpoints

# Full eval: anonymize dev set (~10h) + 3 attacker conditions.
_FULL_EVAL_DEV_HOURS = 10.0
_FULL_EVAL_DEV_GPU_HOURS_A100 = _FULL_EVAL_DEV_HOURS * _B2_GPU_HOURS_PER_AUDIO_HOUR_A100
_FULL_EVAL_TOTAL_GPU_HOURS_A100 = _FULL_EVAL_DEV_GPU_HOURS_A100 + _ATTACKER_TOTAL_GPU_HOURS_A100
_FULL_EVAL_VRAM_GB = 16.0
_FULL_EVAL_DISK_RATIO = 4.0  # dev + train + all anon outputs + checkpoints


def _disk_for_audio(total_hours_audio: float, ratio: float) -> float:
    """Return rough disk estimate in GB.

    Assumes 16-bit mono WAV at 16 kHz ≈ 115.2 MB/h ≈ 0.1125 GB/h.
    We round to 0.12 GB/h for conservative headroom.
    """
    audio_gb_per_hour = 0.12
    return round(total_hours_audio * audio_gb_per_hour * ratio, 2)


def handle(
    total_hours_audio: float,
    num_speakers: int,
    method: str = "B2",
    task: str = "anonymize",
    gpu_type: str = "A100",
) -> ToolResult:
    """Estimate compute requirements for a VP2026 pipeline run.

    Args:
        total_hours_audio: Total hours of audio to process.
        num_speakers: Number of unique speakers in the dataset.
        method: Anonymization method — "B1", "B2", or "custom_neural".
        task: Pipeline task — "anonymize", "attacker_ignorant",
            "attacker_lazy_informed", "attacker_semi_informed", or "full_eval".
        gpu_type: Target GPU — "V100", "A100", "A10G", "RTX3090", "RTX4090",
            or "CPU". B1 is CPU-only regardless of this parameter.

    Returns:
        ok() with gpu_hours, vram_gb_required, disk_gb_required,
        wall_clock_hours_single_gpu, estimated_cost_usd, bottleneck, and notes;
        or err("INVALID_CONFIG", ...) for bad inputs.
    """
    # --- Input validation -----------------------------------------------------
    if total_hours_audio <= 0:
        return err(
            "INVALID_CONFIG",
            f"total_hours_audio must be positive, got {total_hours_audio}",
            "Pass the total duration of your audio dataset in hours (e.g. 10.5).",
        )
    if num_speakers <= 0:
        return err(
            "INVALID_CONFIG",
            f"num_speakers must be positive, got {num_speakers}",
            "Pass the number of unique speakers in your dataset (e.g. 100).",
        )
    if method not in _VALID_METHODS:
        return err(
            "INVALID_CONFIG",
            f"method must be one of {sorted(_VALID_METHODS)}, got {method!r}",
            "Use 'B1' (McAdams), 'B2' (HuBERT+ECAPA+HiFi-GAN), or 'custom_neural'.",
        )
    if task not in _VALID_TASKS:
        return err(
            "INVALID_CONFIG",
            f"task must be one of {sorted(_VALID_TASKS)}, got {task!r}",
            "Choose from: anonymize, attacker_ignorant, attacker_lazy_informed, "
            "attacker_semi_informed, full_eval.",
        )
    if gpu_type not in _VALID_GPU_TYPES:
        return err(
            "INVALID_CONFIG",
            f"gpu_type must be one of {sorted(_VALID_GPU_TYPES)}, got {gpu_type!r}",
            "Supported types: V100, A100, A10G, RTX3090, RTX4090, CPU.",
        )

    # --- B1 is always CPU-only ------------------------------------------------
    effective_gpu_type = gpu_type
    b1_forced_cpu_note: str | None = None
    if method == "B1":
        effective_gpu_type = "CPU"
        if gpu_type != "CPU":
            b1_forced_cpu_note = (
                f"B1 (McAdams) runs on CPU only — ignoring requested gpu_type={gpu_type!r}. "
                "No GPU provisioning needed."
            )

    slowdown = _GPU_SLOWDOWN[effective_gpu_type]
    cost_per_hour = _GPU_COST_USD_PER_HOUR[effective_gpu_type]

    # --- Compute base estimates at A100 rate, then scale ----------------------
    notes: list[str] = []
    gpu_hours_a100: float
    vram_gb: float
    disk_ratio: float
    bottleneck: str

    if method == "B1":
        # Pure CPU — report wall clock, not GPU hours.
        gpu_hours_a100 = 0.0
        vram_gb = _B1_VRAM_GB
        disk_ratio = _B1_DISK_RATIO
        # Wall clock scales with slowdown relative to "A100" nominal.
        # For B1 the nominal is CPU speed, so we don't use the A100 ref.
        wall_clock_hours = total_hours_audio * _B1_WALL_CLOCK_PER_AUDIO_HOUR_CPU
        bottleneck = "inference"
        notes.append("B1 (McAdams) runs on CPU only. No GPU required.")

    elif method in {"B2", "custom_neural"}:
        if method == "B2":
            gpu_hours_a100_per_audio_hour = _B2_GPU_HOURS_PER_AUDIO_HOUR_A100
            vram_gb = _B2_VRAM_GB
            disk_ratio = _B2_DISK_RATIO
        else:  # custom_neural
            gpu_hours_a100_per_audio_hour = _CUSTOM_GPU_HOURS_PER_AUDIO_HOUR_A100
            vram_gb = _CUSTOM_VRAM_GB
            disk_ratio = _CUSTOM_DISK_RATIO
            notes.append(
                "custom_neural estimates assume ~30x realtime on A100. "
                "Your architecture may differ significantly — benchmark on 30 min of audio first."
            )

        # Select base GPU hours based on task.
        if task == "anonymize":
            gpu_hours_a100 = total_hours_audio * gpu_hours_a100_per_audio_hour
            bottleneck = "inference"

        elif task in {"attacker_ignorant", "attacker_lazy_informed"}:
            # Ignorant and lazy-informed: run the attacker ASV on anonymized audio.
            # No retraining — just inference through the ASV model.
            # Approximate: ~2x the anonymization cost (anon + ASV scoring).
            gpu_hours_a100 = total_hours_audio * gpu_hours_a100_per_audio_hour * 2.0
            disk_ratio = max(disk_ratio, 2.0)
            bottleneck = "inference"
            notes.append(
                f"task={task!r}: attacker runs ASV inference on anonymized audio (no retraining). "
                "Estimate includes anonymization pass + ASV scoring."
            )

        elif task == "attacker_semi_informed":
            # Semi-informed: anonymize train-clean-360 + retrain ECAPA + score dev.
            # This dominates regardless of total_hours_audio passed.
            gpu_hours_a100 = _ATTACKER_TOTAL_GPU_HOURS_A100
            vram_gb = max(vram_gb, _ATTACKER_VRAM_GB)
            disk_ratio = max(disk_ratio, _ATTACKER_DISK_RATIO)
            bottleneck = "attacker_training"
            notes.append(
                "task=attacker_semi_informed: estimate covers anonymizing train-clean-360 "
                f"(~{_ATTACKER_ANON_HOURS:.0f}h audio) + ECAPA retraining (~{_ATTACKER_ECAPA_TRAINING_GPU_HOURS_A100:.0f}h GPU). "
                "This is the official VP2026 ranking condition."
            )
            notes.append(
                f"total_hours_audio={total_hours_audio}h is used for dev-set scoring only "
                "(minor compared to train-set anonymization)."
            )

        elif task == "full_eval":
            gpu_hours_a100 = _FULL_EVAL_TOTAL_GPU_HOURS_A100
            vram_gb = max(vram_gb, _FULL_EVAL_VRAM_GB)
            disk_ratio = max(disk_ratio, _FULL_EVAL_DISK_RATIO)
            bottleneck = "attacker_training"
            notes.append(
                "task=full_eval: anonymize dev set (~10h) + all 3 attacker conditions "
                "(ignorant, lazy-informed, semi-informed). Semi-informed dominates."
            )

        else:
            # Unreachable given the earlier validation, but be safe.
            return err("INTERNAL", f"unhandled task: {task}", "")

        # Scale wall clock for the selected GPU type.
        wall_clock_hours = gpu_hours_a100 * slowdown

    else:
        return err("INTERNAL", f"unhandled method: {method}", "")

    # Disk estimate.
    disk_gb = _disk_for_audio(total_hours_audio, disk_ratio)
    # For attacker tasks the train set dominates disk.
    if task in {"attacker_semi_informed", "full_eval"}:
        disk_gb = max(disk_gb, _disk_for_audio(_ATTACKER_ANON_HOURS, disk_ratio))

    # GPU hours for the selected GPU type (B1 stays 0).
    gpu_hours_actual = gpu_hours_a100 * slowdown if method != "B1" else 0.0

    # Cost estimate.
    if method == "B1":
        estimated_cost_usd = wall_clock_hours * cost_per_hour
    else:
        estimated_cost_usd = gpu_hours_actual * cost_per_hour

    # --- Notes ----------------------------------------------------------------
    if b1_forced_cpu_note:
        notes.insert(0, b1_forced_cpu_note)

    if method != "B1" and effective_gpu_type == "CPU":
        notes.append(
            f"Neural methods ({method}) on CPU are not practical for production runs. "
            "GPU is strongly recommended."
        )

    notes.append(
        "IMPORTANT: These are rough estimates only. Actual times vary by: "
        "audio quality, utterance length distribution, batch size, disk I/O speed, "
        "network speed for model downloads. Always benchmark on a small sample "
        "(e.g. 30 min of audio) before provisioning infrastructure for a full run."
    )

    if num_speakers > 500:
        notes.append(
            f"num_speakers={num_speakers}: large speaker set. ECAPA embedding extraction "
            "is per-utterance so speaker count itself has minimal effect on GPU time, "
            "but trial-list generation for ASV scoring scales as O(speakers^2) — "
            "budget extra time for scoring at this scale."
        )

    return ok({
        "method": method,
        "task": task,
        "gpu_type": effective_gpu_type,
        "total_hours_audio": total_hours_audio,
        "num_speakers": num_speakers,
        "gpu_hours": round(gpu_hours_actual, 2),
        "vram_gb_required": round(vram_gb, 1),
        "disk_gb_required": round(disk_gb, 1),
        "wall_clock_hours_single_gpu": round(wall_clock_hours, 2),
        "estimated_cost_usd": round(estimated_cost_usd, 2),
        "bottleneck": bottleneck,
        "notes": notes,
    })
