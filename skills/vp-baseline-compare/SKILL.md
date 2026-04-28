---
name: vp-baseline-compare
version: 0.1.0-dev
description: |
  Run B1 (McAdams) + B2 (neural) baselines on the same eval set as the user's anonymization system,
  return a delta table (EER / WER / linkability). Use when the user asks "how does my system compare
  to baseline?" or "is this better than B1?" or wants a quick sanity check of their anonymizer against
  canonical references. (vpstack)
  Voice triggers: "baseline compare", "vs B1", "vs B2".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-baseline-compare

Run the canonical VP2026 baselines and the user's system on the same eval set; return a structured comparison. This is the most-used skill — researchers run it after every meaningful system change to know if they're improving against the canonical references.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

# Activation gate
case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT)
    exit 0
    ;;
  DETECTED_FIRST_RUN)
    # Skill body handles the AskUserQuestion below
    ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED)
    # Proceed normally
    ;;
esac

# Surface upgrade if available — do not block
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
- C → `mkdir -p .vpstack && touch .vpstack/ask-later` and exit silently. Marker is valid for 60 minutes — vpstack-detect treats it as `DETECTED_CONFIRMED` during that window, preventing re-prompt loops in a multi-skill session. After 60min, the prompt fires again.

After A, also append the project hash to `~/.vpstack/projects-decided` so future runs skip the prompt:
```bash
PROJECT_HASH=$(printf '%s' "$PWD" | sha256sum 2>/dev/null | cut -c1-16 || printf '%s' "$PWD" | shasum -a 256 | cut -c1-16)
echo "$PROJECT_HASH" >> ~/.vpstack/projects-decided
```

## Workflow

