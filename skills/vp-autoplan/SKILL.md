---
name: vp-autoplan
version: 0.1.0-dev
description: |
  End-to-end voice-anonymization research lifecycle automation. Runs /vp-talk → /vp-hypothesis →
  /vp-plan-design-review → /vp-plan-eng-review → /vp-implement → /vp-qa → /vp-ship in sequence,
  with check-in gates between phases. Equivalent of gstack /autoplan but for voice-privacy
  research. Use when starting a new research direction and want vpstack to walk you all the
  way from "open question" to "merged PR" with quality gates at each phase. (vpstack)
  Voice triggers: "auto plan", "vp autoplan", "run the full lifecycle", "do everything",
  "automate the whole thing".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-autoplan

Runs the full vpstack research lifecycle in sequence with auto-decisions where unambiguous and check-in gates at major decision points. Saves you from typing `/vp-talk`, then `/vp-hypothesis`, then `/vp-plan-design-review`, then `/vp-plan-eng-review`, then `/vp-implement`, then `/vp-qa`, then `/vp-ship` — but with the same domain-specific quality checks as if you'd run each one manually.

This skill is the gstack `/autoplan` equivalent — but voice-privacy-shaped. Don't run on a generic dev project; it'd be silent (activation gate filters).

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-autoplan 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-autoplan 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi

TEL_START=$(date +%s)
```

## First-run gate

Same shape as `vp-baseline-compare` (Yes / No / Ask later).

## Workflow

### Step 1: Determine lifecycle scope

Ask via AskUserQuestion:

> "Where in the lifecycle does this run start?"
>
> A) **Greenfield** — no hypothesis yet, full lifecycle (~6 phases, multi-day with GPU work)
> B) **Mid-cycle** — have a hypothesis, ready to implement (skip /vp-talk, start at design review)
> C) **Implementation done** — code written, run only QA + ship (skip first 4 phases)
> D) **Pre-submission** — full eval, attacker matrix, ship to submission archive (most expensive)

Branch by answer. Each option determines which phases run.

### Step 2: Confirm gates and budget

Show the planned phases + estimated GPU time + check-in points:

```
Phase             | Skill                  | ETA      | Auto-skip if...
1. Direction      | /vp-talk               | 10 min   | locked plan exists
2. Hypothesis     | /vp-hypothesis         | 5 min    | hypothesis logged in last 24h
3. Design review  | /vp-plan-design-review | 5-10 min | no design-affecting code change
4. Eng review     | /vp-plan-eng-review    | 10 min   | no diff
5. Implementation | /vp-implement          | varies   | nothing to implement
6. QA             | /vp-qa --tier standard | 1 h      | always run
7. Ship           | /vp-ship               | 2 min    | gates failed in 6
                                            ─────
                                  Total ETA: ~1.5h + GPU work
