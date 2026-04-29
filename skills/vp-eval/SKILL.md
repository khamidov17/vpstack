---
name: vp-eval
version: 0.3.0-dev
description: |
  Run the full VP2026 evaluation pipeline on an anonymized output: EER per
  gender split (F-F / M-M / Mixed) via vpstack-score, WER via vpstack-wer
  (Whisper), naturalness PMOS via vpstack-utmos, and emit the official VP2026
  submission CSV layout under exp/asv_anon{suffix}/, exp/asr/, exp/ser/,
  exp/results_summary/track1/. Use when preparing a challenge submission or
  generating publication-grade numbers. Distinct from /vp-baseline-compare —
  this is the full eval, not a comparison. (vpstack)
  Voice triggers: "full eval", "evaluate", "score my system", "VP2026 eval",
  "submission scorecard".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-eval

Run the VP2026 eval pipeline end-to-end via the `vpstack-eval` orchestrator. Produces VP2026-format submission CSVs (per Eval Plan v1, HAL hal-05561895, Tables 8-9).

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-eval 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-eval 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

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
EXP_ID="eval-$(date +%Y%m%dT%H%M%S)"
VPSTACK_BIN=~/.claude/skills/vpstack/bin
[ -d "$VPSTACK_BIN" ] || VPSTACK_BIN=.claude/skills/vpstack/bin
```

## First-run gate

If `ACTIVATION=DETECTED_FIRST_RUN`, ask once (Yes / No / Ask later) — same shape as `vp-baseline-compare`.

## Workflow

### Step 1: Locate the system and data

Ask via AskUserQuestion:

> **What do you want to evaluate?**
>
> A) Run B1 anonymization first, then full eval on the output (start-to-finish)
> B) Eval a directory of already-anonymized audio
> C) Re-emit the submission CSV/ZIP from a prior eval run (no re-scoring)
>
> Recommendation: B if you've already anonymized; A if you're benchmarking against B1; C only if you've already done the heavy lifting and just need the submission archive regenerated.

Collect paths:

- `$ANONYMIZED_PATH` — directory of anonymized 16kHz mono WAVs (auto-derived from B1 output_dir if option A)
- `$ENROLLMENT_PATH` — original-speaker enrollment WAVs (required for ASV/EER scoring)
- `$TRIAL_LIST_FF`, `$TRIAL_LIST_MM`, `$TRIAL_LIST_MIXED` — VP2026 trial files (any subset; eval only what's provided)
- `$REFERENCE_TEXT` — TSV manifest `filename<TAB>transcription` for WER (optional)
- `$OUTPUT_DIR` — where the VP2026 submission tree gets written (default: `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/`)
- `$SYSTEM_SUFFIX` — appears in CSV/ZIP names, e.g. `_ohnn-v3` (default: `_yoursystem`)

**Test-split protection.** If any path contains `test`, `eval`, or `heldout` (case-insensitive), warn:

> **WARNING:** Path contains "test/eval/heldout" — running eval on the held-out test split before official submission risks overfitting your system to the test set. Are you preparing your official submission?
>
> A) Yes — official submission run  B) No — switch to dev set
>
> Recommendation: B unless you're literally about to upload. Tag the experiment with `official_run: true` only if A.

### Step 2: Run B1 first if option A

```bash
~/.claude/skills/vpstack/bin/vpstack-b1 \
  --data_path "$DATA_PATH" \
  --output_format json \
  --seed 42
```

Parse stdout JSON; set `$ANONYMIZED_PATH=$(jq -r .output_dir <<<"$B1_OUT")`.

### Step 2.5: Dependency check (run BEFORE the orchestrator)

`vpstack-eval` calls three downstream binaries with separate Python deps. Probe each one based on what the user actually wants to run, so the user only has to install what's needed:

```bash
DEPS_BIN=~/.claude/skills/vpstack/bin/vpstack-deps
[ -x "$DEPS_BIN" ] || DEPS_BIN=.claude/skills/vpstack/bin/vpstack-deps