### Step 1: Resolve the slug and timestamps

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TEL_START=$(date +%s)
EXP_ID="baseline-compare-$(date +%Y%m%dT%H%M%S)"
```

### Step 2: Locate the user's system

Ask via AskUserQuestion:

> "Which anonymization system should I compare against B1 and B2?"
>
> A) Path to a directory with my anonymized audio (already-run system)
> B) Just run B1 — no user system comparison, I want canonical numbers

If A: ask for the path. Validate it exists and contains `.wav` files with:
```bash
ls "$USER_PATH"/*.wav 2>/dev/null | head -5
```
If no `.wav` files are found, report the error and stop.

If B: skip Step 3.

### Step 3: Collect user system metrics (if applicable)

If the user provided a pre-anonymized audio directory, note it for the comparison table. vpstack does not run a separate eval pipeline for arbitrary user systems in this version — the user should provide EER/WER values directly, or run their own eval script first.

Ask via AskUserQuestion:

> "Do you have EER and WER values for your system already, or should I just show the baseline numbers?"
>
> A) I have values — I'll paste them  B) Just show the baseline numbers

If A: ask the user to provide EER (%) and WER (%) for their system. Record them as `user_eer` and `user_wer`.

### Step 4: Run B1 baseline

Inform the user: "Running B1 (McAdams) baseline. This takes ~5 minutes on CPU. B2 is not yet implemented in this version of vpstack — see note below."

```bash
python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run \
  --data_path "$DATA_PATH" \
  --output_format json \
  --seed 42
```

- Exit 0: anonymization succeeded. Parse stdout JSON: `{config_hash, n_files_anonymized, output_dir}`.
- Exit 2: `BASELINE_NOT_IMPLEMENTED` — the anonymization ran but the eval pipeline is not yet implemented. Parse the JSON error from stdout, note this to the user, and continue. Record `b1_eer` and `b1_wer` as `"pending"`.
- Exit 1: real error — read stderr, report to user, set `OUTCOME=error`, and stop.

**B2 note:** B2 (neural: HuBERT + ECAPA-TDNN + HiFi-GAN) is not yet implemented. Running it will always exit 2 with `BASELINE_NOT_IMPLEMENTED`. Do not attempt to run B2 in this skill unless the user explicitly requests it as a smoke test. If asked, run:

```bash
python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B2.run \
  --data_path "$DATA_PATH" \
  --output_format json \
  --seed 42
```

Then report exit 2 to the user clearly: "B2 is not yet implemented — exits with BASELINE_NOT_IMPLEMENTED. Skipping B2 column."

### Step 5: Build the delta table

Construct the comparison table from available data. Use `"—"` for any metric that could not be obtained.

```
                        B1            B2            Yours
EER % (↑ = private)    [b1_eer]      not impl.     [user_eer or —]
WER % (↓ = useful)     [b1_wer]      not impl.     [user_wer or —]
Linkability (↓)         [b1_link]     not impl.     [user_link or —]

Δ vs B1:  EER [delta_eer]  WER [delta_wer]
```

Metric direction reminders (always show to user):
- EER: **higher = more private**. Random-chance ceiling is 50%. A perfect anonymizer would approach 50%.
- WER: **lower = more useful**. 0% = perfect transcription.
- Linkability: **lower = harder to link back to original speaker**.

Color guidance (if terminal supports ANSI):
- Green: user's system improves over B1 on the primary metric (EER)
- Yellow: mixed result (EER up but WER also up significantly)
- Red: regression vs B1

### Step 6: Log experiment

Use the Write tool to create the experiment summary. First ensure the directory exists:

```bash
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Then use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json` with contents:

```json
{
  "exp_id": "<EXP_ID>",
  "skill": "vp-baseline-compare",
  "timestamp": "<ISO 8601 timestamp>",
  "slug": "<SLUG>",
  "seed": 42,
  "b1": {
    "config_hash": "<from B1 stdout or null>",
    "n_files_anonymized": "<from B1 stdout or null>",
    "output_dir": "<from B1 stdout or null>",
    "eer": "<b1_eer or null>",
    "wer": "<b1_wer or null>"
  },
  "b2": null,
  "user_system": {
    "eer": "<user_eer or null>",
    "wer": "<user_wer or null>"
  },
  "notes": "<any BASELINE_NOT_IMPLEMENTED notices>"
}
```

### Step 7: Suggest next steps

Based on results:

- If the user's system EER is higher than B1 EER: "Your system shows stronger privacy than B1. Consider running `/vp-eval` when the full eval pipeline is implemented to validate on the held-out test set."
- If the user's system EER is lower than B1 EER: "Your system shows weaker privacy than B1. Try `/vp-spike` to ablate components and find what's hurting privacy."
- If B1 exited with `BASELINE_NOT_IMPLEMENTED` (exit 2): "B1 anonymization ran successfully but the EER/WER scoring pipeline is not yet implemented. Check `output_dir` for anonymized audio. Run your own ASV eval against it."
- If no user system was provided: "No user system compared. Try `/vp-hypothesis` to formalize your first ablation idea."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-baseline-compare \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

Where `OUTCOME` is one of: `success`, `error`, `abort`. On `error`, include `--error-class` (allowlist: `GPU_OOM`, `DATA_MISSING`, `INVALID_CONFIG`, `TIMEOUT`).

## Completion status

- DONE — table produced, experiment logged
- DONE_WITH_CONCERNS — B1 exited 2 (BASELINE_NOT_IMPLEMENTED); anonymization ran but no EER/WER scored
- BLOCKED — VP2026 data path missing or B1 recipe exited 1 (real error)

## Notes for skill authors

This is the canonical vpstack skill — every other skill follows the same shape:
1. Preamble with `vpstack-skill-init` (handles activation, version check, telemetry start)
2. Activation gate (exit silently on NO_MATCH / DISABLED)
3. First-run gate (AskUserQuestion if DETECTED_FIRST_RUN)
4. Workflow body (runs bash commands directly, uses Write tool for state)
5. Telemetry end (`vpstack-telemetry-log`)

Skills MUST NOT bypass the preamble — that's the privacy and silent-on-non-voice contract.
