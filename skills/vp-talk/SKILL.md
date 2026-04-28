---
name: vp-talk
version: 0.3.0
description: |
  Two-mode planning skill for voice anonymization work.
  Two-mode planning skill. Like gstack /office-hours — asks forcing questions,
  then writes a locked plan that downstream skills use.
  Mode R (Research): VP2026 benchmark — 8 forcing questions on open question,
  threat model, contribution claim, baseline, eval scope, failure modes. Writes
  research-plan.md that /vp-hypothesis references.
  Mode E (Engineering): Building a real system — 6 domain questions on domain,
  audio format, methods, metrics, compliance, scale. Writes BOTH domain_config.yaml
  (read by every skill preamble) AND engineering-plan.md (feeds /vp-plan-eng-review).
  Gives concrete tool recommendations and honest gaps.
  Switch modes any time: "switch to research" / "switch to engineering".
  Run before /vp-hypothesis (Research) or /vp-plan-eng-review (Engineering). (vpstack)
  Voice triggers: "research direction", "office hours", "what should I build",
  "vp talk", "planning session", "help me think through this".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
  - WebSearch
---

# /vp-talk

Two modes in one skill.

**Mode R — Research:** 8 forcing questions that expose vagueness before GPU time is spent. Output: a locked research plan that `/vp-hypothesis` runs reference.

**Mode E — Engineering:** 6 domain questions that figure out what you're actually building. Output: a `domain_config.yaml` that tells every vpstack skill about your setup, plus concrete tool recommendations and honest gaps.

**Switch mode any time.** Say "switch to engineering", "actually this is more research", "go back to mode selection" — the skill restarts the relevant section without losing what's already been answered.

---

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null \
  || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null \
  || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null \
  || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null \
  || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

