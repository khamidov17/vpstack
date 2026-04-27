"""Smoke tests for the B1 McAdams transformation.

These tests verify the McAdams function works on synthetic signals — they do NOT
constitute the CG1 reproducibility gate (that requires real VP2026 data + GPU).

CG1 (full B1 reproducibility on dev set) is in a separate test module guarded by
@pytest.mark.gpu and run only in CI with VP2026 data fixtures.
"""

import numpy as np
import pytest


def test_mcadams_preserves_length():
    from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import mcadams_anonymize

    sr = 16000
    duration_s = 1.0
    n = int(sr * duration_s)
    # Synthetic vowel — sum of 3 sine waves at formant-like frequencies
    t = np.arange(n) / sr
    signal = (np.sin(2 * np.pi * 500 * t) + 0.5 * np.sin(2 * np.pi * 1500 * t)
              + 0.3 * np.sin(2 * np.pi * 2500 * t)).astype(np.float32) * 0.3

    out = mcadams_anonymize(signal, sr, alpha=0.8)
    assert out.shape == signal.shape
    assert out.dtype == np.float32


def test_mcadams_alpha_validation():
    from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import mcadams_anonymize

    sr = 16000
    signal = np.random.randn(sr).astype(np.float32) * 0.1

    with pytest.raises(ValueError, match="alpha"):
        mcadams_anonymize(signal, sr, alpha=0.0)
    with pytest.raises(ValueError, match="alpha"):
        mcadams_anonymize(signal, sr, alpha=1.5)


def test_mcadams_rejects_2d_input():
    from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import mcadams_anonymize

    sr = 16000
    stereo = np.random.randn(sr, 2).astype(np.float32) * 0.1
    with pytest.raises(ValueError, match="1D"):
        mcadams_anonymize(stereo, sr)


def test_mcadams_alpha_1_close_to_identity():
    """alpha=1 keeps pole angles unchanged → output should be very close to input.

    Tightened from 0.5 to 0.95 per QA review: 0.5 was so loose that a transformation
    destroying half the signal would still pass. With alpha=1.0, overlap-add
    reconstruction routinely hits >0.99 correlation; setting the gate at 0.95 leaves
    headroom for legitimate frame-edge artifacts but catches real regressions.
    """
    from speechbrain_voice_anon.recipes.VP2026.baseline_B1.mcadams import mcadams_anonymize

    sr = 16000
    np.random.seed(42)
    signal = np.random.randn(sr).astype(np.float32) * 0.1

    out = mcadams_anonymize(signal, sr, alpha=1.0)
    correlation = np.corrcoef(signal, out)[0, 1]
    assert correlation > 0.95, (
        f"alpha=1 correlation too low: {correlation:.4f}. "
        "Expected >0.95 — overlap-add reconstruction with no pole transformation "
        "should be very close to input."
    )


@pytest.mark.gpu
@pytest.mark.skip(reason="CG1 reproducibility gate — requires VP2026 data + GPU; run in CI only")
def test_b1_reproducibility_within_tolerance():
    """CG1 — placeholder. Real implementation:
       1. Run baseline_B1.run on canonical VP2026 dev set
       2. Compare EER against published number ±0.5%
       3. See TEST-PLAN.md for tolerance notes (may need widening due to CUDA non-determinism)
    """
    pass
