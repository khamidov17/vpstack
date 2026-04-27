"""B2 recipe entrypoint: neural anonymization pipeline (HuBERT + ECAPA + HiFi-GAN).

STATUS: NOT YET IMPLEMENTED in v0.1.0-dev. This module is a stub that documents
the contract; the full implementation is week-1+ work that needs:
  - GPU access for inference + fine-tuning
  - Reproducibility verification (CUDA non-determinism handling)
  - HuggingFace Hub model downloads (HuBERT, ECAPA-TDNN)
  - HiFi-GAN anonymization vocoder (jik876 reference + LibriTTS fine-tune)

When implemented, this entrypoint must:
  1. Accept the same CLI args as baseline_B1/run.py (--data_path, --seed, --output_format)
  2. Stream progress to stderr every 30s
  3. Return a single JSON line on stdout: {eer, wer, linkability, config_hash}
  4. Re-implement from VP2024 Eval Plan PDF — DO NOT port VP2024 GPLv3 code
  5. Use lazy HF Hub downloads (huggingface_hub.snapshot_download) for weights
  6. Honor `torch.use_deterministic_algorithms(True)` if hparams.yaml requests determinism
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="VP2026 B2 (neural) baseline — NOT YET IMPLEMENTED.")
    parser.add_argument("--data_path", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output_format", choices=["json", "human"], default="human")
    args = parser.parse_args()

    msg = (
        "baseline_B2 is not yet implemented in v0.1.0-dev. "
        "Track progress at: https://github.com/vpstack/vpstack/issues "
        "(milestone: B2 reproducibility). "
        "For B1 (McAdams, signal-only) use: "
        "python -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run"
    )

    if args.output_format == "json":
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "BASELINE_NOT_IMPLEMENTED",
                "message": msg,
                "hint": "Use B1 baseline for now; B2 needs week-1+ neural recipe work.",
            },
        }))
    else:
        print(msg, file=sys.stderr)
    return 2  # non-zero exit so vp_run_baseline surfaces the error correctly


if __name__ == "__main__":
    sys.exit(main())
