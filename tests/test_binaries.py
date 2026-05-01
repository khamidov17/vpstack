import os
import subprocess
import pytest
import numpy as np
import soundfile as sf
import json
from pathlib import Path

def test_b1_smoke(tmp_path):
    # Create synthetic audio
    sr = 16000
    duration = 0.5
    t = np.linspace(0, duration, int(sr * duration))
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    in_dir = tmp_path / "in"
    in_dir.mkdir()
    sf.write(in_dir / "test.wav", audio, sr)

    out_dir = tmp_path / "out"

    bin_path = Path(__file__).parent.parent / "bin" / "vpstack-b1"

    res = subprocess.run([
        str(bin_path.absolute()),
        "--data_path", str(in_dir),
        "--output_dir", str(out_dir),
        "--output_format", "json"
    ], capture_output=True, text=True)

    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["n_files"] == 1
    assert (out_dir / "test.wav").exists()

def test_score_help():
    bin_path = Path(__file__).parent.parent / "bin" / "vpstack-score"
    res = subprocess.run([str(bin_path.absolute()), "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "usage" in res.stdout.lower() or "wrap an external ASV attacker" in res.stdout

def test_eval_help():
    bin_path = Path(__file__).parent.parent / "bin" / "vpstack-eval"
    res = subprocess.run([str(bin_path.absolute()), "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "usage" in res.stdout.lower() or "orchestrator that runs VP2026" in res.stdout
