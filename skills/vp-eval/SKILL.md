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

Run the canonical VP2026 eval pipeline end-to-end and validate the submission format. Higher fidelity than `/vp-baseline-compare` — runs the full protocol with all required metrics and produces a submission-ready bundle.

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

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as in `vp-baseline-compare`.

## Workflow

### Step 1: Locate the system to evaluate

> "Path to the anonymization system or output directory to evaluate?"
> A) System config (vpstack runs anonymization + eval)
> B) Pre-anonymized audio directory (vpstack runs eval only)

If user passes the held-out **test** split, require explicit `--official` flag and ask for confirmation:

> "Test split is held-out. Running eval on test before submission can lead to overfitting. Continue?"
> A) Yes — I'm preparing the official submission  B) No, switch to dev

### Step 2: Run the full eval

```python
result = mcp_client.call("vp_run_eval", {
    "system_path": system_path,
    "eval_set": eval_set,  # "dev" or "test"
    "seed": 42,
})
```

Stream progress every 30s. Total runtime: ~1-3 hours on a single GPU depending on system.

### Step 3: Validate submission format

```python
validation = mcp_client.call("vp_check_submission", {"submission_path": result.output_dir})
```

If invalid, surface errors with hints:
```
Submission errors:
  - missing required file: trial_results/dev/eer.json
  - eer.json malformed: expected {"male": float, "female": float, "overall": float}, got {...}
```

### Step 4: Present results

```
VP2026 Evaluation Results
=========================
Eval set: dev
Seed: 42
System: <path>
Config hash: abc123...

| Metric             | Value | vs B2  |
|--------------------|-------|--------|
| EER (overall)      | 11.1  | -1.2   |
| EER (male)         | 10.8  | -1.4   |
| EER (female)       | 11.4  | -1.0   |
| WER                | 8.0   | -0.1   |
| Linkability        | 0.39  | -0.03  |
| Side-channel: age  | ...   | ...    |
| Side-channel: pitch| ...   | ...    |

Submission validation: PASS
Output directory: ~/.vpstack/projects/{slug}/experiments/{id}/
```

### Step 5: Log + suggest next

Call `vp_log_experiment`. Suggest:
- If submission validation passed AND running on dev: `/vp-eval --official` to run on held-out test
- If failed validation: fix the listed issues and re-run
- If running on test: bundle the output dir as the official submission archive

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-eval --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` on full eval pass. `error` with `--error-class EVAL_BLOCKED_TEST_SPLIT` if user tried test split without `--official`. `error` with class `MALFORMED_SUBMISSION` on validation fail.

## Completion status

- DONE — eval ran, results saved, submission validated
- DONE_WITH_CONCERNS — eval ran but submission validation found errors (listed)
- BLOCKED — VP2026 data missing, GPU OOM, or MCP unreachable