```

Ask:

> "Confirm scope? Each phase still gates on its own check-in — autoplan doesn't skip those."
>
> A) Yes, run as planned
> B) Customize — let me skip specific phases
> C) Abort

### Step 3: Phase 1 — `/vp-talk` (skip if greenfield not selected)

If Step 1 = A (Greenfield), invoke `/vp-talk` directly. The skill writes a research-plan doc and prompts for LOCK / DRAFT / DISCARD. autoplan does NOT auto-lock — user must explicitly choose A or B.

If LOCKED → continue to Phase 2.
If DRAFT → ask "Continue with draft (riskier — direction might shift mid-cycle) or pause autoplan to revise?"
If DISCARDED → autoplan exits ABORT.

### Step 4: Phase 2 — `/vp-hypothesis` (skip if mid-cycle from Step 1B/C/D)

Invoke `/vp-hypothesis`. It will reference the locked research plan from Phase 1.

### Step 5: Phase 3 — `/vp-plan-design-review`

Invoke `/vp-plan-design-review`. Reviews recipe interface contract, attacker condition coverage, repro design, eval-set safety, license posture.

If verdict = APPROVED → continue to Phase 4.
If verdict = NEEDS_REVISION → STOP. Present findings to user. autoplan does NOT auto-fix design issues — those are research decisions.
If verdict = BLOCKED (e.g., GPLv3 contamination) → autoplan exits BLOCKED.

### Step 6: Phase 4 — `/vp-plan-eng-review`

Invoke `/vp-plan-eng-review` (which itself runs `/plan-eng-review` + 18 VP gates).

P0 fails → STOP. autoplan does NOT auto-fix P0 gates — those need user judgment.
P1 fails → ask: "P1 fails: {list}. Continue (defer fix) or pause to fix?"
All clean → continue to Phase 5.

### Step 7: Phase 5 — `/vp-implement`

Invoke `/vp-implement`. The skill enforces its own pre/during/post gates (license audit, hparams completeness, repro-check, test regression).

BLOCKED on any gate → autoplan exits BLOCKED with the specific error class. The user resolves manually then resumes by re-running `/vp-autoplan` from Phase 5.

### Step 8: Phase 6 — `/vp-qa`

Invoke `/vp-qa` with tier from Step 1:
- A/B Greenfield/Mid-cycle → `--tier standard` (~1h)
- C Implementation-done → `--tier quick` (~15min)
- D Pre-submission → `--tier pre-submission` (~12h)

If QA score < 80 → ask: "QA score {N}/100. Ship anyway, fix specific findings, or abort?"

### Step 9: Phase 7 — `/vp-ship`

Invoke `/vp-ship`. The skill enforces its own gates (tests, repro-check, attacker smoke, submission format).

BLOCKED on a gate → autoplan exits BLOCKED. Reasons preserved in `~/.vpstack/projects/{slug}/autoplan-{date}.md`.

### Step 10: Final summary

Write to `~/.vpstack/projects/{slug}/autoplan-runs/{date}.md`:

```markdown
# Autoplan run: {date}

| Phase | Skill                  | Outcome | Duration | Notes |
|-------|------------------------|---------|----------|-------|
| 1     | /vp-talk               | DONE    | 12m      | locked plan {id} |
| 2     | /vp-hypothesis         | DONE    | 4m       | hypothesis {id} |
| 3     | /vp-plan-design-review | DONE    | 7m       | 0 P0, 1 P1 deferred |
| 4     | /vp-plan-eng-review    | DONE    | 9m       | 0 P0, 0 P1 |
| 5     | /vp-implement          | DONE    | varies   | repro-check PASS |
| 6     | /vp-qa --tier standard | DONE    | 58m      | score 87/100 |
| 7     | /vp-ship               | DONE    | 90s      | PR: <url> |

Total: {duration}
Final state: SHIPPED / BLOCKED at phase {N}
```

## Check-in gate principle

autoplan never silently skips a skill's check-in. Each phase runs its own AskUserQuestion gates as if invoked manually. This means autoplan is interactive — it'll prompt the user mid-run multiple times. That's intentional: research correctness > drive-by automation.

For fully-headless autoplan (CI / overnight): set `VPSTACK_HEADLESS=1` and individual skills will auto-pick the recommended option at each gate. Use cautiously — headless autoplan can run for hours and ship something the user wouldn't have approved interactively.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-autoplan \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

## Completion status

- DONE — all selected phases ran cleanly, ship completed
- DONE_WITH_CONCERNS — completed but with P1 issues the user accepted along the way
- BLOCKED — phase {N} hit a P0 / blocked state. Resume by re-running `/vp-autoplan` after manual fix.
- ABORT — user discarded research plan in Phase 1 or aborted at a gate.

## Why this skill exists

Voice-privacy research has a fixed pipeline: research direction → hypothesis → design → engineering review → implementation → QA → ship. Researchers know this; they just have to remember to invoke each phase manually, and they skip phases when in a rush. autoplan ensures every phase happens (or is explicitly skipped with a reason). This is exactly the gstack `/autoplan` value proposition, applied to a different lifecycle.