TEL_START=$(date +%s)
MODE=""  # set by Step 0
echo "SLUG: $SLUG"
```

## First-run gate

If `DETECTED_FIRST_RUN`: ask once (Yes / No / Ask later) — same shape as vp-baseline-compare.

---

## Step 0: Mode Selection

**Always ask this first.** Do not assume mode from the user's initial message.

Ask via AskUserQuestion:

> **What kind of work is this?**
>
> A) **Research** — VP2026 benchmark, planning a paper, comparing systems
> B) **Engineering** — building a voice anonymization system for a real application
> C) **Both** — applied research with a real deployment in mind

Set `MODE` from the answer (research / engineering / both).

**Remind the user they can switch at any time:**
> "You can switch modes any time — just say 'switch to research', 'switch to engineering', or 'go back to mode selection'. I'll pick up from there."

For Codex/Cursor: present as a numbered list, wait for user response, store answer in `$MODE`.

---

## Mode R: Research — VP2026 Forcing Questions

*Skip to Mode E if MODE=engineering. Run both if MODE=both (Engineering first, then Research).*

Force the researcher to commit to a direction in writing before a single hypothesis is logged. One question at a time. After a weak answer, ask the documented follow-up.

### R1. What's the open question — one sentence — and who else has tried to answer it?

- **Strong:** gap-shaped, names 1–3 prior attempts.
- **Weak:** "I want to try X."
- **Follow-up:** "What's the gap? If [X] works in the original paper, what's left to find?"
- *Optional:* `WebSearch` on the user's component + "voice anonymization" + current year for prior work they may have missed.

### R2. Who's the attacker, and how informed are they?

- **Strong:** names a specific VP2026 condition; ideally specifies a stronger variant.
- **Weak:** "Standard" / "figure out later."
- **Follow-up:** "Privacy claims are conditional on attacker. Which condition does your contribution live or die on?"

### R3. What does this do better than B2 — quantified how?

- **Strong:** numeric thresholds, both privacy and utility named, what counts as failure.
- **Weak:** "Better privacy."
- **Follow-up:** "Pick a number you'd be embarrassed to fall short of. '+3pp EER, WER within 0.3pp' survives a reviewer; 'better' doesn't."

### R4. Which baseline is the right one to beat, and why that one?

- **Strong:** names baseline + reason it's the relevant competitor for THIS claim.
- **Weak:** "B1 and B2."
- **Follow-up:** "Selection-class → ECAPA-farthest is your real competitor. Transformation-class (OHNN) → B2 is the floor, prior transformation work is the bar. What class is yours?"

### R5. Which slices are in-scope, which are explicitly out?

- **Strong:** committed in/out list, both written down before running.
- **Weak:** "All of them."
- **Follow-up:** "Cross-gender is new in VP2026 and breaks several VP2024 systems. Pre-commit slices or you'll p-hack post-hoc."

### R6. When does this approach break — be specific?

- **Strong:** 3+ named failure modes, each with a planned diagnostic.
- **Weak:** "I don't know yet."
- **Follow-up:** "Spend 20 minutes naming the worst slice before spending 40 GPU-hours."

### R7. What's in scope this cycle vs explicitly deferred?

- **Strong:** in/out experiment list, named cycle type.
- **Weak:** "Full submission" without the gating.
- **Follow-up:** "'Submission' is 6+ weeks. 'Exploratory ablation' is 1 week. Pick one."

### R8. (Clinical projects only) Threat model beyond speaker re-identification?

Scan for clinical signals before asking:
```bash
CLINICAL=$(grep -iE 'hipaa|clinical|medical|patient|phi|ehr' CLAUDE.md README.md 2>/dev/null | wc -l | tr -d ' ')
[ "$CLINICAL" -gt 0 ] && echo "CLINICAL_MODE=yes" || echo "CLINICAL_MODE=no"
```

If `CLINICAL_MODE=yes` OR user mentioned medical/HIPAA anywhere: ask this question.

- **Strong:** names attribute-inference threats (gender / age / accent / mental-state), dataset-access posture, publishability constraints.
- **Weak:** "It's HIPAA-compliant."
- **Follow-up:** "VP2026 read-speech eval understates clinical threat surface. Re-identification is one threat; attribute inference is the one that breaks de-identification claims."

### R — Write research plan

```bash
mkdir -p ~/.vpstack/projects/$SLUG/research-plans
PLAN_ID="$(date +%Y%m%d-%H%M%S)-$(echo "$R1_TEXT" | head -c 40 | tr -c 'a-zA-Z0-9' '-' | sed 's/--*/-/g')"
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/research-plans/$PLAN_ID.md`:

```markdown
# Research direction: <one-line>

Date: <ISO 8601>
Project: <slug>
ID: <plan_id>
Status: DRAFT

## Open question (R1)
<one sentence + 1–3 prior attempts>

## Threat model (R2)
<attacker condition>

## Contribution claim (R3)
<quantified delta vs named baseline + utility floor>

## Baseline (R4)
<which + why>

## Eval scope (R5)
- In: ...
- Out: ...

## Failure modes (R6)
<3+ named with planned diagnostic>

## Scope this cycle (R7)
- In: ...
- Out (deferred): ...
- Cycle type: exploratory ablation | submission prep

## Clinical (R8, if applicable)
<attribute-inference threats, dataset access, publishability>

