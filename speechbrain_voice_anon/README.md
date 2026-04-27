# speechbrain-voice-anon

SpeechBrain recipes for VoicePrivacy 2026:

- **B1 (McAdams)** — classical signal-processing baseline. Implemented in v0.1.0-dev.
- **B2 (neural)** — HuBERT + ECAPA + HiFi-GAN. Stub in v0.1.0-dev; week-1+ implementation.
- **ecapa_farthest** — stronger starter (ECAPA farthest-point speaker selection). Stub.
- **hifigan_anon** — HiFi-GAN anonymization vocoder. Stub.

**Important:** This package is a **re-implementation** of the canonical baselines from the published [VP2024 Eval Plan PDF](https://inria.hal.science/hal-04531444v1/), NOT a port of the [VP2024 GitHub code](https://github.com/Voice-Privacy-Challenge/Voice-Privacy-Challenge-2024) which is **GPLv3** (incompatible with vpstack's Apache 2.0 license). See [LICENSING.md](../LICENSING.md) at repo root.

## Install

```bash
pip install speechbrain-voice-anon
```

## Run B1 baseline

```bash
python -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run \
    --data_path /path/to/vp2026/data \
    --seed 42 \
    --output_format json
```

Outputs a JSON line with `eer`, `wer`, `linkability`, `config_hash`, `n_files_anonymized`, `output_dir`. Stderr shows progress every 30s.

## Pretrained model attribution (downloaded at runtime)

| Model | License | Citation |
|---|---|---|
| HuBERT (`facebook/hubert-base-ls960`) | Apache 2.0 | Hsu et al., arXiv:2106.07447 |
| ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) | Apache 2.0 | Desplanques et al., Interspeech 2020 |
| HiFi-GAN (jik876) | MIT (© 2020 Jungil Kong) | Kong, Kim, Bae, NeurIPS 2020 |

## Status

- v0.1.0-dev: B1 anonymization implemented; eval pipeline (EER/WER/linkability scoring) is a placeholder. Contract is locked.
- Next: B1 eval pipeline, then B2 neural recipe.
