"""speechbrain-voice-anon: SpeechBrain recipes for VoicePrivacy 2026.

This package re-implements the canonical baselines (B1 McAdams, B2 neural) and
provides stronger starter systems (ECAPA-farthest, HiFi-GAN anonymizer). It is
*not* a fork of the VP2024 GitHub (which is GPLv3) — see LICENSING.md.

Pretrained model weights are fetched from primary sources (HuggingFace Hub,
jik876/hifi-gan reference) at runtime. None are redistributed.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("speechbrain-voice-anon")
except PackageNotFoundError:
    __version__ = "0.1.0.dev0"
