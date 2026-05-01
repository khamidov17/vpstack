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
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-baseline-compare 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-baseline-compare 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

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

# Load domain config written by /vp-talk engineering mode
DOMAIN_CONFIG="$HOME/.vpstack/projects/$SLUG/domain_config.yaml"
RESAMPLE_REQUIRED=false
COMPLIANCE=none
DOMAIN=research

if [ -f "$DOMAIN_CONFIG" ]; then
  DOMAIN=$(grep "^domain:" "$DOMAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
  SAMPLE_RATE_NATIVE=$(grep "^sample_rate_native:" "$DOMAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
  RESAMPLE_REQUIRED=$(grep "^resample_required:" "$DOMAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
  COMPLIANCE=$(grep "^compliance:" "$DOMAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
  echo "Domain config loaded: domain=$DOMAIN | native_sr=${SAMPLE_RATE_NATIVE}Hz | compliance=$COMPLIANCE"

  if [ "$RESAMPLE_REQUIRED" = "true" ]; then
    echo "⚠ RESAMPLE REQUIRED: audio is ${SAMPLE_RATE_NATIVE}Hz, B1 needs 16kHz."
    echo "  Resample first: sox input.wav -r 16000 output.wav"
    echo "  Or batch:       for f in \$DIR/**/*.wav; do sox \"\$f\" -r 16000 \"\${f%.wav}_16k.wav\"; done"
  fi

  if [ "$COMPLIANCE" = "hipaa" ] || [ "$COMPLIANCE" = "gdpr" ] || [ "$COMPLIANCE" = "both" ]; then
    CURRENT_TEL=$(~/.claude/skills/vpstack/bin/vpstack-config get telemetry 2>/dev/null || echo "unknown")
    if [ "$CURRENT_TEL" != "off" ]; then
      echo "⚠ COMPLIANCE WARNING: compliance=$COMPLIANCE but telemetry is $CURRENT_TEL (not off)"
      echo "  Fix: ~/.claude/skills/vpstack/bin/vpstack-config set telemetry off"
    else
      echo "✓ Telemetry off — compliance=$COMPLIANCE requirement met"
    fi
  fi
else
  echo "No domain config found. Run /vp-talk → Engineering mode to set up your domain."
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

### Step 1: Check preamble output and set session vars

The preamble already ran SLUG, TEL_START, domain config loading, and learnings. Read any output it emitted:

**If `LEARNINGS_COUNT > 0`:** Read the recent learnings listed between `RECENT_LEARNINGS_START` and `RECENT_LEARNINGS_END`. Surface any that are relevant to this baseline run (e.g., known issues with B1 on the current domain).

**If `ROUTING_INJECTION_PENDING=yes`:** Ask once via AskUserQuestion:
> "Add vpstack skill routing to this project's CLAUDE.md so Claude automatically uses the right skill for each task?"
> A) Yes — append routing table and commit (recommended)
> B) No — I'll invoke skills manually
>
> Recommendation: A, because it makes Claude route naturally without typing /vp-* every time.

If A: append the routing block below to CLAUDE.md and run `git add CLAUDE.md && git commit -m "chore: add vpstack skill routing"`. Then `touch ~/.vpstack/projects/$SLUG/.routing-injected`.
If B: `touch ~/.vpstack/projects/$SLUG/.routing-injected` (suppress forever).

Routing block to append:
```markdown
## Skill routing (vpstack)
When voice anonymization work is requested, use these vpstack skills:
- Planning / research direction → /vp-talk
- New experiment idea → /vp-hypothesis
- Test variants → /vp-spike
- Compare against baselines → /vp-baseline-compare
- Run attacker / privacy eval → /vp-attack
- Verify reproducibility → /vp-repro-check
- Write up experiment → /vp-writeup
- Debug strange results → /vp-investigate
- Ship changes → /vp-ship
```

- If `⚠ RESAMPLE REQUIRED` appeared → **stop and ask the user to resample before continuing**
- If `⚠ COMPLIANCE BLOCKER` appeared → **stop and fix telemetry before running**
- If domain config loaded → adapt Step 2 question to mention their domain (e.g. "call center audio" instead of generic)

```bash
EXP_ID="baseline-compare-$(date +%Y%m%dT%H%M%S)"
VPBRAIN=~/.claude/skills/vpstack/bin/vpstack-brain
[ -x "$VPBRAIN" ] || VPBRAIN=.claude/skills/vpstack/bin/vpstack-brain
```

### Step 1.5: Check vpbrain for prior runs

Before spending time re-running B1, ask vpbrain whether this project has already produced canonical baseline numbers recently:

```bash
$VPBRAIN query "B1-McAdams" 2>/dev/null | head -20 || true
$VPBRAIN top --metric eer --limit 3 2>/dev/null || true
```

If a recent (≤7 days old) `B1-McAdams` run already exists with the same data path, say so and ask via AskUserQuestion:

> **Found a prior B1 run on this data ({prior_exp_id}, {date}, EER={eer}).**
>
> A) Skip re-running B1, reuse the prior numbers in the comparison
> B) Re-run B1 anyway (something material changed)
>
> Recommendation: A, because B1 is deterministic for a fixed alpha/seed/data — re-running gives you the same numbers. Pick B only if alpha changed, audio changed, or you suspect drift.