## Linked artifacts
- Hypotheses: (fill via /vp-hypothesis)
- Experiments: (fill via /vp-spike)
```

Ask: "Lock this plan?" A) Lock  B) Keep draft  C) Discard

On A: set `Status: LOCKED`.

**Next step:** `/vp-hypothesis` to formalize the first experiment from this direction.

---

## Mode E: Engineering — Domain Setup

*Skip to Mode R if MODE=research. Run this first if MODE=both.*

6 questions. Each has a default if the user isn't sure — always offer a default so the session stays moving. After all 6, generate concrete recommendations + `domain_config.yaml`.

### E1. What's your domain?

Ask via AskUserQuestion:

> **What kind of audio are you working with?**
>
> A) Call center / customer service (telephone, 8kHz, noisy)
> B) Medical / clinical speech (dictation, consultations, patient audio)
> C) Podcast / broadcast (studio or semi-studio quality)
> D) Research audio (LibriSpeech / VCTK / similar clean read speech)
> E) General / other — I'll describe it

If E: ask free-form. Store as `DOMAIN`.

### E2. What's your audio format?

Ask via AskUserQuestion:

> **Sample rate and channels?**
>
> A) 8 kHz mono (telephone standard — most call center)
> B) 16 kHz mono (research standard — LibriSpeech, VCTK)
> C) 44.1 or 48 kHz (professional recording, podcast)
> D) Mixed / I don't know yet

Store as `SAMPLE_RATE`. If A or C: flag immediately — B1 and all neural models assume 16kHz. Resampling is required.

```bash
# Resample command to show user if needed:
# sox input.wav -r 16000 output.wav
# or: ffmpeg -i input.wav -ar 16000 output.wav
# or batch: for f in dir/**/*.wav; do sox "$f" -r 16000 "${f%.wav}_16k.wav"; done
```

### E3. What anonymization methods are you considering?

Ask via AskUserQuestion (multi-select OK):

> **Which anonymization approach(es)?**
>
> A) Signal processing (McAdams B1 — CPU, fast, weak privacy, no GPU needed)
> B) Neural: speaker selection / farthest-point (B2-style: pick furthest target from a pool)
> C) Neural: OHNN — transformation-based (Miao et al. 2023, on-distribution pseudospeakers)
> D) Neural: B2 full pipeline (HuBERT content + ECAPA speaker + HiFi-GAN vocoder)
> E) Custom / my own method
> F) Not sure yet — help me choose

If F: ask 2 follow-ups — "Is privacy or utility your harder constraint?" and "Do you have GPU access?" Then recommend based on answers. (CPU-only → B1. GPU + strong privacy → B2/OHNN. GPU + interpretability → selection.)

Store as `METHODS` list.

### E4. Which metrics matter most?

Ask via AskUserQuestion (multi-select):

> **What are you measuring? Pick all that apply.**
>
> A) EER — speaker verification, primary privacy metric (higher = more private)
> B) WER — transcription quality / utility (lower = better)
> C) PMOS / UTMOS — naturalness / perceptual quality (higher = better)
> D) Linkability (ZEBRA Cllr) — lower = harder to link speakers
> E) Compliance / audit trail (HIPAA, GDPR)
> F) Real-time factor / latency (production constraint)

Store as `METRICS` list. Note which vpstack provides vs what user must bring themselves.

### E5. Compliance requirements?

Ask via AskUserQuestion:

> **Any regulatory constraints?**
>
> A) HIPAA (US medical — data stays local, audit logs required)
> B) GDPR (EU — data minimization, right to erasure)
> C) Both
> D) None — research / internal use only

Store as `COMPLIANCE`. If A or B or C: add `vpstack-config set telemetry off` to setup commands.

### E6. Scale?

Ask via AskUserQuestion:

> **How much audio are you processing?**
>
> A) Small (< 100 hours) — single machine, batch overnight
> B) Medium (100–1000 hours) — GPU server, multi-day run
> C) Large (> 1000 hours) — HPC / cluster needed
> D) Real-time / streaming — latency constraint (< 500ms)

Store as `SCALE`.

---

### E — Generate recommendations

Based on `DOMAIN`, `SAMPLE_RATE`, `METHODS`, `METRICS`, `COMPLIANCE`, `SCALE`:

**Tell the user clearly:**

#### What vpstack can do for you right now
- `/vp-hypothesis` — formalize what you're testing before spending compute
- `/vp-spike` — run B1 variants as baseline anchor (writes McAdams script to /tmp)
- `/vp-repro-check` — verify seeds, splits, checkpoint hashes before writing up
- `/vp-writeup` — structured experiment report from your logs (no hallucinated citations)
- Experiment logging to `~/.vpstack/projects/{slug}/experiments/`

#### Tools you need to bring (with install commands)

Build this list dynamically from their answers:

**If SAMPLE_RATE ≠ 16kHz:**
```bash
pip install sox  # or: brew install sox / apt install sox
# Resample: sox input.wav -r 16000 output.wav
```

**If METHODS includes OHNN:**
> OHNN is not bundled in vpstack. You need the SpeechBrain OHNN recipe or Miao et al. reference implementation. `pip install speechbrain` — then follow their anonymization recipe.

**If METHODS includes Selection / B2:**
> ECAPA farthest-point and HiFi-GAN are not bundled. `pip install speechbrain` and follow the VP2026 challenge B2 recipe from the official challenge organizers.

**If METRICS includes WER:**
```bash
pip install openai-whisper
# Run: whisper /path/to/anon_audio --model medium --language en
```

**If METRICS includes PMOS/UTMOS:**
```bash
pip install utmos  # or: pip install torchaudio (for Squim)
# UTMOS: from utmos import UTMOSScore; score = UTMOSScore().score("file.wav")
# Squim: import torchaudio; bundle = torchaudio.pipelines.SQUIM_OBJECTIVE.get_model()
```

**If METRICS includes EER:**
> EER needs an ASV system + your own trial list (target/nontarget speaker pairs). vpstack does not generate trial lists for custom datasets. Build one with: enrollment directory (1–3 utterances/speaker) + test utterances + labels CSV.
```bash
pip install speechbrain
# Use spkrec-ecapa-voxceleb for ASV scoring: speechbrain/spkrec-ecapa-voxceleb
```

**If COMPLIANCE includes HIPAA/GDPR:**
```bash
~/.claude/skills/vpstack/bin/vpstack-config set telemetry off
# Verify: vpstack-config get telemetry  (should print: off)
```

**If SCALE is Large or Real-time:**
> Large: B1 is embarrassingly parallel — `parallel python3 /tmp/vp_b1_run.py ::: dir1 dir2 ...`
> Real-time: B1 is fast (~8x realtime on CPU). Neural methods (B2/OHNN) are too slow for real-time without GPU + batching optimization.

#### The honest gap list

Tell the user directly:
```
vpstack v0.2 does NOT provide:
  ✗ OHNN or selection anonymization (bring SpeechBrain)
  ✗ WER evaluation (bring Whisper or your ASR system)
  ✗ PMOS / naturalness scoring (bring UTMOS or Squim)
  ✗ EER calculation on custom trial lists (bring ASV + your trial file)
  ✗ B2 neural pipeline (coming v0.3)
  ✗ Real-time streaming (batch-only for now)