# Build the list of features required for THIS run
NEEDED=()
[ -n "${TRIAL_LIST_FF:-}" ] || [ -n "${TRIAL_LIST_MM:-}" ] || [ -n "${TRIAL_LIST_MIXED:-}" ] && NEEDED+=("score")
[ -n "${REFERENCE_TEXT:-}" ] && NEEDED+=("wer")
NEEDED+=("utmos")   # always run — UTMOS is automatic in vpstack-eval

# Find missing
MISSING=()
for feat in "${NEEDED[@]}"; do
  $DEPS_BIN check "$feat" >/dev/null 2>&1 || MISSING+=("$feat")
done
```

If `MISSING` is non-empty, list them with their pip packages and ask via AskUserQuestion **before** any pip mutation:

> **The full eval needs Python packages that aren't installed yet.** Per missing component:
>
> - `score` (ASV / EER): `<vpstack-deps packages score>`
> - `wer` (Whisper / WER): `<vpstack-deps packages wer>`
> - `utmos` (UTMOS / PMOS): `<vpstack-deps packages utmos>`
>
> A) Install all missing now (`pip install --user` per component, sandboxed to `~/.local`)
> B) Install only score+wer; skip utmos (naturalness column will be blank)
> C) I'll install manually — pause this skill
> D) Run partial eval: skip the components that need missing packages
>
> Recommendation: A for a real eval. D for a quick smoke run when you only need one metric.

On A: loop `$DEPS_BIN install <feat>` for each item in `MISSING`. Stop at first failure.
On B: install only `score` and `wer`. UTMOS will be reported as `skipped` by the orchestrator, which already handles this gracefully.
On C: print the per-feature pip commands and stop with "Re-run /vp-eval after installing."
On D: drop the relevant inputs (e.g. unset `REFERENCE_TEXT` if `wer` is missing) so the orchestrator skips that component cleanly. Continue.

### Step 3: Run the full eval

```bash
mkdir -p "$OUTPUT_DIR"
$VPSTACK_BIN/vpstack-eval \
  --anonymized_path "$ANONYMIZED_PATH" \
  --output_dir      "$OUTPUT_DIR" \
  ${ENROLLMENT_PATH:+--enrollment_path "$ENROLLMENT_PATH"} \
  ${TRIAL_LIST_FF:+--trial_list_FF "$TRIAL_LIST_FF"} \
  ${TRIAL_LIST_MM:+--trial_list_MM "$TRIAL_LIST_MM"} \
  ${TRIAL_LIST_MIXED:+--trial_list_Mixed "$TRIAL_LIST_MIXED"} \
  ${REFERENCE_TEXT:+--reference_text "$REFERENCE_TEXT"} \
  --condition semi_informed \
  --asv_backend speechbrain \
  --whisper_model base.en \
  --system_suffix "$SYSTEM_SUFFIX" \
  --seed 42 \
  --output_format json
```

Inform the user: "Full VP2026 eval — semi-informed ASV is the official ranking attacker. Expect 30-90 min on a single GPU for ASV + 10-30 min for WER + 5 min for UTMOS, depending on n_files and model size."

The orchestrator runs only the components for which inputs were provided. Components that fail (e.g. missing whisper deps) are reported as `skipped` and the rest continue.

Parse the resulting JSON. Extract:
- `metrics.eer_F_F`, `metrics.eer_M_M`, `metrics.eer_Mixed`
- `metrics.wer_overall`
- `metrics.pmos_mean`
- `components_ran` map
- `submission_summary_csv` path
- `submission_zip` path (if `--make_zip` was used; offer in Step 4)

### Step 4: Offer the submission ZIP

If the user wants the bundled submission archive:

> **Bundle the eval into a submission ZIP?**
>
> A) Yes — re-run vpstack-eval with `--make_zip` to produce `result_for_submission${SYSTEM_SUFFIX}.zip`
> B) No, the CSVs are enough for now
>
> Recommendation: A if you're at the official-submission stage; B during iteration.

### Step 5: Present results

```
VP2026 Eval — system$SYSTEM_SUFFIX (condition=semi_informed, seed=42)
================================================================
EER F-F:    <value>%   (↑ = more private, 50% = random)
EER M-M:    <value>%
EER Mixed:  <value>%
WER:        <value>%   (↓ = more useful, 0% = perfect)
PMOS:       <value>    (↑ = more natural, 1=bad / 5=excellent)

