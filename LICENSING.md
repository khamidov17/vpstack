# vpstack Licensing & Redistribution

Last audited: 2026-04-27

**Net verdict: DOWNLOAD_AT_RUNTIME_ONLY.** vpstack ships recipe code only. Pretrained model weights are fetched from primary sources (HuggingFace Hub, jik876/hifi-gan) at install or first-use. Eval data is never bundled — users fetch from challenge organizers themselves.

---

## Recommended vpstack license

**Apache 2.0** (or MIT). Avoid GPL to keep vpstack usable as a library by other projects.

---

## Pretrained model dependencies

| Model | Recommended checkpoint | License | Redistribute? | Commercial? |
|---|---|---|---|---|
| HuBERT | `facebook/hubert-base-ls960` | Apache 2.0 | YES (with NOTICE) | YES |
| ECAPA-TDNN | `speechbrain/spkrec-ecapa-voxceleb` | Apache 2.0 | YES (with NOTICE) | YES (caveat: VoxCeleb training data) |
| HiFi-GAN | jik876/hifi-gan + LibriTTS-fine-tuned anon vocoder | MIT | YES (preserve copyright) | YES |
| SpeechBrain | framework dep | Apache 2.0 | declare as PyPI dep | YES |

**Action:** Use `huggingface_hub.snapshot_download()` or SpeechBrain's `Pretrained.from_hparams()` for lazy weight download on first use. Host the fine-tuned anonymization HiFi-GAN under MIT on a HuggingFace Hub repo (preserve Jungil Kong 2020 copyright).

---

## Datasets — for reference and CI fixtures

| Dataset | License | Use in vpstack |
|---|---|---|
| LibriSpeech (OpenSLR-12) | CC-BY 4.0 | Safe for CI fixtures (small clips). Attribute. |
| LibriTTS (OpenSLR-60) | CC-BY 4.0 | Safe for CI fixtures. Attribute. |
| VoxCeleb 1/2 | CC-BY 4.0 metadata; audio = YouTube copyright | **Reference only.** Do not bundle clips. |
| IEMOCAP | Non-commercial, request-only (USC SAIL) | **Cannot redistribute.** Users register at https://sail.usc.edu/iemocap/ |
| VP2026 trial lists / eval splits | Challenge organizer terms; participant registration required | **Do not redistribute.** Users fetch via official download script. |
| VP2024 baseline code | **GPLv3** | **Do not import or vendor.** Viral license. Re-implement B1/B2 from the published eval plan PDF. |

---

## Five concrete blockers to resolve before PyPI publish

1. **Do not import or vendor any VP2024 GPLv3 source files.** Re-implement B1 (McAdams, signal processing only — trivial) and B2 (HuBERT + ECAPA + HiFi-GAN — re-implement using anthologies + papers) from the VoicePrivacy 2024 Eval Plan PDF (https://inria.hal.science/hal-04531444v1/). The eval plan itself is not GPL.
2. **Ship `THIRD_PARTY_LICENSES` (or `NOTICE`) file** in repo root listing:
   - Apache 2.0 attribution for HuBERT (Hsu et al., Meta AI), SpeechBrain (Ravanelli et al.), ECAPA (Desplanques et al.)
   - MIT copyright preservation for HiFi-GAN (Jungil Kong 2020)
   - CC-BY citation for LibriSpeech / LibriTTS
3. **Do not bundle VoxCeleb / IEMOCAP / VP2026 trial audio in CI fixtures.** Use small LibriSpeech-derived clips (CC-BY) for `tests/fixtures/`.
4. **Pick vpstack repo license** — Apache 2.0 recommended (matches HuBERT/ECAPA/SpeechBrain). MIT also acceptable. Avoid GPL.
5. **Re-verify VP2026 trial-data license terms** once organizers publish the 2026 data agreement. The 2026 challenge plan was released 2026-03-17 — recent enough that terms could shift. Re-check before any v0.1 release.

---

## Citation requirements (for `/vp-writeup` and recipe README)

When vpstack is used in published research, cite:

- **HuBERT:** Hsu et al., "HuBERT: Self-Supervised Speech Representation Learning by Masked Prediction of Hidden Units" — arXiv:2106.07447
- **SpeechBrain:** Ravanelli et al., "SpeechBrain: A General-Purpose Speech Toolkit" — arXiv:2106.04624
- **ECAPA-TDNN:** Desplanques et al., "ECAPA-TDNN: Emphasized Channel Attention, Propagation and Aggregation in TDNN Based Speaker Verification" — Interspeech 2020
- **HiFi-GAN:** Kong, Kim, Bae, "HiFi-GAN: Generative Adversarial Networks for Efficient and High Fidelity Speech Synthesis" — NeurIPS 2020
- **LibriSpeech:** Panayotov et al., ICASSP 2015
- **LibriTTS:** Zen et al., Interspeech 2019

vpstack itself does not generate these citations (per `/vp-writeup` constraint — no LLM citation generation). The recipe README lists them; researchers copy as appropriate.

---

## License-acceptance prompt design

On first invocation of `/vp-eval` or `/vp-baseline-compare`, print a one-time notice:

```
First-time vpstack eval setup.

This will download pretrained models from:
  - HuggingFace Hub: facebook/hubert-base-ls960 (Apache 2.0)
  - HuggingFace Hub: speechbrain/spkrec-ecapa-voxceleb (Apache 2.0)

vpstack does NOT redistribute VoicePrivacy challenge evaluation data.
You must obtain trial lists and eval splits from:
  https://www.voiceprivacychallenge.org/

If you use IEMOCAP for emotion evaluation, register separately at:
  https://sail.usc.edu/iemocap/

Continue? [Y/n]
```

Persist user's choice in `~/.vpstack/config.json` so it's only shown once.

---

## Sources

- HuBERT: https://huggingface.co/facebook/hubert-base-ls960
- SpeechBrain ECAPA: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb
- jik876/hifi-gan: https://github.com/jik876/hifi-gan
- jik876 LICENSE (MIT): https://github.com/jik876/hifi-gan/blob/master/LICENSE
- Voice-Privacy-Challenge-2024 (GPLv3): https://github.com/Voice-Privacy-Challenge/Voice-Privacy-Challenge-2024
- SpeechBrain LICENSE: https://github.com/speechbrain/speechbrain/blob/develop/LICENSE
- VoxCeleb1 terms: https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox1.html
- VoxCeleb2 terms: https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox2.html
- LibriSpeech (CC-BY 4.0): https://www.openslr.org/12/
- LibriTTS (CC-BY 4.0): https://www.openslr.org/60/
- IEMOCAP (request-only): https://sail.usc.edu/iemocap/
- VoicePrivacy challenge: https://www.voiceprivacychallenge.org/
- VP2024 eval plan PDF: https://inria.hal.science/hal-04531444v1/
