"""vp_run_attacker — run a VoicePrivacy-conformant ASV attacker against anonymized speech.

Implements the three VP2024/2026 official attacker conditions:
  - "ignorant"      : pretrained VoxCeleb ECAPA, original enrollment, anonymized trials
  - "lazy_informed" : pretrained VoxCeleb ECAPA, anonymized enrollment + trials
  - "semi_informed" : ECAPA retrained on anonymized train-clean-360 (the ranking attacker)

For "semi_informed", the tool anonymizes train-clean-360 with the user's anonymizer_config,
trains a fresh ECAPA-TDNN (512ch, SpeechBrain VoxCeleb-on-LibriSpeech recipe), then scores trials.

Per-gender EER (female/male/overall) is reported as the primary VPC privacy metric.
Linkability (ZEBRA Cllr) is reported alongside for continuity with VP2020/VP2022 literature.

Failure surfaces: ATTACKER_TRAINING_FAILED, MODEL_DOWNLOAD_FAILED, DATA_MISSING,
GPU_OOM, INVALID_CONFIG, ATTACKER_DATA_MISMATCH, RECIPE_FAILED.

Source notes:
- VPC2024 Eval Plan v2.0: https://inria.hal.science/hal-04531444v1/
- Pretrained ECAPA: speechbrain/spkrec-ecapa-voxceleb (Apache 2.0)
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err

logger = logging.getLogger(__name__)

VALID_CONDITIONS = {"ignorant", "lazy_informed", "semi_informed"}
VALID_ARCHS = {"ecapa_tdnn"}  # v0.2: ecapa_plda_mix, resnet34_lora
PRETRAINED_ECAPA_HF = "speechbrain/spkrec-ecapa-voxceleb"


def _check_path(label: str, path_str: str, must_have_wav: bool = False) -> str | None:
    """Return None if path is fine; otherwise an error hint string."""
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        return f"{label} does not exist: {p}"
    if not p.is_dir():
        return f"{label} is not a directory: {p}"
    if must_have_wav:
        # Bounded wav check (mirror run_baseline.py pattern — short-circuit)
        try:
            for entry in p.rglob("*.wav"):
                return None
        except OSError:
            pass
        return f"{label} contains no .wav files: {p}"
    return None


def handle(
    anonymized_path: str,
    enrollment_path: str,
    trial_list: str,
    attacker_condition: str,
    attacker_arch: str = "ecapa_tdnn",
    anonymizer_config: str | None = None,
    seed: int = 42,
) -> ToolResult:
    """Run the requested attacker condition and return per-gender EER + linkability."""

    # ---- Validation ---------------------------------------------------------
    if attacker_condition not in VALID_CONDITIONS:
        if attacker_condition == "fully_informed":
            return err(
                "INVALID_CONFIG",
                "fully_informed is not a VPC official condition",
                "VPC defines ignorant / lazy_informed / semi_informed only. "
                "semi_informed is the strongest official attacker. For "
                "Attacker-Challenge-style open attackers, see post-v0.2 "
                "vp_run_attacker_open (not yet implemented).",
            )
        return err(
            "INVALID_CONFIG",
            f"attacker_condition must be one of {sorted(VALID_CONDITIONS)}, "
            f"got: {attacker_condition}",
            "Use 'semi_informed' for the official VP2026 ranking attacker.",
        )

    if attacker_arch not in VALID_ARCHS:
        return err(
            "INVALID_CONFIG",
            f"attacker_arch must be one of {sorted(VALID_ARCHS)}, got: {attacker_arch}",
            "Only ecapa_tdnn is supported in v0.1. ecapa_plda_mix and "
            "resnet34_lora are reserved for v0.2.",
        )

    if attacker_condition == "semi_informed" and not anonymizer_config:
        return err(
            "INVALID_CONFIG",
            "semi_informed condition requires anonymizer_config to anonymize train-clean-360",
            "Pass the path to the SpeechBrain-style YAML config that produced "
            "anonymized_path. Without it, the attacker cannot adapt to your "
            "specific anonymization system.",
        )

    for label, path in [("anonymized_path", anonymized_path), ("enrollment_path", enrollment_path)]:
        e = _check_path(label, path, must_have_wav=True)
        if e:
            return err("DATA_MISSING", e,
                       "Obtain VP2026 trial data via the official challenge process. "
                       "vpstack does not redistribute trial lists.")

    if not Path(trial_list).expanduser().exists():
        return err(
            "DATA_MISSING",
            f"trial_list not found: {trial_list}",
            "trial_list is a TSV with columns: enrollment_speaker, trial_utt, target (1/0).",
        )

    # ---- Dispatch to recipe entry point -------------------------------------
    module = "speechbrain_voice_anon.recipes.VP2026.attacker.run"
    cmd = [
        sys.executable, "-m", module,
        "--anonymized_path", str(anonymized_path),
        "--enrollment_path", str(enrollment_path),
        "--trial_list", str(trial_list),
        "--condition", attacker_condition,
        "--arch", attacker_arch,
        "--seed", str(seed),
        "--pretrained_hf", PRETRAINED_ECAPA_HF,
        "--output_format", "json",
    ]
    if anonymizer_config:
        cmd += ["--anonymizer_config", str(anonymizer_config)]

    logger.info("vp_run_attacker: invoking %s", " ".join(cmd))

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return err(
            "RECIPE_FAILED",
            "speechbrain_voice_anon attacker recipe not found",
            "The attacker recipe is implemented in v0.1.x — check that your "
            "speechbrain-voice-anon install is current. "
            "Install with: pip install -U speechbrain-voice-anon",
        )
    except Exception as e:
        return err("INTERNAL", f"subprocess launch failed: {e}", "")

    if proc.returncode != 0:
        # Inspect stderr for known failure patterns (no full stack traces in error
        # messages — privacy contract).
        tail = (proc.stderr or "")[-500:]
        if "OutOfMemoryError" in tail or "CUDA out of memory" in tail:
            return err(
                "GPU_OOM",
                f"GPU OOM during {attacker_condition} attacker run",
                "Reduce attacker_batch_size in attacker.yaml, or use a larger GPU. "
                "Semi-informed ECAPA training typically needs >=24GB VRAM at default batch.",
            )
        if "401" in tail or "403" in tail or "huggingface" in tail.lower():
            return err(
                "MODEL_DOWNLOAD_FAILED",
                f"could not download {PRETRAINED_ECAPA_HF}",
                "Run `huggingface-cli login` or set HF_TOKEN.",
            )
        if "TrainingDiverged" in tail or "loss is nan" in tail.lower():
            return err(
                "ATTACKER_TRAINING_FAILED",
                "ECAPA training diverged on anonymized train-clean-360",
                "Try seed=43, reduce learning rate in attacker.yaml, or verify "
                "the anonymized training set has reasonable speaker variety. "
                "Check ~/.vpstack/projects/<slug>/attacker_logs/ for the loss curve.",
            )
        if "TrialListMismatch" in tail or "speaker_id_not_found" in tail.lower():
            return err(
                "ATTACKER_DATA_MISMATCH",
                "trial list speakers don't match enrollment_path layout",
                "Verify enrollment/ subdirectory contains a folder per enrolled "
                "speaker, with names matching column 1 of trial_list.",
            )
        if "No such file" in tail or "FileNotFoundError" in tail:
            return err(
                "DATA_MISSING",
                "attacker recipe could not find a required file",
                f"Tail: {tail[:200]}",
            )
        return err(
            "RECIPE_FAILED",
            f"attacker recipe returned non-zero exit (condition={attacker_condition})",
            f"Tail of stderr: {tail[:200]}",
        )

    # Parse the recipe's JSON output. Recipes write a single JSON dict to stdout.
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return err(
            "RECIPE_FAILED",
            "attacker recipe completed but output was not parseable JSON",
            f"First 200 chars: {proc.stdout[:200]}",
        )

    # Required schema: per-gender EER + overall + linkability + config_hash
    required = {
        "eer_female", "eer_male", "eer_overall",
        "linkability_cllr", "linkability_min_cllr", "config_hash",
    }
    missing = required - set(data.keys())
    if missing:
        return err(
            "RECIPE_FAILED",
            f"attacker output missing required keys: {sorted(missing)}",
            "This is a recipe bug — file an issue with the config used.",
        )

    return ok({
        "attacker_condition": attacker_condition,
        "attacker_arch": attacker_arch,
        "eer_female": float(data["eer_female"]),
        "eer_male": float(data["eer_male"]),
        "eer_overall": float(data["eer_overall"]),
        "linkability_cllr": float(data["linkability_cllr"]),
        "linkability_min_cllr": float(data["linkability_min_cllr"]),
        "config_hash": str(data["config_hash"]),
        "anonymized_path": str(anonymized_path),
        "seed": seed,
    })
