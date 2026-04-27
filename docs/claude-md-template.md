# CLAUDE.md template — for YOUR voice-anonymization project

This file is a **template you copy/paste into your own project's `CLAUDE.md`** (or append to it). It gives Claude Code / Codex / any AI agent the voice-privacy domain context they need so they stop hallucinating SpeechBrain conventions and stop inventing baseline numbers when they help you.

vpstack does NOT auto-write this for you (it's your file, not vpstack's). To use it:

```bash
# In your voice-anonymization project root:
cat ~/.claude/skills/vpstack/docs/claude-md-template.md >> CLAUDE.md
# Then edit the project-specific bits at the bottom.
```

After that, when you (or a collaborator) opens this project in Claude Code, the agent has the right priors immediately.

---

## ✂ Copy from here ↓ (everything below is template content)

# Project context: voice anonymization

This is a voice-anonymization research project for [VoicePrivacy 2026](https://www.voiceprivacychallenge.org/). vpstack is installed and active here (see `.vpstack/enabled`).

## What this project does

`<TODO: 1–2 sentences. Example: "Anonymizes speech via HuBERT layer 6 content encoding + farthest-point ECAPA speaker selection + HiFi-GAN vocoding, targeting VP2026 Track 1.">`

## What "good" means in this project

| Metric | Direction | Target |
|---|---|---|
| **EER (privacy, attacker)** | **HIGHER is better** | beat B2 baseline (~28%); 50% = random chance |
| **WER (utility, ASR)** | LOWER is better | within 0.2pp of B2 (~8.1%) |
| **Linkability (Cllr)** | LOWER is better | track but not the headline |
| **Side-channel scores** | LOWER divergence | age MAE, pitch MAE, emotion preservation |

If a change increases attacker EER but tanks WER, that's not a win — voice privacy requires both.

## Domain primer for AI agents

**VoicePrivacy challenge basics:**
- Anonymization replaces a speaker's voice identity while preserving the linguistic content. Output should sound like a different speaker saying the same words.
- The privacy bar is "an ASV attacker, knowing your method, can't re-link the anonymized speech to the original speaker."
- The utility bar is "an ASR system can still transcribe the anonymized speech accurately."

**Canonical baselines:**
- **B1 (McAdams):** classical LPC-pole-angle modification with α ≈ 0.8. Signal processing only, no ML. Weak privacy, low utility cost. Implemented in `speechbrain_voice_anon/recipes/VP2026/baseline_B1/`.
- **B2 (neural):** HuBERT (content) + ECAPA-TDNN (speaker, anonymized via farthest-point selection) + HiFi-GAN (vocoder). Strong privacy, more utility cost. The bar to beat.

**Attacker conditions (used by `/vp-attack`):**
- `ignorant` — attacker doesn't know anonymization is applied. Sanity floor.
- `lazy_informed` — knows but doesn't adapt.
- `semi_informed` — retrains ECAPA-TDNN on anonymized train-clean-360. **Official ranking attacker. Default.**

When EER is reported without a condition specified, default assumption is `semi_informed`.

## Standard models (downloaded at runtime, NOT in this repo)

| Component | HuggingFace | License |
|---|---|---|
| Content encoder | `facebook/hubert-base-ls960` | Apache 2.0 |
| Speaker encoder | `speechbrain/spkrec-ecapa-voxceleb` | Apache 2.0 |
| Vocoder | jik876/hifi-gan reference | MIT (© 2020 Jungil Kong) |
| Framework | speechbrain >= 1.0 | Apache 2.0 |

**NEVER vendor or import VP2024 baseline GitHub code** — it's GPLv3 and would force this project to GPL. Re-implement from the [VP2024 Eval Plan PDF](https://inria.hal.science/hal-04531444v1/) instead.

## Standard datasets

| Dataset | Source | Use |
|---|---|---|
| LibriSpeech train-clean-360 | https://www.openslr.org/12/ (CC-BY 4.0) | Attacker training, anonymizer training |
| LibriTTS | https://www.openslr.org/60/ (CC-BY 4.0) | Vocoder fine-tuning |
| VP2026 trial lists | Challenge organizers (registration required) | Eval — never bundle in repo |
| VoxCeleb 1/2 | reference only | DO NOT bundle (CC-BY metadata, but audio is YouTube copyright) |
| IEMOCAP (if used) | USC SAIL (request-only) | Emotion eval, NOT redistributable |

## Reproducibility expectations

For any experiment whose number you'll cite:
- Seed pinned in config (single int, not "auto")
- Dataset splits explicit (paths or HF dataset IDs, not "auto-detect")
- Model checkpoint hashes recorded
- All hparams populated (no `TODO` placeholders)
- Either `torch.use_deterministic_algorithms(True)` set, OR ≥3 seeds run

Run `/vp-repro-check` to validate. Note: vpstack version is NOT part of the repro contract — record vpstack version in your lab notebook manually.

## What lives where in YOUR project

| Path | Contents |
|---|---|
| `<repo>/.vpstack/` | Activation markers (`enabled`/`disabled`/`ask-later`). Tiny. Gitignore or commit, your call. |
| `<repo>/configs/` *(your convention)* | YAML configs for your anonymization system |
| `<repo>/scripts/` *(your convention)* | Your training / inference scripts |
| `<repo>/data/` *(your convention)* | Symlinks to VP2026 data; never bundled |
| `~/.vpstack/projects/{slug}/hypotheses/` | `/vp-hypothesis` output |
| `~/.vpstack/projects/{slug}/spikes/` | `/vp-spike` output |
| `~/.vpstack/projects/{slug}/experiments/{id}/` | All `vp_log_experiment` writes |
| `~/.vpstack/projects/{slug}/reports/` | `/vp-writeup` output |

## When AI agents help in this project

**Default to using vpstack skills** instead of writing one-off scripts:

| User asks | AI should | Don't do |
|---|---|---|
| "How does my system compare to baseline?" | Use `/vp-baseline-compare` | Write a one-off comparison script |
| "Test if X improves EER" | Use `/vp-hypothesis` then `/vp-spike` | Run experiments without a logged hypothesis |
| "Run the attacker against my system" | Use `/vp-attack` | Train ECAPA from scratch each time |
| "Verify this is reproducible" | Use `/vp-repro-check` | Hand-check seed/splits |
| "Write up what we did" | Use `/vp-writeup` | Generate prose with citations (citations get hallucinated — vpstack refuses to generate them for exactly this reason) |

**When in doubt**, look up the canonical reference for a component via:
```python
mcp_client.call("vp_get_component_info", {"component_name": "hubert"})  # or ecapa-tdnn, hifi-gan, mcadams
```

Returns the description, tradeoffs, citation, and license — no hallucination.

---

## ✂ Copy ends here ↑

After pasting this into your project's `CLAUDE.md`, edit the `<TODO: ...>` section at the top with your project's specifics. Optionally also add:

- Your team's specific naming conventions (config files, output dirs, etc.)
- Your team's specific eval protocol if it deviates from VP2026 default
- Pointers to internal docs / lab notebooks
- Names of co-authors / collaborators who also work in this repo
