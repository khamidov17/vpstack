"""B1: McAdams coefficient transformation — classical signal-processing voice anonymization.

The B1 baseline. No neural model. Modifies LPC pole angles by a McAdams coefficient (alpha)
to shift formants. Preserves linguistic content (low WER cost) at the price of weak speaker
anonymization.

Re-implementation per the VoicePrivacy 2024 Eval Plan PDF
(https://inria.hal.science/hal-04531444v1/). NOT a fork of VP2024 GPLv3 code.

Reference:
    Patino et al., "Speaker Anonymisation Using the McAdams Coefficient", VP2020 baseline B1.
"""

from __future__ import annotations

import numpy as np
import scipy.signal


def mcadams_anonymize(
    waveform: np.ndarray,
    sample_rate: int,
    alpha: float = 0.8,
    lpc_order: int = 20,
    frame_length_ms: int = 25,
    hop_length_ms: int = 10,
    eps: float = 1e-8,
) -> np.ndarray:
    """Apply McAdams transformation to anonymize a single waveform.

    Args:
        waveform: 1D float32 array, [-1, 1].
        sample_rate: typically 16000 Hz for VP2026.
        alpha: McAdams coefficient. 0.8 = standard B1 setting (mild anonymization).
            Lower (e.g., 0.5) = stronger anonymization, more artifacts.
        lpc_order: LPC analysis order. 20 is standard for 16kHz speech.
        frame_length_ms: frame length for analysis.
        hop_length_ms: hop length between frames.
        eps: numerical stability for log/divide.

    Returns:
        Anonymized waveform, same shape as input.

    Pipeline:
        1. Frame the signal (Hann-windowed).
        2. Per frame: LPC analysis -> get poles.
        3. Modify pole angles: angle' = angle ** alpha (preserves magnitude < 1).
        4. Reconstruct LPC filter with modified poles.
        5. Inverse-filter to get residual, re-filter with modified LPC -> anonymized frame.
        6. Overlap-add frames.
    """
    if waveform.ndim != 1:
        raise ValueError(f"expected 1D waveform, got shape {waveform.shape}")
    if not 0.0 < alpha <= 1.0:
        raise ValueError(f"alpha must be in (0, 1], got {alpha}")

    frame_length = int(sample_rate * frame_length_ms / 1000)
    hop_length = int(sample_rate * hop_length_ms / 1000)
    window = np.hanning(frame_length).astype(np.float32)

    # Pad to a multiple of hop_length
    n_frames = max(1, 1 + (len(waveform) - frame_length) // hop_length)
    padded_len = (n_frames - 1) * hop_length + frame_length
    if padded_len < len(waveform):
        n_frames += 1
        padded_len = (n_frames - 1) * hop_length + frame_length
    padded = np.zeros(padded_len, dtype=np.float32)
    padded[: len(waveform)] = waveform

    output = np.zeros(padded_len, dtype=np.float32)
    norm = np.zeros(padded_len, dtype=np.float32)

    for i in range(n_frames):
        start = i * hop_length
        end = start + frame_length
        frame = padded[start:end] * window

        # LPC via Levinson-Durbin (autocorrelation method).
        # F2 fix from code review: short trailing frames after silence trimming can
        # raise ValueError from broadcasting in the recursion, not just LinAlgError.
        # A single bad utterance must NOT crash the whole batch.
        try:
            lpc_coeffs = _lpc(frame, lpc_order)
        except (np.linalg.LinAlgError, ValueError):
            # Singular or too-short frame — pass through unchanged
            output[start:end] += frame
            norm[start:end] += window
            continue

        # Roots of LPC polynomial = poles
        roots = np.roots(lpc_coeffs)
        # Keep only stable poles (inside unit circle)
        roots = roots[np.abs(roots) < 1.0 - eps]

        # McAdams transformation: angle' = angle ** alpha, magnitude unchanged
        magnitudes = np.abs(roots)
        angles = np.angle(roots)
        # Apply only to non-real-axis poles (avoid sign flips on real poles)
        complex_mask = np.abs(angles) > eps
        new_angles = angles.copy()
        new_angles[complex_mask] = np.sign(angles[complex_mask]) * (np.abs(angles[complex_mask]) ** alpha)
        new_roots = magnitudes * np.exp(1j * new_angles)

        # Reconstruct LPC polynomial from modified poles
        new_lpc = np.real(np.poly(new_roots)).astype(np.float32)
        if len(new_lpc) > len(lpc_coeffs):
            new_lpc = new_lpc[: len(lpc_coeffs)]
        elif len(new_lpc) < len(lpc_coeffs):
            new_lpc = np.pad(new_lpc, (0, len(lpc_coeffs) - len(new_lpc)))

        # Inverse-filter (analysis) then forward-filter (synthesis with modified LPC)
        residual = scipy.signal.lfilter(lpc_coeffs, [1.0], frame)
        synthesized = scipy.signal.lfilter([1.0], new_lpc, residual)

        output[start:end] += synthesized.astype(np.float32) * window
        norm[start:end] += window

    # Normalize overlap-add
    nonzero = norm > eps
    output[nonzero] /= norm[nonzero]
    return output[: len(waveform)]


def _lpc(frame: np.ndarray, order: int) -> np.ndarray:
    """Compute LPC coefficients via Levinson-Durbin recursion.

    Returns coefficients [1, -a1, -a2, ..., -a_order] suitable for scipy.signal.lfilter.

    Raises:
        np.linalg.LinAlgError: zero-energy frame (silence) or too-short input.
            Callers should catch and pass the frame through unchanged.
    """
    # F2 fix: explicit length guard. Short trailing frames after silence trimming
    # would otherwise produce broadcasting errors deeper in the recursion.
    if len(frame) < order + 1:
        raise np.linalg.LinAlgError(
            f"frame too short for LPC order {order}: got {len(frame)} samples, need {order + 1}"
        )
    # Autocorrelation
    r = np.correlate(frame, frame, mode="full")[len(frame) - 1 : len(frame) + order]
    if r[0] < 1e-10:
        raise np.linalg.LinAlgError("zero-energy frame")
    # Levinson-Durbin
    a = np.zeros(order + 1, dtype=np.float64)
    a[0] = 1.0
    e = r[0]
    for i in range(order):
        k = -np.sum(a[: i + 1] * r[i + 1 : 0 : -1] if i > 0 else [r[1]]) / e
        a_new = a.copy()
        a_new[1 : i + 2] = a[1 : i + 2] + k * a[i :: -1][: i + 1]
        a = a_new
        e *= 1 - k * k
        if e < 1e-12:
            break
    return a.astype(np.float32)
