# VoicePrivacy 2026 — Domain Reference

This file is the authoritative domain knowledge source for vpstack skills. When a skill tells Claude to "apply inline domain knowledge" or "see docs/domain.md", this is what Claude reads.

---

## Metrics

### EER (Equal Error Rate) — Privacy metric
- **Direction: HIGHER = more private**
- **50% = random attacker = perfect anonymization (the goal)**
- **Original speech (no anonymization): ~3-5% EER** (ASV works perfectly, zero privacy)
- 0% EER = attacker is perfect, you have no privacy whatsoever
- Report EER under the **semi-informed condition** (official VP2026 ranking)
- Do NOT report only ignorant condition — reviewers will ask for semi-informed

### WER (Word Error Rate) — Utility metric
- **Direction: LOWER = more useful**
- 0% = perfect transcription
- Typical target: within 0.5pp of the B2 baseline on your dataset

### Linkability (ZEBRA Cllr) — Secondary privacy metric
- **Direction: LOWER = harder to link speaker identities**
- Report alongside EER, not instead of it

### The tradeoff
More aggressive anonymization raises EER (good) but also raises WER (bad). Every ablation must report both.

---

## Attacker Conditions

| Condition | Time | What it means | Use when |
|---|---|---|---|
| `ignorant` | ~5 min | Attacker doesn't know anonymization was applied | Fast sanity check only |
| `lazy_informed` | ~10 min | Attacker knows, uses pretrained ECAPA + anonymized enrollment | Quick diagnostic |
| `semi_informed` | 4-12h GPU | Attacker retrains ECAPA on anonymized train-clean-360 | **Official VP2026 ranking — always report this** |

**Always report semi-informed** for any result you will cite or submit.

---

## Canonical Baselines

Do NOT use hardcoded numbers from older challenge years. Run the actual baselines on your VP2026 data.

- **B1 (McAdams):** Signal-processing only. No GPU. Fast (~5min CPU). Weak anonymization. The floor to beat.
  - Run: `python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run --data_path PATH --output_format json --seed 42`
- **B2 (HuBERT + ECAPA-TDNN + HiFi-GAN):** Neural. Requires GPU. Strong anonymization. The real target.
  - NOT YET IMPLEMENTED in vpstack v0.2. Recipe exits 2 with BASELINE_NOT_IMPLEMENTED.

Log your B1 run as `exp_id="b1-reference"` so it anchors your experiment comparisons.

---

## Components

### HuBERT (content encoder)
**What it does:** Extracts phonetic content from speech, removing (ideally) speaker identity.
- Layer 1-4: speaker-leaning — **avoid as content encoder**
- Layer 6: standard B2 default — good content/speaker balance
- Layer 7-9: phonetic content peak — strongest disentanglement per Pasad et al. (ASRU 2021)
- Layer 12: content-leaning (not speaker-leaning, despite older claims)
- **License:** Apache 2.0 (`facebook/hubert-base-ls960`)
- **Known issue:** Layer 6 causes speaker leakage on utterances < 1s. Switch to layer 9 for short utterance corpora.
- **Known issue:** Always resample to 16kHz before encoding — do not rely on pipeline auto-resample.

### ContentVec (disentanglement-tuned HuBERT)
- Explicitly trained to suppress speaker from content representation
- Superior to vanilla HuBERT for anonymization when available
- Use layer 9
- **License:** MIT (`AIMiranker/contentvec`)

### WavLM (2026 SOTA self-supervised)
- Best-performing on SUPERB benchmark. Many VP2026 teams will use WavLM-Large.
- Use layers 6-9 for content (1-4 still speaker-leaning)
- **Caveat:** WavLM-Large is 300M params — needs GPU with ≥8GB VRAM for inference on 10s utterances
- **License:** MIT (`microsoft/wavlm-large`)

