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
  - Write
  - AskUserQuestion
---

# /vp-repro-check

Validate that an experiment can be reproduced. Verifies every input that affects the output: seed, splits, checkpoints, hparams, and determinism. **Limitation:** does NOT validate vpstack version itself — see DESIGN.md for the rationale.

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

TEL_START=$(date +%s)
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion:

> "This project looks like voice-anonymization work (matched: $ACTIVATION_REASON). Enable vpstack here?"
>
> A) Yes, enable for this project
> B) No, silence vpstack on this project forever
> C) Ask me again next time

On A: `mkdir -p .vpstack && touch .vpstack/enabled`, append project hash to `~/.vpstack/projects-decided`, and proceed.
On B: `mkdir -p .vpstack && touch .vpstack/disabled`, exit silently.
On C: `mkdir -p .vpstack && touch .vpstack/ask-later` and exit silently. Marker valid for 60min — prevents re-prompt loops in a multi-skill session.

## Workflow

### Step 1: Locate the experiment to check

Ask via AskUserQuestion:

> "Which experiment configuration should I check for reproducibility?"
>
> A) Most recent experiment in this project (from ~/.vpstack/projects/<slug>/experiments/)
> B) Search by experiment ID
> C) Path to a specific config file (e.g., train.yaml, hparams.yaml)

For A: run:
```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
ls -t ~/.vpstack/projects/$SLUG/experiments/ | head -1
```
Load the `summary.json` from that experiment and extract `config_path`.

For B: ask for the ID, then resolve to `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json` and extract `config_path`.

For C: use the path the user provides directly as `CONFIG_PATH`.

If `CONFIG_PATH` does not exist or is not readable, report BLOCKED and exit.

### Step 2: Run the five reproducibility checks

Execute each check as a separate bash command. Collect the output to determine PASS or FAIL per item.

**Check 1 — Seed pinned**

```bash
grep -E "^seed:" "$CONFIG_PATH" || echo "MISSING: seed"
```

PASS: output is a single line matching `seed: <integer>` (e.g., `seed: 42`).
FAIL: output is `MISSING: seed`, or the seed value is a range, a list, or the word `null`/`auto`.

**Check 2 — Dataset splits explicit**

```bash
grep -E "^(data|splits|data_path|train_csv|dev_csv|test_csv):" "$CONFIG_PATH" || echo "MISSING: data/splits section"
```

PASS: at least one concrete path or HuggingFace dataset ID is present (not `auto`, not empty).
FAIL: output is `MISSING: data/splits section`, or every matched value is `auto` / blank.

**Check 3 — Model checkpoint hashes**

First, locate the lockfile:
```bash
LOCKFILE="$(dirname "$CONFIG_PATH")/checkpoints.lock"
ls "$LOCKFILE" 2>/dev/null || echo "MISSING: checkpoints.lock"
```

If `checkpoints.lock` is missing: FAIL on this check, note it, continue.

If present, read the lockfile and for each checkpoint listed:
```bash
sha256sum /path/to/checkpoint.pt
```
Compare the computed hash against the expected hash in `checkpoints.lock`. Any mismatch = FAIL for this item. Report which checkpoint(s) failed and both hashes.

**Check 4 — Hparams complete (no placeholder values)**

```bash
grep -E "TODO|FILL_ME|PLACEHOLDER|null|~$" "$CONFIG_PATH" && echo "FAIL: placeholder hparams found" || echo "PASS: no placeholders detected"
```

PASS: no matches (the `grep` exits non-zero and we fall through to the echo).
FAIL: any `TODO`, `FILL_ME`, `PLACEHOLDER` token found, or values that are bare `null` or `~` (YAML null).

Additionally, use Read to scan the config and verify that every key referenced in the recipe's `run.py` docstring is present in the config. If there are missing required keys, list them as FAIL items.

**Check 5 — CUDA determinism**

```bash
grep -E "deterministic|torch_deterministic|use_deterministic_algorithms" "$CONFIG_PATH" || echo "MISSING: determinism"
```

PASS (strong): a line matching `torch.use_deterministic_algorithms(True)` or `deterministic: true` is present.
PASS (weak, note it): output is `MISSING: determinism` AND the experiment's summary.json records ≥3 seeds with variance estimates.
FAIL: determinism is missing and fewer than 3 seeds are recorded.

### Step 3: Surface result

Collate all five check outcomes and print a structured verdict.

**If all checks pass (with checkpoint hashes verified):**

```
Reproducibility check: PASS_STRONG
Verified:
  ✓ seed pinned: <value>
  ✓ splits: explicit (<paths or dataset IDs found>)
  ✓ checkpoints: all <N> hash-verified against checkpoints.lock
  ✓ hparams: no placeholder values detected, required keys present
  ✓ determinism: torch.use_deterministic_algorithms(True)

PASS_STRONG: This experiment should reproduce exactly given the same hardware.
Note: vpstack version is not part of the repro contract. Record it in your lab notebook.
```

**If all checks pass but determinism via n_seeds (no torch_deterministic flag):**

```
Reproducibility check: PASS_WEAK
Verified:
  ✓ seed pinned: <value>
  ✓ splits: explicit
  ✓ checkpoints: <N> hash-verified
  ✓ hparams: no placeholders
  ⚠ determinism: ≥3 seeds recorded (statistical reproduction only — no torch_deterministic flag)

PASS_WEAK means variance was measured, not eliminated. A 4th seed could be an outlier.
Suitable for exploratory work. For publication, set torch_deterministic: true and rerun.
```

**If checkpoints.lock is missing:**

```
Reproducibility check: PASS_WEAK (checkpoint hashes unverified)
⚠ checkpoints.lock not found — model weights are not hash-pinned.
  If HuggingFace updates a checkpoint and you re-download, your results change silently.
  Create checkpoints.lock (format documented in docs/domain.md#checkpoints-lock-format).
  Generate SHA256: sha256sum /path/to/checkpoint.pt | awk '{print $1}'
```

**If any check fails:**

```
Reproducibility check: FAIL
Issues:
  ✗ <check name>: <specific reason>
  ✗ <check name>: <specific reason>

Passed:
  ✓ <check name>
  ...

Fix the marked issues and re-run /vp-repro-check.
```

For checkpoint hash mismatches specifically, show both the expected and actual sha256 so the user knows whether the checkpoint was silently updated upstream or locally modified.

### Step 4: Log repro result

Compute:
```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPRO_ID="repro-check-${TIMESTAMP}"
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$REPRO_ID
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$REPRO_ID/summary.json`:

```json
{
  "exp_id": "<REPRO_ID>",
  "skill": "vp-repro-check",
  "timestamp": "<ISO 8601>",
  "config_path": "<CONFIG_PATH>",
  "verdict": "PASS" | "FAIL",
  "checks": {
    "seed": "<PASS|FAIL>: <detail>",
    "splits": "<PASS|FAIL>: <detail>",
    "checkpoints": "<PASS|FAIL>: <detail>",
    "hparams": "<PASS|FAIL>: <detail>",
    "determinism": "<PASS|FAIL|PASS_WEAK>: <detail>"
  }
}
```

This metadata is used by `/vp-search-experiments` to filter "reproducible-only" results.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-repro-check --duration "$TEL_DUR" --outcome "$OUTCOME"
```

`OUTCOME`: `success` regardless of PASS/FAIL verdict (the check itself ran). `error` if config was unreadable. `abort` if user cancelled.

## Completion status

- DONE — check ran, verdict shown (PASS or FAIL with per-check reasons), result logged
- BLOCKED — config file missing, unreadable, or experiment ID not found
