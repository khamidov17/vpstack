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

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion:

> "This project looks like voice-anonymization work (matched: $ACTIVATION_REASON). Enable vpstack here?"
>
> A) Yes, enable for this project (writes `<repo>/.vpstack/enabled`)
> B) No, silence vpstack on this project (writes `<repo>/.vpstack/disabled`)
> C) Ask me again next time

On answer:
- A → `mkdir -p .vpstack && touch .vpstack/enabled` and proceed
- B → `mkdir -p .vpstack && touch .vpstack/disabled` and exit silently
- C → `mkdir -p .vpstack && touch .vpstack/ask-later` and exit silently

After A, append the project hash to `~/.vpstack/projects-decided`:
```bash
PROJECT_HASH=$(printf '%s' "$PWD" | sha256sum 2>/dev/null | cut -c1-16 || printf '%s' "$PWD" | shasum -a 256 | cut -c1-16)
echo "$PROJECT_HASH" >> ~/.vpstack/projects-decided
```

## Workflow

### Step 1: Resolve slug and timestamps

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TEL_START=$(date +%s)
EXP_ID="spike-$(date +%Y%m%dT%H%M%S)"
```

### Step 2: Load hypothesis (if any)

```bash
ls ~/.vpstack/projects/$SLUG/hypotheses/ 2>/dev/null | sort -r | head -5
```

If hypothesis files are found, ask:

> "Found hypothesis: '<text>'. Use this as the basis for the spike?"
> A) Yes  B) No, free-form spike

If A, populate Given/When/Then fields from the hypothesis doc. If B, prompt for them.

### Step 3: Define variants (1-3)

Ask via AskUserQuestion:

> "How many variants to test?"
> A) 1 — quick check  B) 2 — A/B  C) 3 — three-way

For each variant, ask:
- Variant name (free-form, short)
- Data path for this variant's anonymized output OR a description of the component change to apply

**Important:** The B1 baseline recipe runs anonymization (McAdams coefficient). Each spike variant should represent a different anonymization configuration or component. Ask the user for the `--data_path` for each variant (a directory of audio to anonymize).

### Step 4: Confirm scope

Show the user the plan and confirm:

> "Will run <N> variant(s) using the B1 recipe on the dev set. Each variant takes ~5 minutes on CPU. Continue?"
> A) Yes  B) No, abort

If B: set `OUTCOME=abort` and jump to Telemetry.

### Step 5: Execute

For each variant, run the B1 recipe directly:

```bash
python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run \
  --data_path "$VARIANT_DATA_PATH" \
  --output_format json \
  --seed 42
```

Capture stdout and exit code for each variant.

- Exit 0: anonymization succeeded. Parse JSON from stdout: `{config_hash, n_files_anonymized, output_dir}`.
- Exit 2: `BASELINE_NOT_IMPLEMENTED` — anonymization ran but eval pipeline is pending. Parse the JSON error from stdout. Mark variant as `INCONCLUSIVE` with note "eval pipeline not yet implemented; anonymized audio is in output_dir".
- Exit 1: real error. Read stderr. Mark variant as `FAILED`. Continue with remaining variants.

Report progress to the user after each variant: "Variant <N>/<total>: done. Exit code: <code>."

### Step 6: Verdict per variant

For each variant, determine the verdict based on hypothesis acceptance criteria (if loaded) or default thresholds:

- **CONFIRMED:** primary metric (EER) improved by the expected magnitude AND no regressions on held-constant metrics. Note: EER higher = more private.
- **REFUTED:** primary metric did not improve or regressed.
- **INCONCLUSIVE:** result within noise band (EER delta ≤ 0.2pp), variant exited 2 (eval pipeline pending), or variant FAILED.

If the eval pipeline is not yet implemented (exit 2), all verdicts will be INCONCLUSIVE. Report this clearly: "The eval pipeline is not yet implemented — anonymization ran but EER/WER cannot be automatically scored. Check the output_dir for anonymized audio and run your own ASV eval to determine the verdict."

### Step 7: Write spike doc

Use the Write tool to create `~/.vpstack/projects/$SLUG/spikes/$EXP_ID.md`:

```markdown
# Spike: <name>

Date: <ISO 8601>
Hypothesis: <link to hypothesis doc, if any>
ID: <EXP_ID>

## Given
<setup state — what was the starting configuration>

## When
<what was changed in each variant>

## Then (results)
| Variant  | Data path | Exit code | EER  | WER | Verdict       |
|----------|-----------|-----------|------|-----|---------------|
| baseline | ...       | ...       | ...  | ... | -             |
| v1       | ...       | ...       | ...  | ... | CONFIRMED     |
| v2       | ...       | ...       | ...  | ... | REFUTED       |

## Decision
<short note: kill / iterate / ship / further-spike>
```

Also use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json`:

```json
{
  "exp_id": "<EXP_ID>",
  "skill": "vp-spike",
  "timestamp": "<ISO 8601>",
  "slug": "<SLUG>",
  "seed": 42,
  "variants": [
    {
      "name": "<variant name>",
      "data_path": "<path>",
      "exit_code": "<0|1|2>",
      "config_hash": "<from stdout or null>",
      "n_files_anonymized": "<from stdout or null>",
      "output_dir": "<from stdout or null>",
      "eer": "<value or null>",
      "wer": "<value or null>",
      "verdict": "<CONFIRMED|REFUTED|INCONCLUSIVE|FAILED>"
    }
  ]
}
```

First ensure the directory exists:
```bash
mkdir -p ~/.vpstack/projects/$SLUG/spikes
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

### Step 8: Update hypothesis doc

If a hypothesis doc was loaded, use the Edit tool to append to it:

```markdown
## Result
Status: <CONFIRMED / REFUTED / INCONCLUSIVE>
Spike: ~/.vpstack/projects/$SLUG/spikes/$EXP_ID.md
Date: <ISO 8601>
```

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-spike --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` if all variants ran and spike doc was written (regardless of verdict). `error` if the recipe exited 1 on all variants. `abort` if user cancelled at scope-confirm step.

## Completion status

- DONE — all variants completed, spike doc written, hypothesis updated
- DONE_WITH_CONCERNS — some variants exited 2 (BASELINE_NOT_IMPLEMENTED) or 1 (FAILED); verdicts are INCONCLUSIVE or FAILED for those
- BLOCKED — VP2026 data path missing for all variants, or all variants exited 1
