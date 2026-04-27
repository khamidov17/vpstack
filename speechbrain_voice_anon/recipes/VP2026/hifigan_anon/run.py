"""hifigan_anon: HiFi-GAN as the anonymization vocoder, fine-tuned on LibriTTS.

Status: STUB. Not implemented in v0.1.0-dev. Use the jik876 reference HiFi-GAN
(MIT licensed, copyright 2020 Jungil Kong) as the starting point. Fine-tune on
LibriTTS (CC-BY 4.0) to specialize for anonymization output. Host the fine-tuned
checkpoint on a HuggingFace Hub repo under MIT, preserving Kong's copyright.

Contract is identical to baseline_B1/run.py.
"""
from __future__ import annotations
import argparse, json, sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data_path", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output_format", choices=["json", "human"], default="human")
    args = p.parse_args()
    msg = "hifigan_anon not yet implemented in v0.1.0-dev."
    if args.output_format == "json":
        print(json.dumps({"ok": False, "error": {"code": "BASELINE_NOT_IMPLEMENTED", "message": msg, "hint": ""}}))
    else:
        print(msg, file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