If A: load `~/.vpstack/projects/$SLUG/experiments/$PRIOR_EXP_ID/summary.json` and skip to Step 5 (comparison table).

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

### Step 3.5: Pre-flight audio check (do this BEFORE running B1)

B1 (McAdams) is calibrated for 16 kHz mono speech. Wrong format → wrong anonymization with no error. Claude must check first:

```bash
# Check sample rate of first WAV file found
FIRST_WAV=$(find "$DATA_PATH" -name "*.wav" -maxdepth 6 | head -1)
if [ -n "$FIRST_WAV" ]; then
  # Try soxi (sox), then ffprobe, then python fallback
  SR=$(soxi -r "$FIRST_WAV" 2>/dev/null \
    || ffprobe -v quiet -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 "$FIRST_WAV" 2>/dev/null \
    || python3 -c "import soundfile as sf; print(sf.info('$FIRST_WAV').samplerate)" 2>/dev/null \
    || echo "unknown")
  CHANNELS=$(soxi -c "$FIRST_WAV" 2>/dev/null \
    || python3 -c "import soundfile as sf; print(sf.info('$FIRST_WAV').channels)" 2>/dev/null \
    || echo "unknown")
  echo "Sample rate: $SR Hz | Channels: $CHANNELS"
fi
```

**Interpret the output:**
- Sample rate is NOT 16000 → **STOP and warn**: "B1 assumes 16 kHz. Your audio is ${SR} Hz. Processing it will produce badly conditioned LPC and incorrect anonymization. Resample first: `sox input.wav -r 16000 output.wav` or `ffmpeg -i input.wav -ar 16000 output.wav`. Proceed anyway only if you understand the implications."
- Channels > 1 → **Warn** (do not block): "Audio has ${CHANNELS} channels — all channels will be averaged to mono. If you need a specific channel, pre-process with `sox input.wav remix 1` first."
- Sample rate unknown → warn and proceed with caution

Also validate alpha if the user is not using the default:
- alpha > 0.95 → warn: "alpha={alpha} is near 1.0 — the pole shift is minimal, producing almost no anonymization. Canonical B1 uses alpha=0.8."
- alpha < 0.6 → warn: "alpha={alpha} is below 0.6 — expect audible artifacts and WER regression, especially on fast speech. Consider alpha in [0.7, 0.9]."

### Step 4: Run B1 baseline (McAdams)

**B1 is signal-processing only — no neural models, no GPU needed.**

#### Step 4.0: Dependency check (run BEFORE invoking B1)

```bash
DEPS_BIN=~/.claude/skills/vpstack/bin/vpstack-deps
[ -x "$DEPS_BIN" ] || DEPS_BIN=.claude/skills/vpstack/bin/vpstack-deps
DEPS_PKGS=$($DEPS_BIN packages b1)
DEPS_OK=0
$DEPS_BIN check b1 >/dev/null 2>&1 && DEPS_OK=1
```

