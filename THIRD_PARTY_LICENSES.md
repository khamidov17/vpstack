# Third-Party Licenses

vpstack depends on or fetches the following third-party software and pretrained models. Each is governed by its own license, preserved here per attribution requirements.

See [LICENSING.md](LICENSING.md) for the full audit and redistribution rationale.

---

## Pretrained Models (downloaded at runtime — not redistributed)

### HuBERT (`facebook/hubert-base-ls960`)
- **License:** Apache License 2.0
- **Citation:** Hsu et al., "HuBERT: Self-Supervised Speech Representation Learning by Masked Prediction of Hidden Units", arXiv:2106.07447
- **Source:** https://huggingface.co/facebook/hubert-base-ls960

### ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`)
- **License:** Apache License 2.0
- **Citation:** Desplanques et al., "ECAPA-TDNN: Emphasized Channel Attention, Propagation and Aggregation in TDNN Based Speaker Verification", Interspeech 2020
- **Source:** https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb

### HiFi-GAN (jik876 reference)
- **License:** MIT License
- **Copyright:** Copyright (c) 2020 Jungil Kong
- **Citation:** Kong, Kim, Bae, "HiFi-GAN: Generative Adversarial Networks for Efficient and High Fidelity Speech Synthesis", NeurIPS 2020
- **Source:** https://github.com/jik876/hifi-gan

---

## Framework Dependencies

### SpeechBrain
- **License:** Apache License 2.0
- **Citation:** Ravanelli et al., "SpeechBrain: A General-Purpose Speech Toolkit", arXiv:2106.04624
- **Source:** https://github.com/speechbrain/speechbrain

### anthropic-mcp
- **License:** MIT License
- **Source:** https://github.com/anthropics/python-mcp-sdk (or current Anthropic MCP SDK)

---

## Dataset Attribution (used in fixtures)

### LibriSpeech
- **License:** CC-BY 4.0
- **Citation:** Panayotov et al., ICASSP 2015
- **Source:** https://www.openslr.org/12/

### LibriTTS
- **License:** CC-BY 4.0
- **Citation:** Zen et al., Interspeech 2019
- **Source:** https://www.openslr.org/60/

---

## NOT Used or Distributed

- **VP2024 baseline GitHub code (GPLv3):** Explicitly NOT vendored or imported. vpstack re-implements baselines from the published Eval Plan PDF. See LICENSING.md for rationale.
- **VoxCeleb 1/2 audio:** Reference only. Not bundled.
- **IEMOCAP:** Request-only. Users register at https://sail.usc.edu/iemocap/.
- **VP2026 trial lists / eval splits:** Distributed by challenge organizers under registration. Users obtain via official process at https://www.voiceprivacychallenge.org/.
