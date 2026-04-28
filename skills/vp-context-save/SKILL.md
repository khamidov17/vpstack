---
name: vp-context-save
version: 0.1.0
description: |
  Save current session state so any future session can resume without losing the thread.
  Captures: current hypothesis ID, last experiment ID, last skill run, what's pending,
  suggested next skill. Writes to ~/.vpstack/projects/{slug}/session-state.md.
  Run before ending a session, switching branches, or handing off to a collaborator.
  Pair with /vp-context-restore. (vpstack)
  Voice triggers: "save my progress", "save session", "context save", "save where I am".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-context-save

Snapshot the current session so any future session — or a collaborator — can pick up without losing the thread. Voice-privacy research is iterative: hypotheses get abandoned mid-run, baselines shift, and context evaporates overnight. This skill captures where you are and what to do next so you don't have to reconstruct it from scratch.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-context-save 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-context-save 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;        # Skill body handles AskUserQuestion below
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi

SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
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

### Step 1: Collect context via bash

Run all context-gathering commands in a single Bash call:

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")

# Most recent hypothesis (by filename sort — filenames are ISO-prefixed)
LATEST_HYP=$(ls ~/.vpstack/projects/$SLUG/hypotheses/ 2>/dev/null | sort -r | head -1)

# Most recent experiment
LATEST_EXP=$(ls ~/.vpstack/projects/$SLUG/experiments/ 2>/dev/null | sort -r | head -1)

# Most recent spike
LATEST_SPIKE=$(ls ~/.vpstack/projects/$SLUG/spikes/ 2>/dev/null | sort -r | head -1)

# Recent timeline (last 5 skill runs)
RECENT_TIMELINE=$(tail -5 ~/.vpstack/analytics/timeline.jsonl 2>/dev/null || echo "no timeline")

# First line of latest hypothesis file (the title / status line)
HYP_FIRST_LINE=""
if [ -n "$LATEST_HYP" ]; then
  HYP_FILE=$(ls ~/.vpstack/projects/$SLUG/hypotheses/$LATEST_HYP/*.md 2>/dev/null | head -1)
  if [ -n "$HYP_FILE" ]; then
    HYP_FIRST_LINE=$(head -1 "$HYP_FILE" 2>/dev/null || echo "")
  fi
fi

# EER/WER from latest experiment summary if it exists
EXP_METRICS=""
if [ -n "$LATEST_EXP" ]; then
  EXP_JSON=~/.vpstack/projects/$SLUG/experiments/$LATEST_EXP/summary.json
  if [ -f "$EXP_JSON" ]; then
    EXP_METRICS=$(python3 -c "
import json, sys
try:
  d = json.load(open('$EXP_JSON'))
  m = d.get('metrics') or d.get('b1') or {}
  eer = m.get('eer_overall') or m.get('eer') or 'n/a'
  wer = m.get('wer') or 'n/a'
  print(f'EER={eer}  WER={wer}')
except Exception as e:
  print('metrics unavailable')
" 2>/dev/null || echo "metrics unavailable")
  fi
fi

# Domain config
DOMAIN_CONFIG="$HOME/.vpstack/projects/$SLUG/domain_config.yaml"
DOMAIN_INFO=""
if [ -f "$DOMAIN_CONFIG" ]; then
  DOMAIN_INFO=$(grep -E "^(domain|methods|sample_rate_native):" "$DOMAIN_CONFIG" 2>/dev/null | tr '\n' ' ')
fi

# Current git branch
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Current ISO timestamp
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=== CONTEXT SNAPSHOT ==="
echo "Slug: $SLUG"
echo "Branch: $GIT_BRANCH"
echo "Timestamp: $NOW"
echo "Latest hypothesis: ${LATEST_HYP:-none}"
echo "Hypothesis title: ${HYP_FIRST_LINE:-n/a}"
echo "Latest experiment: ${LATEST_EXP:-none}"
echo "Experiment metrics: ${EXP_METRICS:-n/a}"
echo "Latest spike: ${LATEST_SPIKE:-none}"
echo "Domain config: ${DOMAIN_INFO:-none}"
echo "--- Recent timeline ---"
echo "$RECENT_TIMELINE"
```

Read this output carefully — it supplies the values for the session-state.md template.

### Step 2: Ask about pending work and next skill

Ask via AskUserQuestion:

> "What should I capture as 'what's pending' and 'suggested next skill'?"
>
> A) Auto-detect from recent activity — infer pending work from hypothesis status and timeline
> B) Let me describe it — I'll tell you what's pending and what to do next

If A: infer from the collected context:
- If `LATEST_HYP` exists and the hypothesis file contains `status: PENDING` or `status: IN_PROGRESS` → pending = "Continue hypothesis $LATEST_HYP"; suggested next skill = `/vp-spike`
- If hypothesis status is `CONFIRMED` → pending = "Run full evaluation on $LATEST_HYP"; suggested next skill = `/vp-baseline-compare`
- If hypothesis status is `DONE` and no newer experiment → pending = "Write up results"; suggested next skill = `/vp-writeup`
- If no hypothesis found → pending = "Formalize current experiment direction"; suggested next skill = `/vp-hypothesis`
- If timeline shows the last skill was `vp-attack` → pending = "Review attacker results, consider next ablation"; suggested next skill = `/vp-spike` or `/vp-eval`
- Apply the first matching rule and tell the user what was inferred before writing.

If B: ask a follow-up via AskUserQuestion:

> "Describe what's pending and what the next skill should be."
>
> (Free text — user types anything; capture as `PENDING_DESC` and `NEXT_SKILL_DESC`)

### Step 3: Write session-state.md

Ensure the directory exists:

```bash
mkdir -p ~/.vpstack/projects/$SLUG
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/session-state.md` (overwriting any existing file — only one session state is kept per project):

```markdown
# Session State
Saved: <ISO 8601 timestamp from NOW>
Branch: <GIT_BRANCH>
Slug: <SLUG>

## Active hypothesis
<LATEST_HYP filename, or "none">
<HYP_FIRST_LINE, or "n/a">

## Last experiment
<LATEST_EXP, or "none">
<EXP_METRICS, or "n/a">

## Last skill run
<Last entry from timeline.jsonl, or "no timeline recorded">

## Pending work
<PENDING_DESC — from user input (option B) or auto-inferred (option A)>

## Suggested next skill
<NEXT_SKILL_DESC — from user input (option B) or inferred skill name (option A)>

## Domain config
<DOMAIN_INFO, or "none — run /vp-talk Engineering mode to set up your domain">
```

### Step 4: Confirm to user

Tell the user:

> "Session saved to ~/.vpstack/projects/$SLUG/session-state.md.
> Run /vp-context-restore in any future session to resume from here."

If the file was just overwritten (i.e. a previous session-state.md already existed), note: "Previous session state replaced."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-context-save \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

`OUTCOME`: `success` | `error` | `abort`. On error, include `--error-class` from allowlist: `DATA_MISSING`, `INVALID_CONFIG`.

## Completion status

- DONE — session-state.md written, user confirmed
- ABORT — user cancelled or project not recognized as a vpstack project
