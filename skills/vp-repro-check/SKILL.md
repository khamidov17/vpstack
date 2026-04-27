---
name: vp-repro-check
version: 0.1.0-dev
description: |
  Verify a VP2026 experiment is reproducible — checks seeds, dataset splits, model checkpoint
  hashes, and config completeness. Returns PASS or FAIL with specific reason. Use before submitting
  results, before merging changes, or when diagnosing why two runs produced different numbers.
  Catches silent drift early. (vpstack)
  Voice triggers: "is this reproducible", "repro check", "check splits and seeds".
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /vp-repro-check

Validate that an experiment can be reproduced. Verifies every input that affects the output: seed, splits, checkpoints, hparams. **Limitation:** does NOT validate vpstack version itself — see DESIGN.md for the rationale.

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

### Step 1: Locate the experiment to check

> "Which experiment to check?"
> A) Most recent in this project
> B) Search by ID
> C) Path to a config file

For A or B: load from `~/.vpstack/projects/{slug}/experiments/`.
For C: just point at the config.

### Step 2: Run the check

```python
report = mcp_client.call("vp_check_reproducibility", {"config_path": config_path})
```

Tool checks:
1. **Seed pinned?** Single integer in config; not absent, not list, not auto-derived from time.
2. **Dataset splits explicit?** Train/dev/test paths or HF dataset IDs are concrete, not "auto-detect".
3. **Model checkpoint hashes?** Each pretrained checkpoint has a verified SHA matching the lockfile in the recipe.
4. **Hparams complete?** Every key referenced by the recipe is present (no defaults silently filling in).
5. **CUDA determinism?** Either `torch.use_deterministic_algorithms(True)` is set, OR ≥3 seeds are recorded for variance estimation.

### Step 3: Surface result

If `report.status == "PASS"`:
```
Reproducibility check: PASS
Verified:
  ✓ seed pinned: 42
  ✓ splits: explicit (LibriSpeech dev-clean + VP2026 trial list v2026.03.17)
  ✓ checkpoints: all 3 hash-verified
  ✓ hparams: 47/47 keys present
  ✓ determinism: torch.use_deterministic_algorithms(True)

Note: vpstack version is not part of the repro contract. Current vpstack: 0.1.0-dev.
Record this version in your lab notebook.
```

If `report.status == "FAIL"`:
```
Reproducibility check: FAIL
Issues:
  ✗ seed: missing — config has no `seed` key
  ✗ checkpoints: hifigan_anon checkpoint hash mismatch (expected sha256:abc..., got sha256:def...)

Other items (passed):
  ✓ splits, hparams, determinism

Fix the marked issues and re-run /vp-repro-check.
```

### Step 4: Log result

Call `vp_log_experiment` with the repro report metadata. Useful for `/vp-search-experiments` to filter "reproducible only".

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-repro-check --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` regardless of PASS/FAIL verdict (the check ran). `error` if config unreadable.

## Completion status

- DONE — check ran, verdict shown (PASS or FAIL with reasons)
- BLOCKED — config file missing or unreadable
