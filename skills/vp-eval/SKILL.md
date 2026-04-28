---
name: vp-eval
version: 0.1.0-dev
description: |
  Run the full VP2026 evaluation pipeline (EER + WER + linkability + side-channel scores) on the
  user's anonymization system. Validates submission format. Use when preparing a challenge submission
  or generating publication-grade numbers. Distinct from /vp-baseline-compare — this is the full eval,
  not a comparison. (vpstack)
  Voice triggers: "full eval", "evaluate", "score my system", "VP2026 eval".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-eval

Run the VP2026 eval pipeline end-to-end and validate submission format.

**Current implementation status:** The full eval pipeline (EER scoring, WER scoring, linkability, side-channel metrics) is not yet implemented in vpstack. What IS available and runnable right now:

- B1 baseline anonymization (`baseline_B1.run`) — exits 0 on success
- B2 baseline anonymization (`baseline_B2.run`) — always exits 2 (not yet implemented)
- Attacker runner (`attacker.run`) — for ASV-based EER estimation

This skill runs what is available, is honest about what is not, and gives the user a manual checklist for submission validation.

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
EXP_ID="eval-$(date +%Y%m%dT%H%M%S)"
```

### Step 2: Locate the system and data

Ask via AskUserQuestion:

> "What do you want to evaluate?"
>
> A) Run B1 anonymization on a data directory (and then run the attacker on the output)
> B) I already have anonymized audio — run the attacker on it directly
> C) Just validate my submission directory format (no runs)

Ask for the relevant path depending on the answer.

**Test-split protection warning.** If the user's data path contains the word `test`, `eval`, or `heldout` (case-insensitive), warn explicitly:

> "WARNING: The path you provided appears to be the held-out test split. Running eval on test data before your official submission can lead to overfitting your system to the test set, which undermines the challenge integrity. Are you preparing your official submission?"
>
> A) Yes, this is my official submission run  B) No, switch to dev set

If the user answers B, ask for the dev set path instead. If A, proceed but include `"official_run": true` in the experiment log.

### Step 3: Run B1 anonymization (if applicable)

If the user chose option A in Step 2, run:

```bash
python3 /tmp/vp_b1_run.py \
  --data_path "$DATA_PATH" \
  --output_format json \
  --seed 42
```

- Exit 0: parse stdout JSON. The `output_dir` field is the anonymized audio path to pass to the attacker.
- Exit 2: `BASELINE_NOT_IMPLEMENTED` — anonymization ran but eval pipeline is pending. Parse `output_dir` from the JSON error payload (it is still populated). Continue to the attacker with that path. Note this to the user.
- Exit 1: real error. Read stderr, report to user. Set `OUTCOME=error` and stop.

### Step 4: Run the attacker

Run the attacker against the anonymized audio. Inform the user: "Running the semi-informed ASV attacker. This can take 30-90 minutes on a single GPU."

```bash
# see /vp-attack skill for attacker command \
  --anonymized_path "$ANONYMIZED_PATH" \
  --enrollment_path "$ENROLLMENT_PATH" \
  --trial_list "$TRIAL_LIST" \
  --attacker_condition semi_informed \
  --output_format json \
  --seed 42
```

Before running, ask the user for:
- `--enrollment_path`: path to enrollment audio (original speaker samples used by the attacker)
- `--trial_list`: path to the VP2026 trial list file

Parse stdout JSON on success. Key fields: `eer`, `eer_male`, `eer_female`, `attacker_condition`.

Metric reminder: **EER higher = more private.** A random-chance attacker scores ~50% EER. The goal is to approach 50%.

If the attacker exits non-zero, report stderr to the user. Set `OUTCOME=error`.

### Step 5: Submission format checklist (bash)

Run this checklist manually regardless of which option the user chose. This replaces the former `vp_check_submission` MCP tool.

```bash
SUBMISSION_DIR="$OUTPUT_DIR"  # or the user's provided path

echo "=== VP2026 Submission Format Checklist ==="

# 1. Check required top-level structure
for required in trial_results system_description.json; do
  if [ -e "$SUBMISSION_DIR/$required" ]; then
    echo "  [OK]  $required exists"
  else
    echo "  [MISSING]  $required — required for submission"
  fi
done

# 2. Check EER result file
EER_FILE="$SUBMISSION_DIR/trial_results/dev/eer.json"
if [ -f "$EER_FILE" ]; then
  echo "  [OK]  eer.json exists"
  # Validate expected keys
  python3 -c "
