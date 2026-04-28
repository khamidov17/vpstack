---
name: vp-talk
version: 0.1.0-dev
description: |
  Voice-anonymization research-direction office hours. Eight forcing questions that pin down
  the open question, threat model, contribution claim, baseline choice, eval scope, failure
  modes, scope discipline, and (if clinical) HIPAA-grade threat surface — before any
  hypothesis is formalized or GPU time is spent. Writes to
  ~/.vpstack/projects/{slug}/research-plans/{id}.md. Use when starting a new research
  direction, considering a pivot, or preparing for a paper submission. Run before
  /vp-hypothesis. (vpstack)
  Voice triggers: "research direction", "is this worth pursuing", "vp office hours",
  "what's my contribution", "talk through this".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
  - WebSearch
---

# /vp-talk

Force the researcher to commit to a research direction in writing — open question, threat model, contribution claim, baseline, scope — before formalizing any single hypothesis. The VP2026 equivalent of YC office hours: questions that expose vagueness, not questions that solicit ideas. Output is a locked plan that subsequent `/vp-hypothesis` runs reference.

This skill complements `/vp-hypothesis`. `/vp-hypothesis` formalizes ONE experiment after the direction is set. `/vp-talk` sets the direction.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as `vp-baseline-compare`.

## Workflow

### Step 0: Detect clinical context

Before Q1, scan project's CLAUDE.md / README.md for clinical markers:

```bash
CLINICAL_MARKERS=$(grep -iE 'hipaa|clinical|medical|patient|phi|ehr|ehealth|clinic' \
  CLAUDE.md README.md 2>/dev/null | head -3 || true)
if [ -n "$CLINICAL_MARKERS" ]; then
  CLINICAL_MODE=yes
else
  CLINICAL_MODE=no
fi
```

If unclear, ask once: "Is this a clinical / medical-voice context (HIPAA-grade threat model)?"  A) Yes  B) No.

`CLINICAL_MODE=yes` enables Q8.

### Step 1: Ask the eight forcing questions

Each via AskUserQuestion, **one at a time**. After a weak answer, ask the documented follow-up before moving on. Skip Q8 unless `CLINICAL_MODE=yes`.

**Q1. What's the open question here, in one sentence — and who else has tried to answer it?**
- Strong: gap-shaped, names 1–3 prior attempts with citations.
- Weak: "I want to try X."
- Follow-up: "What's the gap? If [X] works in the original paper, what's left to find out?"
- Optional: invoke `WebSearch` on user's component name + "voice anonymization" + recent year to surface prior work the user may not have read.

**Q2. Who's the attacker, and how informed are they?**
- Strong: names a specific VP2026 attacker condition; ideally specifies a stronger variant.
- Weak: "Standard." / "Figure out later."
- Follow-up: "Privacy claims are conditional on attacker. Which condition is your contribution claim about?"

**Q3. What does this approach do better than B2 — privacy delta, utility delta, or both — quantified how?**
- Strong: numeric thresholds, both privacy and utility named, what counts as failure.
- Weak: "Better privacy."
- Follow-up: "Pick a number you'd be embarrassed to fall short of. 'Better' doesn't survive a reviewer; '+3pp EER, WER stays within 0.3pp' does."

**Q4. Which baseline is the right one to beat, and why that one?**
- Strong: names baseline + reason it's the relevant competitor for *this* claim.
- Weak: "B1 and B2."
- Follow-up: "If your method is selection-class, ECAPA-farthest is your real competitor. If transformation-class (e.g., OHNN), B2 is the floor and prior transformation work is your real competitor. What class is yours?"

**Q5. Which slices do you need to hold up on, and which are you explicitly punting?**
- Strong: in/out lists, both committed before running.
- Weak: "All of them."
- Follow-up: "Cross-gender was new in VP2026 and breaks several 2024 systems. Pre-commit slices or you'll p-hack post-hoc."

**Q6. When does this approach break — be specific.**
- Strong: 3+ named failure modes, each with a planned diagnostic.
- Weak: "I don't know yet."
- Follow-up: "Spend 20 minutes thinking about the worst slice before 40 GPU-hours."

