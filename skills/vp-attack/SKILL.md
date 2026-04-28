---
name: vp-attack
version: 0.1.0-dev
description: |
  Run an ASV attacker against the user's anonymized speech to measure how well the anonymization
  hides the speaker. Default attacker: VP2024/2026 semi-informed ECAPA-TDNN trained on the user's
  anonymized train-clean-360. Reports per-gender EER (the official VPC privacy metric) plus
  linkability (ZEBRA Cllr) for context. Use when the user asks "did I actually hide the speaker?",
  "how strong is my anonymization?", "run the attacker", or is preparing privacy numbers for a
  VP2026 submission. Distinct from /vp-eval (full submission pipeline) and /vp-baseline-compare
  (B1/B2 delta table) — this is privacy-only, attacker-focused. (vpstack)
  Voice triggers: "run attacker", "attack my system", "privacy eval", "speaker re-id", "is my anonymization strong".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-attack

Run a VoicePrivacy-conformant ASV attacker against an anonymized output and report the EER an attacker would achieve when trying to re-identify the original speaker. **This is the central privacy question in voice anonymization** — a defense without an attacker run is unfalsifiable.

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

### Step 1: Locate the anonymized system

Ask via AskUserQuestion:

> "Which anonymized output should the attacker target?"
>
> A) Path to a directory with anonymized .wav files (system already run)
> B) My system hasn't been run yet — run B1 first so I have a baseline to attack
> C) Cancel — I want to /vp-baseline-compare first

If A: ask for the path. Validate it exists and contains .wav files. Check whether the layout matches a VP2026 trial structure (enrollment/ + trial/ subdirs, or a `trial_list.txt`). If layout is non-standard, ask the user for explicit `enrollment_path` and `trial_path`.

If B: tell the user — "Run the B1 recipe first with your anonymizer config, then re-invoke /vp-attack with the output path." Suggest `/vp-baseline-compare` to do this with full B1+B2 scaffolding. Exit.

If C: exit cleanly and suggest `/vp-baseline-compare`.

### Step 2: Choose attacker condition

Ask via AskUserQuestion:

> "Which attacker condition? Semi-informed is the official VP2026 ranking attacker — recommended."
>
> A) **semi-informed** (default, official) — ECAPA-TDNN retrained on anonymized train-clean-360. Slow: ~4–12h on a single GPU.
> B) lazy-informed — uses pretrained VoxCeleb ECAPA, but anonymizes enrollment. Fast: ~10 min.
> C) ignorant — pretrained VoxCeleb ECAPA, no enrollment anonymization. Fastest: ~5 min. Sanity floor.
> D) all three — run all conditions back-to-back (most expensive, most informative).

If user picks A or D and there is no anonymized train-clean-360 yet, warn via AskUserQuestion:

> "Semi-informed requires anonymizing train-clean-360 (~360 hours of audio) with your system before retraining the ASV. Estimated GPU time: 6–12h for anonymization + 4–8h for ASV retraining. Continue?"
>
> A) Yes, proceed
> B) No, run lazy-informed instead

Record the chosen condition(s) as `CONDITION` (one of: `ignorant`, `lazy_informed`, `semi_informed`). For option D, run the steps below three times in order: ignorant → lazy_informed → semi_informed.

### Step 3: Run the attacker

For each condition to run, execute:

```bash
python3 -m speechbrain_voice_anon.recipes.VP2026.attacker.run \
  --anonymized_path "$ANONYMIZED_PATH" \
  --enrollment_path "$ENROLLMENT_PATH" \
  --trial_list "$TRIAL_LIST_PATH" \
  --attacker_condition "$CONDITION" \
  --output_format json \
  --seed 42
```

Capture stdout as `ATTACKER_JSON`. The command streams progress to stderr every 30 seconds — relay those lines to the user verbatim so the session does not appear hung.

**If the command exits non-zero, diagnose from stderr:**

- `ATTACKER_TRAINING_FAILED` — suggest a different `--seed`, lower learning rate in `attacker.yaml`, or running `ignorant` first as a sanity check.
- `MODEL_DOWNLOAD_FAILED` — tell the user to run `huggingface-cli login` and retry.
- `DATA_MISSING` — standard hint: fetch VP2026 trial lists from the official challenge process. The enrollment path or trial list path provided may be wrong.
- `GPU_OOM` — reduce `attacker_batch_size` in attacker.yaml. Semi-informed ECAPA retraining typically needs ≥24 GB VRAM at default batch size.
- Any other failure — show the stderr tail and ask the user whether to abort or retry with a different condition.

