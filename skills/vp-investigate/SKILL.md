---
name: vp-investigate
version: 0.1.0-dev
description: |
  Voice-privacy-domain debugging with VP2026-specific priors. When something looks
  wrong (EER weirdly high, WER tanked, repro fails, attacker output looks random),
  walks through the most-likely causes BEFORE diving into a full Python debugger
  session. Distinct from generic gstack /investigate (works fine on any code) by
  encoding domain knowledge: "EER above 50% = scoring polarity flipped", "WER NaN =
  sample-rate mismatch in vocoder output", etc. Use when something measured looks
  wrong, not when something failed to run. (vpstack)
  Voice triggers: "EER looks wrong", "why did WER spike", "debug my anonymization",
  "vp investigate", "something's off with my numbers".
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Grep
  - AskUserQuestion
---

# /vp-investigate

When voice-privacy numbers look wrong, the bug is usually in one of about a dozen places. This skill walks the dozen, asking concrete questions until the cause is found. Faster than a full debugger session for the common cases; falls back to gstack `/investigate` for the uncommon ones.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-investigate 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-investigate 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

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

### Step 1: What's wrong?

Ask via AskUserQuestion:

> "What looks wrong?"
>
> A) Privacy metric (EER) looks suspicious — too high, too low, or flat
> B) Utility metric (WER) regressed unexpectedly
> C) Two runs with the same config produced different numbers (reproducibility)
> D) Attacker output is incoherent (e.g., all-NaN, all-50%, no gender split)
> E) Submission format check fails for unclear reasons
> F) Tests pass but real-world output sounds wrong (audio quality)
> G) Other / not sure

Branch by answer. The skill is mostly a decision tree — each branch has 2-4 high-yield checks.

### Step 2A: EER looks wrong

Check in order — stop on first match:

#### 2A.1: EER > 50%? Scoring polarity is flipped.

```bash
# A target trial (same speaker enrollment + trial) should score HIGHER than a non-target.
# If your scorer returns higher = different speaker, EER comes out > 50%.
grep -rn "score" recipes/<your-recipe>/ | grep -E "(target|trial)"
```

The fix is one of: invert the score sign, swap target/non-target labels in trial_list, or fix the cosine vs distance confusion (cosine higher = same; distance higher = different).

#### 2A.2: EER ≈ 50% (random)? Attacker is broken or scored wrong.

The attacker is producing random-quality scores. Common causes:
- Attacker model not loaded (using random init weights). Check model path resolution + checkpoint hash.
- Wrong feature pipeline (extracting features at wrong sample rate).
- Anonymization output is silence / noise → attacker has nothing to score on.

Quick check: `vp_run_attacker --condition ignorant` against ORIGINAL (non-anonymized) audio. Should give very LOW EER (~1-5%) — that's the baseline ASV working. If that also shows ~50%, the attacker itself is broken; not the anonymization.

#### 2A.3: EER very low (< B1's ~14%)? Anonymization barely changing the audio.

Check the anonymized audio is actually different from the original:
```bash
# Compare a few sample pairs by file size and short-time spectrum
ls -la <orig_dir>/sample.wav <anon_dir>/sample.wav
python -c "
import soundfile as sf
o, _ = sf.read('<orig>/sample.wav')
a, _ = sf.read('<anon>/sample.wav')
import numpy as np
print('correlation:', np.corrcoef(o[:len(a)], a[:len(o)])[0,1])
"
```

Correlation > 0.95 → anonymization isn't transforming. Common causes: anonymizer in passthrough mode (config bug), output dir is the original dir (path bug), McAdams alpha=1.0 (no transformation).

#### 2A.4: EER fluctuates wildly between runs (e.g., 28% then 41% with same config)?

Non-determinism. Check:
- Seed pinned in config? (`vp-repro-check` will catch this)
- `torch.use_deterministic_algorithms(True)` set?
- DataLoader has `worker_init_fn` set per-worker?
- cuDNN benchmark mode disabled? (`torch.backends.cudnn.benchmark = False`)
- Mixed precision in the attacker training? — non-determinism from FP16 reductions.

### Step 2B: WER regressed

Check in order:

#### 2B.1: WER NaN or "infinity"? Audio is invalid.

Vocoder produced silent / clipped / wrong-sample-rate output. Quick check:
```bash
# Verify output is 16kHz 16-bit PCM (VP2026 requirement)
soxi <anon_dir>/sample.wav | grep -E "Sample Rate|Precision"
```
Expected: `Sample Rate: 16000`, `Precision: 16-bit`. Any deviation breaks downstream ASR.

