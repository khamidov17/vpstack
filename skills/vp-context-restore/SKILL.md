---
name: vp-context-restore
version: 0.1.0
description: |
  Restore working context from a previous session. Reads session-state.md and
  presents a 2-sentence briefing: what you were doing and what to do next.
  Run at the start of any session after a break. Pair with /vp-context-save. (vpstack)
  Voice triggers: "restore context", "resume", "where was I", "pick up where I left off".
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /vp-context-restore

Resume a voice-privacy research session without reconstructing context from scratch. Reads the session state saved by `/vp-context-save` and delivers a 2–3 sentence briefing — what hypothesis was active, what the last experiment showed, and what to do next. One command, no cognitive overhead.

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

### Step 1: Read session-state.md

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
STATE_FILE=~/.vpstack/projects/$SLUG/session-state.md
if [ -f "$STATE_FILE" ]; then
  cat "$STATE_FILE"
else
  echo "NO_STATE"
fi
```

### Step 2: Handle missing state

If the output is `NO_STATE`:

Tell the user:

> "No saved session found for this project ($SLUG). Run /vp-context-save at the end of your next session to enable this."

Then exit (run telemetry with `OUTCOME=abort`).

### Step 3: Synthesize briefing

If the state file was found, read it and compose a 2–3 sentence briefing. Structure:

- **Sentence 1 — hypothesis:** What hypothesis was active and its status. Example: "Last session you were working on hypothesis `2026-04-27-ecapa-pitch-shift` (status: IN_PROGRESS), testing whether pitch-shifted enrollment improves EER."
- **Sentence 2 — last result:** What the most recent experiment showed. Example: "The last experiment (`attack-semi_informed-20260427-1423`) reported EER=38.2%, which is above B1 (34.8%) but below B2 (28.1%)."
- **Sentence 3 — next step:** The suggested next skill. Example: "The saved state suggests running /vp-spike next to ablate the pitch-shift component."

If any field is "none" or "n/a", omit that sentence rather than stating it as "none". If all three fields are absent, say: "Session state file exists but has no substantive content — try re-running /vp-context-save."

Also surface the branch: "Session was saved on branch `<branch>`" — if the current branch differs, note it: "You are now on `<current_branch>`."

Check current branch:
```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
echo "Current branch: $CURRENT_BRANCH"
```

### Step 4: Ask how to proceed

Ask via AskUserQuestion:

> "Resume from here?"
>
> A) Yes — continue with the suggested next skill (<SUGGESTED_NEXT_SKILL>)
> B) Show me the full session state
> C) Start fresh — ignore saved state and start a new hypothesis

**If A:**

Emit the suggested next skill name so Claude invokes it. For example, if the suggested next skill is `/vp-spike`, say: "Continuing with /vp-spike." Then invoke that skill's workflow as if the user had typed the slash command. If the suggested next skill is not recognized or is blank, ask the user what they would like to do instead.

**If B:**

Use the Read tool to read `~/.vpstack/projects/$SLUG/session-state.md` and display its full contents verbatim, formatted as a code block. Then ask the user what they would like to do next.

**If C:**

Say: "Ignoring saved state. To start a new direction, try /vp-hypothesis to formalize your next experiment." Exit cleanly (run telemetry with `OUTCOME=abort`).

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-context-restore \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

`OUTCOME`: `success` | `error` | `abort`. On error, include `--error-class` from allowlist: `DATA_MISSING`, `INVALID_CONFIG`.

## Completion status

- DONE — briefing delivered, user chose a path (A resumed next skill, B showed full state)
- ABORT — no saved state found, or user chose C (start fresh)