Components ran: <list of true>
Components skipped: <list of false> [reason]

CSVs:
  $OUTPUT_DIR/exp/asv_anon$SYSTEM_SUFFIX/eer_*.csv
  $OUTPUT_DIR/exp/asr/wer.csv
  $OUTPUT_DIR/exp/ser/utmos.csv
  $OUTPUT_DIR/exp/results_summary/track1/result_for_submission$SYSTEM_SUFFIX.csv
Submission ZIP (if made): result_for_submission$SYSTEM_SUFFIX.zip
```

### Step 6: Log experiment

```bash
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json`:

```json
{
  "id": "<EXP_ID>",
  "skill": "vp-eval",
  "date": "<ISO 8601>",
  "slug": "<SLUG>",
  "method": "<system_suffix or method label>",
  "system_name": "<system_suffix>",
  "hypothesis": "<from /vp-hypothesis if present, else null>",
  "tags": ["eval", "<official_run if true>"],
  "config_hash": "<from vpstack-eval JSON>",
  "official_run": false,
  "metrics": {
    "eer": "<eer_Mixed or eer_F_F if Mixed missing>",
    "eer_F_F": "<value or null>",
    "eer_M_M": "<value or null>",
    "eer_Mixed": "<value or null>",
    "wer": "<wer_overall or null>",
    "pmos": "<pmos_mean or null>"
  },
  "condition": "semi_informed",
  "submission_dir": "<OUTPUT_DIR>",
  "submission_summary_csv": "<path>",
  "submission_zip": "<path or null>",
  "components_ran": {"asv_F-F": true, "asv_M-M": true, "asv_Mixed": true, "wer": true, "utmos": true}
}
```

This makes the run discoverable via `vpstack-brain top --metric eer` and `vpstack-brain show <EXP_ID>`.

If a confirmed result is worth remembering across sessions (e.g. "with OHNN, semi-informed EER hits 41% on F-F at lambda=0.7"), also log a learning:

```bash
~/.claude/skills/vpstack/bin/vpstack-learnings-log \
  --key "<short-kebab-key>" \
  --insight "<one-sentence finding>" \
  --source vp-eval --confidence 0.85
```

### Step 7: Suggest next steps

- High EER, low WER regression: "Strong full-eval result. Run `/vp-repro-check` before citing or submitting."
- ASV ran but WER didn't (no `--reference_text`): "Provide a TSV manifest of ground-truth transcriptions and re-run to populate the WER column."
- Test-split run: "If you tagged this as official_run, this is your submission archive. If not, regenerate with `--system_suffix _final` on dev only."
- Mixed-condition gap (Mixed EER << F-F or M-M): "Cross-gender attacks are landing harder than same-gender — investigate via `/vp-investigate`."
- If the user wants to compare against B1: "Run `/vp-baseline-compare` to get a side-by-side delta table."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-eval --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` on the orchestrator returning ok=true (even if some components were skipped due to missing inputs). `error` with `--error-class DATA_MISSING` if required paths absent. `error` with `--error-class INVALID_CONFIG` if attacker condition or backend invalid. `abort` if user cancelled at the test-split warning.

## Completion status

- DONE — vpstack-eval ran, all requested components produced metrics, CSVs and (optional) ZIP written, experiment logged to vpbrain
- DONE_WITH_CONCERNS — vpstack-eval ran but one or more components were skipped (DEPS_MISSING for whisper/speechmos, or no input provided)
- BLOCKED — anonymized_path missing, every component failed, or test-split warning declined
