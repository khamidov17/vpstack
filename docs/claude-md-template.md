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

| Metric | Direction | Target | Notes |
|---|---|---|---|
| **EER (privacy, attacker)** | **HIGHER is better** | beat B2 (~12.3%); 50% = random | semi_informed condition = official ranking |
| **WER (utility, ASR)** | LOWER is better | within 0.2pp of B2 (~8.1%) | Whisper or wav2vec2 eval |
| **Linkability (Cllr)** | LOWER is better | track alongside EER | ZEBRA/MAP metric |
| **Side-channel scores** | LOWER divergence | age MAE, pitch MAE, emotion | Secondary metrics |

If EER improves but WER tanks, that's not a win. Voice privacy requires both.

## Domain primer for AI agents

**Critical facts (these do NOT change by challenge year):**
- EER direction: **HIGHER = more private**. 50% = random attacker = perfect anonymization goal.
- **Semi-informed attacker = the official VP2026 ranking metric.** Always report this one.
- Ignorant condition gives high EER (~50%+) but is NOT the ranking metric — don't confuse them.
- Canonical alpha for B1: **0.8** (20ms frame, not 25ms — corrected 2026-04-28)

**Challenge-specific numbers you must NOT hardcode from previous years:**
- B1 EER, B2 EER, WER: these are VP2026-specific. Different data, different trial lists.
- Run `/vp-baseline-compare` on your VP2026 data to get the correct reference values.
- Log them with `vp_log_experiment(exp_id='b1-reference', ...)` so they anchor the leaderboard.
- The VP2026 Eval Plan PDF from the challenge organizers is the authoritative source.

**The privacy/utility tradeoff:** Aggressive anonymization increases EER but also increases WER. Every ablation experiment must report BOTH metrics.

**Attacker conditions (used by `/vp-attack`):**
- `ignorant` (~5 min) — attacker doesn't know anonymization applied. Sanity floor only.
- `lazy_informed` (~10 min) — knows but doesn't adapt. Intermediate signal.
- `semi_informed` (~4-12h GPU) — retrains ECAPA on anonymized train-clean-360. **This is the official VP2026 ranking attacker. Always run this for any result you'll cite.**

When EER is mentioned without a condition, assume `semi_informed`.

**Architecture (B2 and most competitive systems):**
1. Content encoder: HuBERT or ContentVec (layers 6-9) — extracts phonetics, removes speaker
2. Speaker encoder: ECAPA-TDNN — picks a target voice (farthest-point = most anonymous)
3. Vocoder: HiFi-GAN — synthesizes audio from content + target-speaker

**Common mistakes that waste GPU time:**
- Reporting only `ignorant` EER — reviewers will ask for `semi_informed`
- Using B1 frame_length_ms=25 instead of 20 — gives wrong canonical numbers
- HuBERT layer 1-4 as content encoder — these layers are speaker-leaning, not content-leaning
- HiFi-GAN v1 universal at wrong sample rate — VP2026 is 16kHz, v1 was trained at 22.05kHz

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

**At the start of every session, call `vp_get_context` first.** It returns the researcher's best EER so far, last experiment, active hypothesis, EER trend, and any logged learnings — in one call, under 600 tokens. Do not ask the researcher to re-explain their setup.

| User asks | AI should | Don't do |
|---|---|---|
| "Where was I?" / session start | Call `vp_get_context` | Ask the researcher to explain their setup |
| "Which was my best run?" | Call `vp_get_leaderboard` | Read experiments one at a time |
| "How does my system compare to baseline?" | Use `/vp-baseline-compare` | Write a one-off comparison script |
| "Test if X improves EER" | Use `/vp-hypothesis` then `/vp-spike` | Run experiments without a logged hypothesis |
| "Run the attacker against my system" | Use `/vp-attack` | Train ECAPA from scratch each time |
| "Verify this is reproducible" | Use `/vp-repro-check` | Hand-check seed/splits |
| "Write up what we did" | Use `/vp-writeup` | Generate prose with citations (hallucinated — vpstack explicitly refuses) |
| Something unexpected went wrong | Call `vp_get_learnings` first | Start debugging blind |

**When in doubt**, look up the canonical reference for a component via:
```python
mcp_client.call("vp_get_component_info", {"component_name": "hubert"})
# Known: hubert, contentvec, wavlm, ecapa-tdnn, hifi-gan, mcadams, plda
```

Returns description, tradeoffs, known_issues, papers, and license — no hallucination. Also check `known_issues` before debugging — many failure modes are already catalogued.

---

## ✂ Copy ends here ↑

After pasting this into your project's `CLAUDE.md`, edit the `<TODO: ...>` section at the top with your project's specifics. Optionally also add:

- Your team's specific naming conventions (config files, output dirs, etc.)
- Your team's specific eval protocol if it deviates from VP2026 default
- Pointers to internal docs / lab notebooks
- Names of co-authors / collaborators who also work in this repo
