---
name: vp-brain
version: 0.1.0-dev
description: |
  Browse the local experiment store: list runs, rank by EER/WER, show one run, diff two runs,
  search by hypothesis text, see project stats, list recent skill activity, surface research
  learnings. Thin wrapper over the `vpstack-brain` (vpbrain) CLI. Use when the user asks
  "what experiments have I run?", "best run so far", "diff these two runs", "what have we
  learned about X", "show me the timeline", or pastes /vp-brain. (vpstack)
  Voice triggers: "vpbrain", "vp brain", "experiment store", "show experiments", "best EER".
allowed-tools:
  - Bash
  - AskUserQuestion
---

# /vp-brain

Read-only browser over the JSONL state vpstack writes to `~/.vpstack/projects/{slug}/`. No new data is written here — every other vpstack skill writes the experiment summaries; this skill just queries them.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-brain 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-brain 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi

SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TEL_START=$(date +%s)
VPBRAIN=~/.claude/skills/vpstack/bin/vpstack-brain
[ -x "$VPBRAIN" ] || VPBRAIN=.claude/skills/vpstack/bin/vpstack-brain
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion:

> **Enable vpstack on this project?**
>
> A) Yes, enable here (writes `<repo>/.vpstack/enabled`)
> B) No, silence vpstack here (writes `<repo>/.vpstack/disabled`)
> C) Ask me again next time
>
> Recommendation: A, because vpbrain has nothing to read until at least one vpstack skill runs and logs an experiment.

On A → `mkdir -p .vpstack && touch .vpstack/enabled`. On B → `.vpstack/disabled`. On C → `.vpstack/ask-later` (60-min validity).

## Workflow

### Step 1: Pick the operation

If the user passed a subcommand verbatim (e.g. `/vp-brain top --metric eer`), shell straight through:

```bash
$VPBRAIN $USER_ARGS
```

Otherwise, ask via AskUserQuestion:

> **What do you want to see?**
>
> A) `list` — every experiment, newest first
> B) `top` — rank by EER (privacy) or WER (utility)
> C) `stats` — count, best EER, trend
> D) `query "text"` — search hypothesis / method / tags
> E) `diff EXP_A EXP_B` — side-by-side metric delta
> F) `learnings` — research insights logged across runs
> G) `timeline` — recent skill activity
> H) `projects` — all projects on this machine
>
> Recommendation: B (`top --metric eer`) when the user is looking for "what worked", C (`stats`) for a quick health check, F (`learnings`) when starting a new spike to avoid repeating mistakes.

### Step 2: Run it

Always quote arguments and use the resolved `$VPBRAIN` path so this works on systems where vpstack-brain isn't on `$PATH`:

```bash
# Examples
$VPBRAIN list
$VPBRAIN top --metric eer --limit 5
$VPBRAIN top --metric wer --order asc --limit 5     # WER lower-is-better
$VPBRAIN stats
$VPBRAIN show <EXP_ID>
$VPBRAIN diff <EXP_A> <EXP_B>
$VPBRAIN query "alpha 0.75"
$VPBRAIN learnings --query "B1"
$VPBRAIN timeline --last 20
$VPBRAIN projects

# Cross-project (browse another researcher's slug or another repo's data without cd)
$VPBRAIN --slug other-project-d90a1fb2 list
$VPBRAIN --project other-project-d90a1fb2 top --metric eer
```

### Step 3: Interpret the output

Always remind the user of metric direction when EER/WER appear:

- **EER higher = more private** (50% = random-guess ceiling).
- **WER lower = more useful** (0% = perfect transcription).
- **Linkability lower = harder to re-identify** (ZEBRA Cllr).

If `top --metric eer` shows the top run is the user's most recent system → suggest `/vp-repro-check` before citing it.
If `query` returns a near-duplicate of what they're about to run → suggest `$VPBRAIN show <id>` first to confirm they're not re-running the same config.
If `stats` reports `EER trend: improving` → encourage `/vp-writeup` to lock in the narrative.
If `learnings` surfaces a relevant past finding → quote it back to the user before they start a new spike.

### Step 4: Empty-state handling

- `No experiments yet for project ...` → tell the user that vpbrain reads from skills' summary writes; suggest running `/vp-spike`, `/vp-baseline-compare`, `/vp-attack`, `/vp-implement`, or `/vp-eval` first.
- `No projects yet` → same — vpstack hasn't bootstrapped this project yet.
- `No learnings yet` → suggest the user (or a skill) call `vpstack-learnings-log` to start building project memory.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-brain \
  --duration "$TEL_DUR" \
  --outcome "${OUTCOME:-success}"
```

`OUTCOME` is `success` for any successful query, `error` if the underlying CLI exited non-zero, `abort` if the user cancelled.

## Completion status

- DONE — query ran, output surfaced, metric direction reminders given
- DONE_WITH_CONCERNS — query succeeded but state directory was empty (suggested next skills)
- BLOCKED — vpstack-brain binary not found or unreadable
