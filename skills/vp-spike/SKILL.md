---
name: vp-spike
version: 0.1.0-dev
description: |
  Run 1-3 focused ablation experiments with given/when/then verdicts. Use when testing a specific
  hypothesis (paired with /vp-hypothesis) or comparing 2-3 component swaps quickly. Returns a verdict
  per spike (CONFIRMED / REFUTED / INCONCLUSIVE) with the metric deltas. Writes to
  ~/.vpstack/projects/{slug}/spikes/{id}.md. (vpstack)
  Voice triggers: "ablate", "spike", "try variants".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# /vp-spike

Time-boxed ablation runner. Researcher specifies 1-3 component variants; vpstack runs each on the same eval set and returns a verdict with concrete deltas. Replaces ad-hoc "I'll just try a few things" experiments with a structured trace.

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

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as in `vp-baseline-compare`. On Yes: write `.vpstack/enabled` and append project hash to `~/.vpstack/projects-decided`. On No: write `.vpstack/disabled`, exit silently. On Ask later: exit silently.

## Workflow

### Step 1: Load hypothesis (if any)

Check `~/.vpstack/projects/$SLUG/hypotheses/` for recent docs. If found, ask:

> "Found hypothesis: '<text>'. Use this as the basis for the spike?"
> A) Yes  B) No, free-form spike

If A, populate Given/When/Then fields from the hypothesis doc. If B, prompt for them.

### Step 2: Define variants (1-3)

Ask via AskUserQuestion:

> "How many variants to test?"
> A) 1 — quick check  B) 2 — A/B  C) 3 — three-way

For each variant, ask:
- Variant name (free-form, short)
- Config path OR component override (e.g., `content_encoder.layer_idx=6`)

### Step 3: Confirm scope

> "Will run <N> variants on dev set. Estimated GPU time: <N × 45 min>. Continue?"
> A) Yes  B) No, abort

### Step 4: Execute

For each variant, call `vp_run_eval`:

```python
results = []
for v in variants:
    r = mcp_client.call("vp_run_eval", {
        "system_path": v.config_path,
        "eval_set": "dev",
        "seed": 42,
    })
    results.append((v, r))
```

Stream progress to stderr per variant ("Variant 1/3: epoch 12/40, ETA 38m").

If any variant fails (`r.ok == False`), continue with the rest, mark that variant FAILED in output.

### Step 5: Verdict per variant

For each variant, decide based on hypothesis acceptance criteria (or absent that, default thresholds):

- **CONFIRMED:** primary metric improved by ≥ expected magnitude AND no regressions on held-constant metrics
- **REFUTED:** primary metric did not improve OR regressed
- **INCONCLUSIVE:** result within noise band (≤0.2pp on EER) OR variant failed

### Step 6: Write spike doc

```markdown
# Spike: <name>

Date: <ISO 8601>
Hypothesis: <link to hypothesis doc, if any>
ID: <exp_id>

## Given
<setup state>

## When
<what was changed in each variant>

## Then (results)
| Variant | EER  | WER | Linkability | Verdict     |
|---------|------|-----|-------------|-------------|
| baseline| ...  | ... | ...         | -           |
| v1      | ...  | ... | ...         | CONFIRMED   |
| v2      | ...  | ... | ...         | REFUTED     |

## Decision
<short note: kill / iterate / ship / further-spike>
```

Write to `~/.vpstack/projects/$SLUG/spikes/$EXP_ID.md`. Call `vp_log_experiment` for each variant.

### Step 7: Update hypothesis doc

If a hypothesis doc was loaded, append:
```markdown
## Result
Status: <CONFIRMED / REFUTED / INCONCLUSIVE>
Spike: <link to spike doc>
```

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-spike --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` if all variants ran (regardless of verdict). `error` if MCP unreachable or recipe broken. `abort` if user cancelled at scope-confirm step.

## Completion status

- DONE — all variants completed, spike doc written, hypothesis updated
- DONE_WITH_CONCERNS — some variants failed (FAILED in verdict table)
- BLOCKED — MCP server unreachable or VP2026 data missing