vpstack v0.2 DOES provide:
  ✓ B1 McAdams anonymization on any WAV directory
  ✓ Experiment tracking + reproducibility gates
  ✓ Workflow discipline (hypothesis → spike → repro → ship)
  ✓ Domain knowledge encoded in every skill
```

---

### E — Write domain_config.yaml

```bash
mkdir -p ~/.vpstack/projects/$SLUG
CONFIG_PATH="$HOME/.vpstack/projects/$SLUG/domain_config.yaml"
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/domain_config.yaml`:

```yaml
# Generated by /vp-talk engineering mode — <ISO 8601>
# Read by: /vp-baseline-compare, /vp-spike, /vp-repro-check, /vp-qa
# Update by re-running /vp-talk and choosing Engineering mode.

project_slug: <SLUG>
domain: <DOMAIN>           # call_center | medical | podcast | research | other
sample_rate_native: <Hz>   # original audio sample rate
resample_to: 16000         # required for B1 and all neural models
resample_required: <true|false>

anonymization_methods:
  - <method>  # b1_mcadams | ohnn | selection | b2_neural | custom

metrics:
  primary:
    - <metric>  # eer | wer | pmos | linkability
  secondary:
    - <metric>

compliance: <none|hipaa|gdpr|both>
telemetry: <on|off>        # off if hipaa/gdpr