### Step 4: Present results

Parse `ATTACKER_JSON` and format as:

```
VP2026 Attacker Results
=======================
System:     <anonymized_path>
Condition:  <condition> (<"official VP2026 ranking attacker" if semi_informed, else "informational">)
Attacker:   ECAPA-TDNN 512ch<", retrained on anonymized train-clean-360" if semi_informed>
Seed:       42

| Metric                    | Female | Male  | Overall |
|---------------------------|--------|-------|---------|
| EER % (higher = better)   | <f>    | <m>   | <o>     |
| Linkability (ZEBRA Cllr)  | <f>    | <m>   | <o>     |
| min Cllr                  | <f>    | <m>   | <o>     |

Reference points (informational):
  B1 (McAdams)        EER overall: 34.8
  B2 (neural)         EER overall: 28.1
  Random chance       EER overall: 50.0

Verdict: <delta vs B2>
```

Color rules (terminal-aware):
- **Green:** EER higher than B2 overall (you beat the stronger baseline — good privacy)
- **Yellow:** EER between B1 and B2 (better than classical, weaker than neural baseline)
- **Red:** EER below B1 (regression — your system is making re-identification *easier* than the simplest baseline)

If "all three" was selected, print a condensed comparison table across all three conditions showing overall EER and Cllr side-by-side.

### Step 5: Log experiment

Compute:
```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
EXP_ID="attack-${CONDITION}-${TIMESTAMP}"
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json`:

```json
{
  "exp_id": "<EXP_ID>",
  "skill": "vp-attack",
  "timestamp": "<ISO 8601>",
  "condition": "<condition>",
  "anonymized_path": "<anonymized_path>",
  "seed": 42,
  "metrics": <ATTACKER_JSON parsed object>
}
```

This file is retrievable by `/vp-search-experiments` and `/vp-writeup`.

### Step 6: Suggest next steps

Based on results:

- If EER drops below B1: regression — suggest `/vp-spike` to ablate which component is leaking speaker identity.
- If condition was `lazy_informed` only: suggest a follow-up `/vp-attack` with `semi_informed` for the official ranking number.
- If EER is above B2 and the user is submission-ready: suggest `/vp-eval --official` for the full scorecard (WER + side-channels + all attacker conditions).
- If the user wants robustness numbers for a paper rebuttal: suggest running all three conditions and reporting the gap between `ignorant` and `semi_informed` — this is the question reviewers ask in every Interspeech rebuttal.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-attack \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

`OUTCOME`: `success` | `error` | `abort`. On error, include `--error-class` from allowlist: `GPU_OOM`, `DATA_MISSING`, `INVALID_CONFIG`, `TIMEOUT`, `ATTACKER_TRAINING_FAILED`, `MODEL_DOWNLOAD_FAILED`, `ATTACKER_DATA_MISMATCH`.

## Completion status

- DONE — attacker ran for the requested condition(s), per-gender EER and linkability reported, experiment logged
- DONE_WITH_CONCERNS — attacker ran but one of multiple requested conditions failed (note which)
- BLOCKED — GPU OOM, VP2026 data missing, or anonymized path invalid

## Notes for skill authors

This is a **long-running** skill (semi-informed easily 8+ hours). The bash command streams progress to stderr every 30 seconds — Claude must relay those lines so the user never thinks the session is hung. Before kicking off any condition that takes more than 15 minutes, print an explicit time estimate. The "all three" mode prints a per-condition ETA up front so users can decide whether to grab lunch or just coffee.

## Why this skill exists

Voice anonymization is *defined* by an adversarial threat model. A defense without an attacker run is unfalsifiable. The official VP2026 evaluation runs one attacker (semi-informed); but real research — paper rebuttals, ablation studies, "is this gain real or a confound?" — needs the full attacker matrix. This skill standardizes that loop and lets researchers iterate against an attacker dozens of times before they are ready for a full `/vp-eval`.
