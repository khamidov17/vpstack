---
name: vp-hypothesis
version: 0.1.0-dev
description: |
  Formalize a voice-anonymization experiment hypothesis before running anything. Captures what's
  being tested, expected delta vs baseline, evaluation criteria, and which components are being
  swapped. Use when starting a new experiment or before /vp-spike. Writes to
  ~/.vpstack/projects/{slug}/hypotheses/{id}.md. (vpstack)
  Voice triggers: "new experiment", "hypothesis", "test if".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-hypothesis

Force the researcher to formalize a hypothesis before code runs. Catches "I'll know it when I see it" experiments before they consume GPU time. Output is a structured doc the researcher refers back to when interpreting results.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-hypothesis 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-hypothesis 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;        # Skill body handles AskUserQuestion below
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi

TEL_START=$(date +%s)
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion:

> "This project looks like voice-anonymization work (matched: $ACTIVATION_REASON). Enable vpstack here?"
>
> A) Yes, enable for this project
> B) No, silence vpstack on this project forever
> C) Ask me again next time

On A: `mkdir -p .vpstack && touch .vpstack/enabled`, append project hash to `~/.vpstack/projects-decided`, and proceed.
On B: `mkdir -p .vpstack && touch .vpstack/disabled`, exit silently.
On C: `mkdir -p .vpstack && touch .vpstack/ask-later` and exit silently. Marker valid for 60min — prevents re-prompt loops in a multi-skill session.

## Workflow

### Step 1: Gather hypothesis structure via AskUserQuestion (one at a time)

Ask each question separately. Wait for the answer before moving to the next.

1. **What's the hypothesis?** Free-form text. Example: "Replacing HuBERT layer 12 with layer 6 improves EER by ≥0.5pp without WER regression."
2. **Component being changed?** Free-form. Example: "content encoder (HuBERT layer index)".
3. **Baseline comparison?** A) B1, B) B2, C) prior experiment ID, D) nothing — exploratory.
4. **Expected primary metric direction?** A) EER higher (more private), B) WER lower (better utility), C) Linkability lower, D) Multi-objective.
5. **Expected magnitude?** A) <0.5pp (marginal — high replication risk), B) 0.5–2pp (typical paper delta), C) >2pp (probably wrong if you see this).
6. **Acceptance criteria?** Free-form. Example: "EER drops by ≥0.5pp on dev set, WER stays within 0.2pp of B2."
7. **Components held constant?** Free-form. Example: "ECAPA-TDNN speaker encoder, HiFi-GAN vocoder, seed=42." (Helps `/vp-repro-check` later.)

### Step 2: Apply inline domain knowledge for the named component

Do **not** call any tool. Apply the domain knowledge below directly based on the component the user named in question 2.

**HuBERT content encoder**
- Layer index controls the privacy/utility tradeoff. Lower layers (1–6) encode acoustic content and phonetics — better speaker disentanglement, slightly higher WER risk. Higher layers (9–12) encode stronger speaker identity — easier for the vocoder to reconstruct naturalness, but leaks more identity to the ASV attacker.
- Layer 6 is the standard VP2026 B2 default. Layer 9 is often used as an ablation point.
- If the user is testing a different layer index: "Layer <N> vs the B2 default (layer 6) — lower layers disentangle speaker better (privacy gain, possible WER cost); higher layers retain more identity (WER gain, privacy cost). Your hypothesis is consistent with published findings (e.g., Srivastava et al. 2022)."

**ECAPA-TDNN speaker encoder**
- Produces the speaker embedding used to condition the vocoder on target speaker identity. Channel width (512 vs 1024) and the pooling layer affect how much identity leaks through.
- Swapping speaker embeddings (e.g., using a random target pool vs a fixed pseudo-speaker) is the most common ablation. Random pools improve EER at the cost of naturalness.
- If the user is testing speaker pool strategy or ECAPA variants: note that the embedding dimensionality must match the HiFi-GAN conditioning input — check `hifigan_anon.yaml` if changing channel width.

**HiFi-GAN vocoder**
- The HiFi-GAN in B2 is conditioned on both HuBERT content features and the ECAPA speaker embedding. It is the primary source of naturalness (WER) but also a potential identity leakage point if the speaker conditioning is too strong.
- Fine-tuning on anonymized data vs using the pretrained checkpoint is a common ablation. Fine-tuning improves WER but can degrade privacy if the fine-tuning data leaks identity.
- If the user is testing vocoder fine-tuning or conditioning ablations: note the risk of identity re-injection through overfitting.

**McAdams coefficient (B1)**
- B1 modifies LPC pole angles by a scalar α (typically 0.8). Higher α = more aggressive pole shift = more privacy, more distortion. Lower α = less distortion, less privacy.
- α is a continuous knob — if the user is testing different α values, expected EER change is roughly monotone with |α - 1.0|, but WER degrades non-linearly for α < 0.6 or α > 1.4.
- B1 has no neural components and no HuggingFace checkpoints to download.

**Unknown component**
- If the component does not match any of the above, note in the hypothesis doc: "vpstack did not recognize this component — no domain tradeoff note added. Consider adding domain context manually."

Surface the relevant tradeoff note to the user as a brief informational message before writing the doc.

### Step 3: Write hypothesis doc

Run in bash to establish paths and IDs:

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
# Derive a short slug from the hypothesis text (first 40 chars, alphanum only)
H_SLUG=$(echo "$HYPOTHESIS_TEXT" | head -c 40 | tr -c 'a-zA-Z0-9' '-' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
EXP_ID="${TIMESTAMP}-${H_SLUG}"
mkdir -p ~/.vpstack/projects/$SLUG/hypotheses
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/hypotheses/$EXP_ID.md`:

```markdown
# Hypothesis: <one-line summary>

Date: <ISO 8601>
Project: <slug>
ID: <EXP_ID>

## What we're testing
<full hypothesis text from question 1>

## Component changed
<answer from question 2>

## Baseline comparison
<B1 / B2 / prior exp ID / exploratory — from question 3>

## Expected direction & magnitude
<metric direction from question 4> by <magnitude from question 5>

## Acceptance criteria
<answer from question 6>

## Held constant
<answer from question 7>

## Component domain notes
<inline tradeoff note from Step 2 — or "Component not recognized by vpstack.">

## Status
PENDING

## Result
(to be filled by /vp-spike or /vp-baseline-compare)
```

### Step 4: Suggest next step

Tell the user:

> "Hypothesis logged at ~/.vpstack/projects/<slug>/hypotheses/<EXP_ID>.md. Next: run `/vp-spike` to test it with 1–3 quick variants, or `/vp-baseline-compare` if you want a full B1+B2 comparison first."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-hypothesis --duration "$TEL_DUR" --outcome "$OUTCOME"
```

Where `OUTCOME` is one of: `success`, `error`, `abort`. On `error`, include `--error-class` from the allowlist.

## Completion status

- DONE — hypothesis doc written, domain note included, suggested next step shown
- DONE_WITH_CONCERNS — written but component was not recognized (noted in doc)
- BLOCKED — disk write failed (check ~/.vpstack/ permissions)