scale: <small|medium|large|realtime>

tools_needed:
  <tool>: <install_command>
  # e.g., whisper: "pip install openai-whisper"
  # e.g., speechbrain: "pip install speechbrain"
  # e.g., utmos: "pip install utmos"

vpstack_skills_applicable:
  - vp-hypothesis
  - vp-spike         # B1 baseline only in v0.2
  - vp-repro-check
  - vp-writeup
  # add vp-baseline-compare when you have anonymized output to compare

notes: |
  <free-form notes from E5/E6 — scale, compliance, domain-specific issues>
```

**Tell the user:** "This config lives at `~/.vpstack/projects/{slug}/domain_config.yaml`. Every vpstack skill will read it automatically. Re-run `/vp-talk` → Engineering mode to update it."

---

### E — Write engineering design plan

After generating the config, synthesize the conversation into a design plan document. This is the equivalent of gstack's `/office-hours` output — a structured plan that feeds into `/vp-plan-eng-review` and `/vp-plan-design-review`.

```bash
mkdir -p ~/.vpstack/projects/$SLUG/engineering-plans
PLAN_ID="$(date +%Y%m%d-%H%M%S)-$(echo "$DOMAIN" | tr -c 'a-zA-Z0-9' '-')"
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/engineering-plans/$PLAN_ID.md`:

```markdown
# Engineering Plan: <one-line description of what's being built>

Date: <ISO 8601>
Project: <slug>
ID: <plan_id>
Mode: Engineering
Status: DRAFT

## What we're building
<1–2 sentences: the system, the use case, who uses it>

## The real problem
<What pain does this solve? Be specific — not "anonymize audio" but
"35-minute call center recordings need speaker identity removed before
QA team reviews transcripts; current manual redaction takes 2h/recording">

## Domain context (from E1–E2)
- Audio domain: <DOMAIN>
- Native sample rate: <SAMPLE_RATE_NATIVE> Hz
- Resample required: <true|false> (target: 16kHz for all models)
- Scale: <SCALE>
- Compliance: <COMPLIANCE>

## Anonymization approach (from E3)
Methods selected: <METHODS>

Rationale:
<Why these methods for this domain? E.g.: "OHNN chosen over selection because
call center audio has only 12 enrolled agents — pool exhaustion is a real risk.
OHNN generates on-distribution pseudo-speakers without pool dependency.">

## Success criteria (from E4)
Primary metrics:
<metric>: <target value and direction — e.g., "EER > 35% (higher = more private)">

Secondary metrics:
<metric>: <target>

Failure definition:
<What makes this a failed system? E.g., "EER < 20% on semi-informed attacker
OR WER > 15% on our existing ASR pipeline">

## Implementation sequence
1. Set up audio preprocessing (resample to 16kHz, format validation)
2. Run B1 as baseline anchor via vpstack `/vp-spike`
3. Implement [primary method] — bring own SpeechBrain recipe
4. Evaluate: EER via ASV, WER via Whisper, PMOS via UTMOS
5. Repro-check before writing up
6. Ship via `/vp-ship`

## Tools required (bring your own)
<List from E — generate recommendations section>

## vpstack coverage
What vpstack handles:
- B1 McAdams baseline anchor
- Experiment tracking and logging
- Reproducibility checking (PASS_STRONG / PASS_WEAK)
- Engineering review gates (/vp-plan-eng-review)
- Writeup generation

What you bring:
- [Primary anonymization method] implementation
- EER evaluation (ASV + trial list)
- WER evaluation (ASR system)
- PMOS evaluation (UTMOS or Squim)

## Risks and open questions
<Named risks — e.g.: "8kHz telephone audio has limited phonetic information;
HuBERT features may be noisier than on clean read speech. Benchmark B1 on
actual call center clips before committing to neural pipeline.">

