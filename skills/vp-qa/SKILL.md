---
name: vp-qa
version: 0.1.0-dev
description: |
  Voice-privacy QA pass on a project before commit / submission / handoff. Orchestrates
  vpstack's existing checks: /vp-repro-check, a fast /vp-attack lazy_informed smoke run,
  vp_check_submission validation, and pytest of any project-level tests. Distinct from
  generic gstack /qa (which is web-app QA — vpstack has no web UI). Use before /vp-ship,
  before sending to a labmate, or any time you want a "is this work shippable" check.
  (vpstack)
  Voice triggers: "qa my voice work", "is this shippable", "vp qa", "ready for submission",
  "smoke test my anonymization".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-qa

Voice-privacy quality assurance: a fast pass that runs reproducibility checks, a smoke-test attacker run, submission-format validation, and any project-level tests. Catches regressions before they hit a commit, a labmate's inbox, or worse — a published paper.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as `vp-baseline-compare`.

## Workflow

### Step 1: Determine QA tier

Ask via AskUserQuestion:

> "How thorough? (Total ~time, single-GPU)"
>
> A) **Quick (~15 min):** repro-check + lazy-informed attacker on dev + submission-format check + project pytest
> B) **Standard (~1h):** Quick + B1/B2 baseline compare on dev to catch regressions
> C) **Pre-submission (~12h):** Standard + full /vp-eval --official + semi_informed attacker

Default: A. Recommend B before sending to a labmate. Recommend C only when actually preparing a VP2026 submission.

### Step 2: Locate the system to QA

Ask for the path to anonymized output (or a SpeechBrain-style config). Validate it exists and contains `.wav` files.

### Step 3: Run the QA suite

Execute in order. **Stop on first P0 failure** and surface it (the user wants to fix the most-broken thing first).

#### 3a. Project pytest (if test suite exists)

```bash
if [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests/ ]; then
  pytest -q --tb=short -m "not gpu" 2>&1 | tail -10
fi
```

If exit non-zero → **P0 BLOCKER**, stop here. Tests must pass before any other QA matters.

#### 3b. Reproducibility check

Call `/vp-repro-check` on the system's config. PASS / FAIL with reasons.

If FAIL → **P0**, surface and stop. Non-reproducible work shouldn't be QA'd further.

#### 3c. Submission format validation (if applicable)

If the user passed an `exp/` directory (suggesting a submission tree), validate it with bash:

```bash
# VP2026 submission directory structure check
ls "$exp_dir"/eer.json 2>/dev/null || echo "MISSING: eer.json"
ls "$exp_dir"/wer.json 2>/dev/null || echo "MISSING: wer.json"
ls "$exp_dir"/anonymized/ 2>/dev/null || echo "MISSING: anonymized/ directory"
python3 -c "import json; d=json.load(open('$exp_dir/eer.json')); assert 'overall' in d, 'MISSING: eer.json[overall]'" 2>&1
find "$exp_dir" -name "*.wav" -maxdepth 4 | wc -l
```

If any MISSING lines appear → **P1** unless user said "pre-submission" (Tier C), in which case **P0**.

#### 3d. Lazy-informed attacker smoke (Tier A+)

Always run this even in Quick mode — it's the fastest privacy sanity check.

```bash
python3 -m speechbrain.pretrained # or use the official VP2026 attacker script — see /vp-attack for the full command \
  --anonymized_path "$ANONYMIZED_PATH" \
  --enrollment_path "$ENROLLMENT_PATH" \
  --trial_list "$TRIAL_LIST" \
  --attacker_condition lazy_informed \
  --output_format json \
  --seed 42
```

Compare `eer_overall` against:
- B1 baseline (~14% — sanity floor)
- B2 baseline (~28% — the bar to beat)
- Random chance (50%)

Verdicts:
- `eer < B1` → **P0**: regression on privacy. Anonymization is making things worse than B1.
- `eer < B2` → **P1**: didn't beat the strong baseline. May be acceptable if utility gained.
- `eer ≥ B2` → PASS

#### 3e. Baseline compare (Tier B+)

Call `/vp-baseline-compare` to get the full delta table. Surface any cell where the user's system regresses vs B2 (highlight in red).

#### 3f. Full eval (Tier C only)

Call `/vp-eval --official` for the complete scorecard including all attacker conditions. ~12h on single GPU.

### Step 4: Compute QA score

Aggregate findings into a 0-100 score:

| Category | Weight | What deducts |
|---|---|---|
| Tests | 25% | Failing test → 0; warnings → 80 |
| Reproducibility | 25% | Each repro-check FAIL → -10 |
| Privacy (attacker EER) | 25% | EER below B1 → 0; below B2 → 50; above B2 → 100 |
| Submission format | 15% | Each MALFORMED_SUBMISSION error → -10 |
| Utility (WER) | 10% | WER worse than B2 by >0.5pp → -50 |

### Step 5: Write QA report

Write to `~/.vpstack/projects/{slug}/qa-reports/qa-{date}.md`:

```markdown
# QA Report
Date: {ISO 8601}
Tier: Quick / Standard / Pre-submission
Score: {N}/100

## Verdict
{SHIPPABLE / NEEDS_FIX / NOT_READY}

## Findings
### P0
- ...
### P1
- ...
### P2
- ...

## Metrics snapshot
- Repro-check: PASS / FAIL ({reasons})
- Attacker (lazy_informed) EER overall: {X}% (vs B2 {Y}%)
- Submission format: VALID / errors: {list}
- Tests: {N} pass / {M} fail

## Suggested next step
{one of: /vp-ship | fix P0 issues | /vp-spike to ablate the regression | /vp-eval --official}
```

### Step 6: Telemetry log + completion

If score >= 80 AND no P0 → suggest `/vp-ship`.
If score < 80 OR any P0 → suggest specific fix path (`/vp-investigate` for unclear failures, `/vp-spike` for regressions).

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-qa \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

## Completion status

- DONE — QA pass complete, score computed, report written, no P0
- DONE_WITH_CONCERNS — pass complete with P1 issues listed
- BLOCKED — P0 found (test failure, repro-check fail, EER regression below B1)
