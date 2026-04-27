"""B1 recipe entrypoint: anonymize a directory of WAV files via McAdams + run VP2026 eval.

Invoked by vp_run_baseline (the MCP tool):
    python -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run \
        --data_path /path/to/vp2026/data \
        --seed 42 \
        --output_format json

Output: a single JSON line on stdout containing:
    {"eer": float, "wer": float, "linkability": float, "config_hash": str}

Stderr: progress updates ("frame X/Y", "ETA Z").
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import mcadams_anonymize


logger = logging.getLogger("baseline_B1")


def _config_hash(args: argparse.Namespace) -> str:
    """Deterministic hash of the config — used for /vp-repro-check to verify same-config-same-output."""
    payload = json.dumps(
        {
            "baseline": "B1",
            "alpha": args.alpha,
            "lpc_order": args.lpc_order,
            "seed": args.seed,
            "frame_length_ms": args.frame_length_ms,
            "hop_length_ms": args.hop_length_ms,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _anonymize_directory(input_dir: Path, output_dir: Path, args: argparse.Namespace) -> int:
    """Run McAdams on every .wav in input_dir, write to output_dir. Returns count anonymized."""
    try:
        import soundfile as sf
    except ImportError:
        print("baseline_B1: pip install soundfile", file=sys.stderr)
        sys.exit(1)

    wavs = sorted(input_dir.rglob("*.wav"))
    if not wavs:
        print(f"baseline_B1: no .wav files under {input_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)  # noqa: F841 — for stochastic variants

    t0 = time.time()
    last_progress = t0
    for i, wav_path in enumerate(wavs):
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # downmix to mono
        anon = mcadams_anonymize(
            audio, sr,
            alpha=args.alpha,
            lpc_order=args.lpc_order,
            frame_length_ms=args.frame_length_ms,
            hop_length_ms=args.hop_length_ms,
        )
        out_path = output_dir / wav_path.relative_to(input_dir)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), anon, sr)

        # Progress every 30s
        now = time.time()
        if now - last_progress > 30 or i == len(wavs) - 1:
            elapsed = now - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(wavs) - i - 1) / rate if rate > 0 else 0
            print(
                f"baseline_B1: anonymized {i+1}/{len(wavs)} files, ETA {eta:.0f}s",
                file=sys.stderr,
                flush=True,
            )
            last_progress = now

    return len(wavs)


def _run_eval(anonymized_dir: Path, eval_set_dir: Path, args: argparse.Namespace) -> dict:
    """Run the VP2026 eval suite against anonymized audio.

    PLACEHOLDER: in v0.1.0-dev this returns sentinel numbers. The real eval
    pipeline (EER via ASV, WER via ASR, linkability) is implemented in a follow-up.
    The contract here is: returns a dict with keys eer, wer, linkability — all floats.
    """
    print("baseline_B1: eval pipeline not yet implemented in v0.1.0-dev — returning sentinel.",
          file=sys.stderr)
    # TODO(v0.1): implement EER via SpeechBrain ECAPA, WER via Whisper or wav2vec2,
    # linkability via MAP attack from the VP2024 eval plan PDF.
    return {
        "eer": float("nan"),
        "wer": float("nan"),
        "linkability": float("nan"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="VP2026 B1 (McAdams) baseline runner.")
    parser.add_argument("--data_path", required=True, help="Path to VP2026 data directory.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--alpha", type=float, default=0.8, help="McAdams coefficient.")
    parser.add_argument("--lpc_order", type=int, default=20)
    parser.add_argument("--frame_length_ms", type=int, default=20)  # Patino canonical (was 25)
    parser.add_argument("--hop_length_ms", type=int, default=10)
    parser.add_argument("--output_dir", default=None)
    parser.add_argument("--output_format", choices=["json", "human"], default="human")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    data_path = Path(args.data_path).expanduser()
    if not data_path.exists():
        print(f"baseline_B1: data path missing: {data_path}", file=sys.stderr)
        return 1

    # Default output: <data_path>/anon_b1
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else data_path / "anon_b1"

    n = _anonymize_directory(data_path, output_dir, args)
    print(f"baseline_B1: anonymized {n} files to {output_dir}", file=sys.stderr)

    # Eval is a placeholder in v0.1.0-dev — see _run_eval docstring.
    eval_results = _run_eval(output_dir, data_path, args)

    result = {
        "eer": eval_results["eer"],
        "wer": eval_results["wer"],
        "linkability": eval_results["linkability"],
        "config_hash": _config_hash(args),
        "n_files_anonymized": n,
        "output_dir": str(output_dir),
    }

    if args.output_format == "json":
        # Single JSON line on stdout — vp_run_baseline parses this.
        print(json.dumps(result))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