## Next step
<Specific next action — e.g.: "/vp-hypothesis to formalize the B1 vs OHNN
ablation, then /vp-spike to run both on 10 held-out recordings">

## Linked artifacts
- Domain config: ~/.vpstack/projects/<slug>/domain_config.yaml
- Hypotheses: (fill via /vp-hypothesis)
- Experiments: (fill via spikes and runs)
```

Ask: "Lock this plan?" A) Lock  B) Keep draft  C) Discard

On A: set `Status: LOCKED`. This plan feeds `/vp-plan-eng-review` — run that next for 18 engineering quality gates against this document.

---

### E — Suggest next step

Based on their answers and whether the plan is locked:

- **Plan locked, audio ready** → "Run `/vp-plan-eng-review` to review the engineering plan, then `/vp-hypothesis` to formalize your first experiment."
- **Plan locked, no audio yet** → "Get audio in the right format first (resample to 16kHz). Then `/vp-hypothesis` to formalize what you're testing."
- **Compliance flagged** → "Before anything else: `~/.claude/skills/vpstack/bin/vpstack-config set telemetry off` — verify with `vpstack-config get telemetry`."
- **Methods include OHNN/Selection/B2** → "Install SpeechBrain: `pip install speechbrain`. The official VP2026 challenge repo has the B2/attacker recipes."

---

## Mode B: Both (Research + Engineering)

Run Engineering mode (E1–E6) first to set up the domain config. Then run Research mode (R1–R7) for the academic framing. The research plan references the domain_config.yaml for context.

The plan doc gets an additional section:
```markdown
## Engineering context
Domain config: ~/.vpstack/projects/{slug}/domain_config.yaml
Domain: <from E1>
Methods: <from E3>
Metrics: <from E4>
```

---

## Mode switching

**At any point in the session**, if the user says any of:
- "switch to research" / "actually this is a paper" / "let's do the research framing"
- "switch to engineering" / "I'm building a system" / "let's do the practical setup"
- "go back to mode selection" / "I want to pick again" / "restart"
- "change mode"

→ Restart from Step 0 (Mode Selection). Keep any answers already given in the session — don't ask Q2 again if you already have the answer. Show a brief "Switching to [mode]. Here's what we have so far: [summary]" before restarting.

For Codex/Cursor: watch for these phrases in any user message and restart the appropriate section.

---

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-talk \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

## Completion status

- DONE — plan/config written, next step suggested
- DONE_WITH_CONCERNS — written but weak answers remain (noted as TODO in output)
- BLOCKED — disk write failed

---

## Domain notes (read this before responding to any voice anonymization question)

**Three architectural families:**
1. Signal processing — B1 McAdams (no ML, CPU, fast, weak privacy)
2. Selection-based neural — B2-style: pick a target voice from a pool via speaker embeddings (ECAPA-TDNN farthest-point). Good naturalness, bounded by pool diversity.
3. Transformation-based neural — OHNN (Miao et al., IEEE/ACM TASLP 2023): stack of Householder reflections rotates x-vectors inside speaker manifold. On-distribution pseudo-speakers, no pool exhaustion, language-independent.

**OHNN vs Selection comparison:**
- OHNN: stronger privacy (no pool to exhaust), better speaker diversity, works across languages
- Selection: simpler to implement, interpretable (you know which target was used), naturalness limited by pool quality
- Hybrid (OHNN + selection pool): contribution must specify which axis it wins on vs each predecessor

**EER:** Higher = more private. 50% = random attacker = perfect anonymization. Do not use numbers from VP2020/VP2022/VP2024 as references — run baselines on the user's actual VP2026 data.

**PMOS/UTMOS:** Pseudo-MOS — uses a learned model (UTMOS, Saeki et al. 2022, or Squim/torchaudio) to predict naturalness without human listeners. Range typically 1–5. Not a replacement for real MOS but useful for fast iteration.