### ECAPA-TDNN (speaker encoder)
**What it does:** Produces speaker embeddings. Used to pick a target voice for anonymization.
- Farthest-point strategy: pick target speaker most distant from source in embedding space → stronger anonymization
- **License:** Apache 2.0 (`speechbrain/spkrec-ecapa-voxceleb`)
- **Known issue:** ECAPA 192ch + HiFi-GAN v1 universal produces phase artifacts above 4kHz. Use LibriTTS-finetuned HiFi-GAN.
- **Known issue:** Farthest-point selection degrades on non-English corpora — VoxCeleb embedding space doesn't transfer.

### HiFi-GAN (vocoder)
**What it does:** Synthesizes anonymized audio from content features + target speaker embedding.
- Use LibriTTS-finetuned weights for VP2026, not v1 universal (v1 was trained at 22.05kHz; VP2026 is 16kHz)
- **License:** MIT (`jik876/hifi-gan`)
- **Known issue:** Sensitive to mel-spectrogram normalization — verify mel stats match training.

### McAdams coefficient (B1)
**What it does:** Modifies LPC pole angles by scalar α (0.8 = standard B1).
- Higher α → more aggressive shift → more privacy, more distortion
- α < 0.6 or α > 1.4 → audible artifacts, significant WER regression
- **Known issue:** Frame length must be 20ms (not 25ms) for canonical VP2026 B1 numbers.
- α=0.75 sometimes outperforms α=0.8 on female speakers.

---

## Reproducibility Checklist

An experiment is reproducible if ALL of the following are true:

1. **Seed pinned** — single integer in config (e.g., `seed: 42`), not auto-derived
2. **Splits explicit** — data paths are concrete, not `auto-detect`
3. **Checkpoint hashes** — every pretrained model has SHA256 in `checkpoints.lock` alongside config
4. **No placeholder hparams** — no `TODO`, `FILL_ME`, `null`, or empty strings in hparams
5. **Determinism** — either `torch_deterministic: true` OR `n_seeds >= 3` recorded

---

## VP2026 Submission Format

A valid submission directory must contain:
- `eer.json` with at least `{"overall": float, "female": float, "male": float}`
- `wer.json` with at least `{"overall": float}`
- `anonymized/` directory with anonymized WAV files
- No audio files from the original (non-anonymized) dataset

---

## Common Mistakes That Waste GPU Time

1. Reporting only `ignorant` EER — not the ranking metric
2. HuBERT layers 1-4 as content encoder — speaker-leaning, leaks identity
3. HiFi-GAN v1 universal at wrong sample rate — VP2026 is 16kHz, v1 was 22.05kHz
4. McAdams frame_length_ms=25 instead of 20 — gives wrong canonical B1 numbers
5. Missing `seed` key in config — different results every run
6. Running eval only on `ignorant` condition and calling it done

---

## Bash Commands Reference

```bash
# Run B1 anonymization + eval
python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run \
  --data_path PATH --output_format json --seed 42

# Run attacker
python3 -m speechbrain_voice_anon.recipes.VP2026.attacker.run \
  --anonymized_path PATH \
  --enrollment_path PATH \
  --trial_list PATH \
  --attacker_condition semi_informed \
  --output_format json --seed 42

# Get project slug (matches experiment storage path)
~/.claude/skills/vpstack/bin/vpstack-slug

# Log an experiment (use Write tool, not bash, for atomic safety)
# Write to: ~/.vpstack/projects/{SLUG}/experiments/{EXP_ID}/summary.json
```

---

## Exit Codes for Recipe Scripts

| Code | Meaning |
|---|---|
| 0 | Success — parse JSON from stdout |
| 1 | Real error — read stderr. Common: DATA_MISSING, GPU_OOM, soundfile not installed |
| 2 | BASELINE_NOT_IMPLEMENTED — recipe exists but eval pipeline not implemented. JSON on stdout has the error. Anonymization may have run. |

If exit 1 and stderr contains:
- `soundfile` → `pip install soundfile`
- `scipy` → `pip install scipy`
- `CUDA out of memory` → reduce batch size or use smaller GPU
- `No .wav files` → wrong data_path
- `401` or `403` → `huggingface-cli login`