If `DEPS_OK=0`, ask via AskUserQuestion **before** any pip mutation:

> **B1 (vpstack-b1) needs Python packages that aren't installed yet:**
> `<DEPS_PKGS>`
>
> A) Install now (`pip install --user <pkgs>`, sandboxed to `~/.local`)
> B) I'll install manually — pause this skill
> C) Cancel the comparison
>
> Recommendation: A. These are small, common scientific-Python packages. Choose B only if you manage Python in a venv (active in this shell).

On A: `$DEPS_BIN install b1`. If it fails, surface stderr and stop.
On B: stop with "Re-run /vp-baseline-compare after `pip install $DEPS_PKGS`."
On C: set `OUTCOME=abort`.

#### Step 4.1: Run B1

Use the `vpstack-b1` binary directly:

```bash
~/.claude/skills/vpstack/bin/vpstack-b1 --data_path "$DATA_PATH" --seed 42 --output_format json
```

It produces JSON on stdout: `{"ok": true, "n_files": N, "output_dir": "...", "config_hash": "..."}`. Parse it for the leaderboard table.

**Reference implementation (skip this section unless you need to debug or extend B1).** The McAdams algorithm is implemented inside `vpstack-b1`. If you want to inspect or modify it, read the script directly: `~/.claude/skills/vpstack/bin/vpstack-b1`. The algorithm is a single Python heredoc within that bash file — Patino et al. VP2020 reference, VP2026 Eval Plan parameters (alpha=0.8, frame_length=20ms, hop=10ms, lpc_order=20).


### Step 4.5: Optionally run B2 baseline

**B2 (HuBERT + ECAPA + HiFi-GAN) is wrapped via `vpstack-b2`.** vpstack does not vendor the official VP2026 B2 recipe (GPLv3) — instead, the wrapper drives whatever B2 implementation the user has installed.

Ask via AskUserQuestion:

> **Include B2 in the comparison?**
>
> A) Yes — drive my installed VP2026 B2 recipe via `vpstack-b2 --backend external`
> B) Yes — use `--backend pool-selection` (ECAPA farthest-neighbor target selection; produces a target-speaker manifest, not waveforms)
> C) No — B1 only
>
> Recommendation: A if you've installed the official VP2026 B2 recipe and want canonical numbers. B for a quick "how would speaker selection do" sanity check. C if you're iterating on the user system and don't need a B2 column right now.

If A: ask for the recipe path and target speaker pool path. The external recipe is the user's responsibility — its dependencies are not vpstack's concern. Run:
```bash
~/.claude/skills/vpstack/bin/vpstack-b2 \
  --backend external \
  --recipe_path "$RECIPE_PATH" \
  --data_path "$DATA_PATH" \
  --output_dir "$DATA_PATH/anon_b2" \
  --target_speaker_pool "$TARGET_POOL" \
  --seed 42 --output_format json
```
Parse stdout JSON for `output_dir` and `config_hash`. The `output_dir` is what the comparison table will reference and what `/vp-attack` should run on for B2 EER.

If B: dependency check first — `pool-selection` needs ECAPA via SpeechBrain:

```bash
$DEPS_BIN check b2-pool >/dev/null 2>&1 || {
  PKGS=$($DEPS_BIN packages b2-pool)
  # Ask user via AskUserQuestion same shape as Step 4.0
  # Then $DEPS_BIN install b2-pool on approval
}
```

After deps are in place, the call is:
```bash
~/.claude/skills/vpstack/bin/vpstack-b2 \
  --backend pool-selection \
  --data_path "$DATA_PATH" \
  --output_dir "$DATA_PATH/anon_b2" \
  --target_speaker_pool "$TARGET_POOL" \
  --seed 42 --output_format json
```

Surface the resulting `anon_targets.json` location to the user — they need a downstream vocoder to actually anonymize audio with this method. The B2 row in the table shows method label only, not EER/WER.

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