import json, sys
with open('$EER_FILE') as f:
    d = json.load(f)
required = {'male', 'female', 'overall'}
missing = required - set(d.keys())
if missing:
    print('  [ERROR]  eer.json missing keys:', missing)
else:
    print('  [OK]  eer.json has required keys: male, female, overall')
    print('         Values:', d)
" 2>&1
else
  echo "  [MISSING]  trial_results/dev/eer.json"
fi

# 3. Check system description
SYS_DESC="$SUBMISSION_DIR/system_description.json"
if [ -f "$SYS_DESC" ]; then
  echo "  [OK]  system_description.json exists"
else
  echo "  [MISSING]  system_description.json — describe your system components here"
fi

# 4. Check for any audio left in submission (should be scores only)
WAV_COUNT=$(find "$SUBMISSION_DIR" -name '*.wav' 2>/dev/null | wc -l)
if [ "$WAV_COUNT" -gt 0 ]; then
  echo "  [WARN]  Found $WAV_COUNT .wav files in submission dir — submissions should contain scores, not audio"
else
  echo "  [OK]  No audio files in submission (correct)"
fi

echo "=== End of checklist ==="
```

Report the checklist output to the user. For each `[MISSING]` or `[ERROR]` item, explain what is needed and how to fix it.

### Step 6: Present results

```
VP2026 Evaluation Results
=========================
Eval set:       <dev|test>
Seed:           42
System:         <path>
EXP ID:         <EXP_ID>

Attacker condition: semi-informed (official ranking condition)

| Metric              | Value        |
|---------------------|--------------|
| EER % (overall)     | <eer or N/A> |
| EER % (male)        | <or N/A>     |
| EER % (female)      | <or N/A>     |
| WER %               | not yet impl.|
| Linkability         | not yet impl.|

Note: EER higher = more private. Random-chance ceiling = 50%.
Note: WER and linkability scoring are not yet implemented in vpstack.
      Run your own ASR eval to compute WER.

Submission validation: <PASS|FAIL|PARTIAL — list issues>
Output directory: ~/.vpstack/projects/<slug>/experiments/<EXP_ID>/
```

### Step 7: Log experiment

First ensure the directory exists:
```bash
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json`:

```json
{
  "exp_id": "<EXP_ID>",
  "skill": "vp-eval",
  "timestamp": "<ISO 8601>",
  "slug": "<SLUG>",
  "seed": 42,
  "eval_set": "<dev|test>",
  "official_run": false,
  "b1": {
    "exit_code": "<0|1|2>",
    "config_hash": "<or null>",
    "n_files_anonymized": "<or null>",
    "output_dir": "<or null>"
  },
  "attacker": {
    "exit_code": "<or null if not run>",
    "attacker_condition": "semi_informed",
    "eer": "<or null>",
    "eer_male": "<or null>",
    "eer_female": "<or null>"
  },
  "submission_validation": "<PASS|FAIL|PARTIAL>",
  "submission_issues": []
}
```

### Step 8: Suggest next steps

- If EER from attacker is available and high (approaching 50%): "Strong privacy result. If submission validation passed, bundle `output_dir` as your official submission archive."
- If EER is low (much below 50%): "Privacy is weaker than expected. Try `/vp-spike` to ablate components."
- If submission validation failed: "Fix the listed issues and re-run Step 5 manually, or re-run `/vp-eval`."
- If WER is needed: "WER scoring is not yet in vpstack. Run a standard ASR eval (e.g., `whisper` or `kaldi`) on the anonymized audio in `output_dir`."
- If running on dev: "When ready for official submission, re-run `/vp-eval` on the test set and confirm the official-run prompt."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-eval --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` on full run completing (even with BASELINE_NOT_IMPLEMENTED notes). `error` with `--error-class DATA_MISSING` if required paths are absent. `error` with `--error-class INVALID_CONFIG` on attacker misconfiguration. `abort` if user cancelled at the test-split warning.

## Completion status

- DONE — B1 ran, attacker ran, results logged, submission checklist passed
- DONE_WITH_CONCERNS — eval ran but submission checklist found issues (listed), or B1 exited 2 (eval pipeline pending)
- BLOCKED — required data paths missing, B1 exited 1, or attacker exited non-zero