**Q7. What's in scope this cycle vs explicitly deferred?**
- Strong: in/out experiment list, cycle type (exploratory vs submission).
- Weak: "Full submission" without the gating.
- Follow-up: "'Submission' is 6+ weeks. 'Exploratory ablation' is 1 week. Pick one and sequence accordingly."

**Q8. (clinical-only) What's the threat model beyond speaker re-identification, and can you publish at all?**
- Strong: names attribute-inference threats (gender / age / accent / mental-state markers), dataset-access posture, publishability constraints.
- Weak: "It's HIPAA-compliant."
- Follow-up: "VP2026 read-speech eval understates clinical threat surface. Re-identification is one threat; attribute inference is the one that breaks de-identification claims. What does your eval probe for *beyond* speaker re-id?"

### Step 2: Component info lookup (optional)

If the user named a specific component (HuBERT layer X, ECAPA-farthest, HiFi-GAN, McAdams), apply inline domain knowledge from your context. See `docs/domain.md` for the canonical component tradeoff reference. Surface the relevant tradeoffs in the plan doc without any tool call.

### Step 3: Write the research plan

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
mkdir -p ~/.vpstack/projects/$SLUG/research-plans
PLAN_ID="$(date +%Y%m%d-%H%M%S)-$(echo "$Q1_TEXT" | head -c 40 | tr -c 'a-zA-Z0-9' '-' | sed 's/--*/-/g')"
```

Write to `~/.vpstack/projects/$SLUG/research-plans/$PLAN_ID.md`:

```markdown
# Research direction: <one-line>

Date: <ISO 8601>
Project: <slug>
ID: <plan_id>
Status: DRAFT | LOCKED | SUPERSEDED

## Open question (Q1)
<one sentence + 2-4 prior attempts with citations>

## Threat model (Q2)
<attacker condition + any deviation from VP2026 official>

## Contribution claim (Q3)
<quantified primary metric delta vs named baseline + utility floor>

## Baseline selection (Q4)
<which baseline + why this one is the right competitor for the claim>

## Eval scope (Q5)
- In: <slices>
- Out: <slices, with reason>

## Failure modes (Q6)
<3+ named, with planned diagnostic for each>

## Scope this cycle (Q7)
- In: <experiments>
- Out: <experiments, deferred to: ...>
- Cycle type: exploratory ablation | submission prep

## Clinical extensions (Q8, if applicable)
<threat model beyond re-id, dataset access, publishability>

## Linked artifacts
- Hypotheses (will fill via /vp-hypothesis): <list>
- Spikes: <list>
- Experiments: <list>

## Status log
- <date>: DRAFT created via /vp-talk
```

### Step 4: Offer to lock the plan

> "Plan drafted. Lock it in?"
> A) Lock — subsequent /vp-hypothesis runs reference this ID
> B) Keep as draft — I want to revise
> C) Discard

On A: set `Status: LOCKED`, append timestamp to status log.

### Step 5: Suggest next step

> "Direction set. Next: `/vp-hypothesis` to formalize the first experiment, or `/vp-baseline-compare` if you have a system ready and just need numbers vs B1/B2."

If user described a system that doesn't exist yet, suggest `/vp-spike` first.

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

- DONE — plan written + locked or kept as draft per user choice
- DONE_WITH_CONCERNS — written but one or more questions left vague after follow-up (noted as `TODO` in plan)
- BLOCKED — disk write failed

## Domain notes (for AI agents reading this skill)

**OHNN** = Orthogonal Householder Neural Network (Miao et al., IEEE/ACM TASLP 2023, arXiv:2305.18823). Transformation-based speaker anonymizer: a stack of Householder reflections rotates source x-vectors inside the speaker manifold to produce on-distribution pseudo-speakers. Pitch: better than selection-based methods (ECAPA-farthest) on three axes — semi-informed privacy, speaker diversity (no pool exhaustion), language independence. If a user mentions "OHNN + selection method", that's a hybrid — the right competitor is BOTH prior transformation work (Miao 2023) AND prior selection work (ECAPA-farthest), and the contribution claim must specify which axis the hybrid wins on.

**Three architectural families** in VP literature:
1. Classical signal processing (B1 / McAdams)
2. Selection-based neural (B2-style: pulled from a pool toward a target)
3. Transformation-based neural (OHNN-class: speaker vector generated, not picked)
