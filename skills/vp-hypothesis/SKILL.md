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
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;        # Skill body handles AskUserQuestion below
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi
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

1. **What's the hypothesis?** Free-form text. Example: "Replacing HuBERT layer 12 with layer 6 improves EER by ≥0.5pp without WER regression."
2. **Component being changed?** Free-form. Example: "content encoder (HuBERT layer index)".
3. **Baseline comparison?** A) B1, B) B2, C) prior experiment ID, D) nothing — exploratory.
4. **Expected primary metric direction?** A) EER lower, B) WER lower, C) Linkability lower, D) Multi-objective.
5. **Expected magnitude?** A) <0.5pp (marginal — high replication risk), B) 0.5–2pp (typical paper delta), C) >2pp (probably wrong if you see this).
6. **Acceptance criteria?** Free-form. Example: "EER drops by ≥0.5pp on dev set, WER stays within 0.2pp of B2."
7. **Components held constant?** Free-form (helps `/vp-repro-check` later).

### Step 2: Call MCP tool for component info

```python
info = mcp_client.call("vp_get_component_info", {"component_name": user_component_name})
```

If `info.ok`, surface the tradeoff matrix: "Note: HuBERT layer 6 vs 12 — layer 6 emphasizes content (better speaker disentanglement), layer 12 emphasizes speaker identity. Your hypothesis aligns with published findings (Liu et al. 2024)."

If unknown component, proceed without — note in the doc that vpstack didn't recognize the component.

### Step 3: Write hypothesis doc

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
mkdir -p ~/.vpstack/projects/$SLUG/hypotheses
EXP_ID="$(date +%Y%m%d-%H%M%S)-$(echo "$HYPOTHESIS_TEXT" | head -c 40 | tr -c 'a-zA-Z0-9' '-' | sed 's/--*/-/g')"
```

Write to `~/.vpstack/projects/$SLUG/hypotheses/$EXP_ID.md`:

```markdown
# Hypothesis: <one-line>

Date: <ISO 8601>
Project: <slug>
ID: <exp_id>

## What we're testing
<full hypothesis text>

## Component changed
<component>

## Baseline comparison
<B1 / B2 / prior exp / exploratory>

## Expected direction & magnitude
<metric: ↓ / ↑> by <magnitude>

## Acceptance criteria
<criteria>

## Held constant
<list>

## Component info from vpstack
<output of vp_get_component_info, if available>

## Status
PENDING

## Result
(to be filled by /vp-spike or /vp-baseline-compare)
```

### Step 4: Suggest next step

> "Hypothesis logged. Next: run `/vp-spike` to test it, or `/vp-baseline-compare` if you want a full B1+B2 comparison."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-hypothesis --duration "$TEL_DUR" --outcome "$OUTCOME"
```

Where `OUTCOME` is one of: `success`, `error`, `abort`. On `error`, include `--error-class` from the allowlist.

## Completion status

- DONE — hypothesis doc written, suggested next step shown
- DONE_WITH_CONCERNS — written but vp_get_component_info couldn't resolve component (noted in doc)
- BLOCKED — disk write failed
