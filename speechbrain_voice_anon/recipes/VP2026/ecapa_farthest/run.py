"""ecapa_farthest: stronger starter system using ECAPA-TDNN with farthest-point speaker selection.

Status: STUB. Not implemented in v0.1.0-dev. Implementation depends on B2 being functional first
(shares HuBERT content encoder and HiFi-GAN vocoder).

Contract is identical to baseline_B1/run.py — same CLI, same output JSON shape.
"""
from __future__ import annotations
import argparse, json, sys

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data_path", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output_format", choices=["json", "human"], default="human")
    args = p.parse_args()
    msg = "ecapa_farthest not yet implemented in v0.1.0-dev. Depends on B2 recipe."
    if args.output_format == "json":
        print(json.dumps({"ok": False, "error": {"code": "BASELINE_NOT_IMPLEMENTED", "message": msg, "hint": ""}}))
    else:
        print(msg, file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main())
