"""ASV attacker recipe entrypoint — VP2026 official conditions.

STATUS: STUB in v0.1.0-dev. Contract is locked, implementation pending.

Invoked by vp_run_attacker (the MCP tool). Conditions:
  - "ignorant"      : pretrained VoxCeleb ECAPA, original enrollment, anonymized trials
  - "lazy_informed" : pretrained VoxCeleb ECAPA, anonymized enrollment + trials
  - "semi_informed" : ECAPA retrained on anonymized train-clean-360 (ranking attacker)

Usage:
    python -m speechbrain_voice_anon.recipes.VP2026.attacker.run \\
        --anonymized_path /path/to/anon \\
        --enrollment_path /path/to/enroll \\
        --trial_list /path/to/trials.tsv \\
        --condition semi_informed \\
        --arch ecapa_tdnn \\
        --seed 42 \\
        --anonymizer_config /path/to/config.yaml \\
        --output_format json

When implemented, must return a single JSON line on stdout containing:
    {
      "eer_female": float, "eer_male": float, "eer_overall": float,
      "linkability_cllr": float, "linkability_min_cllr": float,
      "config_hash": str
    }

Stderr: progress updates ("epoch X/Y, loss=Z, ETA T") every 30 seconds during
training (semi_informed condition can run 4-12 hours).

Re-implement from VP2024 Eval Plan PDF (https://inria.hal.science/hal-04531444v1/).
DO NOT port VP2024 GPLv3 code. Use:
  - SpeechBrain VoxCeleb ECAPA recipe (Apache 2.0) as starting architecture
  - speechbrain/spkrec-ecapa-voxceleb (Apache 2.0) for ignorant/lazy_informed conditions
  - VP2026 organizers' published baseline attacker checkpoint when URL is published

Reference impl notes for the eventual implementer:
  - For "ignorant": pretrained ECAPA + cosine scoring, enrollment from original audio
  - For "lazy_informed": same model, but enrollment is anonymized speech
  - For "semi_informed":
    1. Anonymize train-clean-360 using anonymizer_config (calls back into SpeechBrain pipeline)
    2. Train fresh ECAPA-TDNN 512ch on anonymized train-clean-360 (~4-8h on single GPU)
    3. Anonymize enrollment, score trials
  - Compute per-gender EER (female/male split per VP2026 trial list)
  - Compute linkability via ZEBRA toolkit (https://github.com/Voice-Privacy-Challenge/zebra)
  - Honor torch.use_deterministic_algorithms(True) if hparams request it
  - Stream "[attacker:semi_informed] epoch X/Y loss=L ETA T" to stderr every 30s
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="VP2026 attacker — STUB.")
    parser.add_argument("--anonymized_path", required=True)
    parser.add_argument("--enrollment_path", required=True)
    parser.add_argument("--trial_list", required=True)
    parser.add_argument("--condition", required=True,
                        choices=["ignorant", "lazy_informed", "semi_informed"])
    parser.add_argument("--arch", default="ecapa_tdnn")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--anonymizer_config", default=None)
    parser.add_argument("--pretrained_hf", default="speechbrain/spkrec-ecapa-voxceleb")
    parser.add_argument("--output_format", choices=["json", "human"], default="human")
    args = parser.parse_args()

    msg = (
        f"VP2026 attacker (condition={args.condition}, arch={args.arch}) is not "
        f"yet implemented in v0.1.0-dev. Tracking issue: vpstack/vpstack#TODO. "
        f"Contract is locked — see speechbrain_voice_anon/recipes/VP2026/attacker/run.py "
        f"docstring for the eventual implementation specification."
    )

    if args.output_format == "json":
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "BASELINE_NOT_IMPLEMENTED",
                "message": msg,
                "hint": "B1 McAdams baseline IS implemented. /vp-attack against the B1 "
                        "anonymized output is also stubbed pending this recipe.",
            },
        }))
    else:
        print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