Also check for clipping: max abs sample == 1.0 means hard clipping. Vocoder hyperparams may need a gain reduction.

#### 2B.2: WER spiked by >2pp after a code change?

Likely the content encoder is now leaking less content (good for privacy, bad for utility). Run `/vp-baseline-compare` to confirm vs B2 — if the gap to B2 widened, the content encoder regressed.

Common: HuBERT layer changed. Per Pasad et al. ASRU 2021, content peaks at layers 7-9. Layers 1-4 are speaker-leaning. Check your config didn't accidentally use layer 3.

#### 2B.3: WER fine on dev but bad on test?

Distribution shift, not a bug. Different speakers / different recording conditions. Document but don't "fix."

### Step 2C: Reproducibility — same config, different numbers

Run `/vp-repro-check` first if you haven't. The 5 checks (seed, splits, checkpoints, hparams, determinism) catch 80% of cases. If repro-check PASSes but numbers still drift:

- **CUDA non-determinism.** Even with deterministic algorithms enabled, a few ops on certain GPU/cuDNN versions are non-deterministic. Mitigation: run with N≥3 seeds and report mean ± std, not single-run numbers.
- **PyTorch version mismatch.** Different PyTorch versions can produce slightly different attacker EER. Pin in `pyproject.toml`.
- **Mixed precision.** Disable FP16 in attacker training; reductions are non-deterministic.
- **Dataloader worker count.** Same `seed` with different `num_workers` shuffles differently. Pin both.

### Step 2D: Attacker output is incoherent

Attacker EER all-NaN or showing no gender split:

#### 2D.1: All-NaN? CSV column missing or scoring crashed silently.
```bash
head -3 exp/asv_anon*/results*.csv
```
Look for missing `EER` column or NaN-filled rows. If the CSV is truncated, training crashed mid-run; check `~/.vpstack/projects/<slug>/attacker_logs/`.

#### 2D.2: No gender split (only "Mixed" reported)? Trial list missing gender column.
VP2026 requires per-gender breakdown. Trial list TSV needs `gender` column populated for every trial.

### Step 2E: Submission format fails

Run `vp_check_submission` and read the error message — it lists missing files specifically. Common:
- You passed the project root, not the `exp/` parent directory.
- File extensions: VP2026 wants `.csv`, not `.json`. (Earlier vpstack docs were wrong about this — corrected 2026-04-28.)
- `result_for_submission<suffix>.zip` missing. Generate it from `exp/results_summary/track1/` after the eval completes.

### Step 2F: Audio quality is bad despite metrics looking OK

Listen to a sample. Common audio defects vocoders introduce:
- **Buzzing / metallic artifacts:** vocoder undertrained or wrong sample rate.
- **Clipping:** gain/normalization issue post-vocoder.
- **Whispered / breathy:** speaker embedding too distant from any natural voice.
- **Robotic:** content encoder layer too speaker-leaning, vocoder hallucinating.

Metrics may not catch these. Spot-check 5-10 random samples after every recipe change.

### Step 2G: Fall back to generic /investigate

For anything that doesn't match the patterns above, hand off:

> "I haven't found a domain-specific cause. Suggest running gstack `/investigate` for a full Python-stack-level analysis, or post the symptom + last-200-lines-of-stderr to `~/.vpstack/projects/<slug>/investigate-notes/{date}.md` so we can grow the priors here."

### Step 3: Document the finding

Whether resolved or punted to gstack `/investigate`, write to `~/.vpstack/projects/{slug}/investigations/{date}.md`:

```markdown
# Investigation: {symptom}
Date: {ISO 8601}

## Symptom
{user's complaint}

## Hypotheses tested
1. {hypothesis} — {result}
2. ...

## Root cause
{found cause, or "punted to gstack /investigate"}

## Fix applied
{or: "fix pending"}

## Lesson learned (add to skill priors?)
{1 sentence; if useful, file an issue to add to /vp-investigate's decision tree}
```

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-investigate \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

`OUTCOME`: success if root cause found, abort if user gave up, error if vpstack itself crashed during diagnostic.

## Completion status

- DONE — root cause found and fix applied (or applied a verified workaround)
- DONE_WITH_CONCERNS — root cause likely identified but not fully verified (e.g., needs a longer rerun)
- BLOCKED — punted to gstack `/investigate` for non-domain causes
- NEEDS_CONTEXT — symptom too vague to triage; ask for stderr / config / sample audio
