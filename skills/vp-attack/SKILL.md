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
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as in `vp-baseline-compare`. On Yes: `mkdir -p .vpstack && touch .vpstack/enabled`, append project hash to `~/.vpstack/projects-decided`. On No: `mkdir -p .vpstack && touch .vpstack/disabled`, exit. On C: `touch .vpstack/ask-later`, exit (60min reprompt suppression).

## Workflow

### Step 1: Locate the anonymized system

Ask via AskUserQuestion:

> "Which anonymized output should the attacker target?"
>
> A) Path to a directory with anonymized .wav files (system already run)
> B) Path to a SpeechBrain-style anonymizer config that vpstack should run first
> C) Cancel — I want to /vp-baseline-compare first

If A: ask for the path. Validate it exists, contains .wav files, and that the layout matches a VP2026 trial structure (enrollment/ + trial/ subdirs, or a `trial_list.txt`). If layout is non-standard, ask the user for explicit `enrollment_path` and `trial_path`.

If B: call `vp_run_eval` first to produce the anonymized output, then continue with the path it returned.

If C: exit cleanly and suggest `/vp-baseline-compare`.

### Step 2: Choose attacker condition

Ask via AskUserQuestion:

> "Which attacker condition? Semi-informed is the official VP2026 ranking attacker — recommended."
>
> A) **semi-informed** (default, official) — ECAPA-TDNN retrained on anonymized train-clean-360. Slow: ~4–12h on a single GPU.
> B) lazy-informed — uses pretrained VoxCeleb ECAPA, but anonymizes enrollment. Fast: ~10 min.
> C) ignorant — pretrained VoxCeleb ECAPA, no enrollment anonymization. Fastest: ~5 min. Sanity floor.
> D) all three — run all conditions back-to-back (most expensive, most informative).

If user picks A or D and there is no anonymized train-clean-360 yet, warn:

> "Semi-informed requires anonymizing train-clean-360 with your system (~360 hours of audio). Estimated GPU time: 6–12h for anonymization + 4–8h for ASV training. Continue?"

### Step 3: Run the attacker

Call MCP tool `vp_run_attacker`:

```python
result = mcp_client.call("vp_run_attacker", {
    "anonymized_path": anonymized_path,
    "enrollment_path": enrollment_path,
    "trial_list": trial_list_path,
    "attacker_condition": condition,   # "ignorant" | "lazy_informed" | "semi_informed"
    "attacker_arch": "ecapa_tdnn",     # default; "ecapa_plda_mix" / "resnet34_lora" reserved for v0.2
    "anonymizer_config": anonymizer_config_path,  # required iff condition == "semi_informed"
    "seed": 42,
})
```

If condition is `semi_informed`, the MCP tool does the full pipeline: anonymize train-clean-360 → retrain ECAPA-TDNN on it → score trials. Stream progress to stderr every 30s.

If `result.ok` is `False`:
- `ATTACKER_TRAINING_FAILED` → suggest a different `seed`, lower learning rate in `attacker.yaml`, or running `lazy_informed` first as a sanity check
- `MODEL_DOWNLOAD_FAILED` → tell user to `huggingface-cli login`
- `DATA_MISSING` → standard hint to fetch VP2026 trial lists from the official challenge process
- `GPU_OOM` → reduce `attacker_batch_size` in attacker.yaml; semi-informed ECAPA training typically needs ≥24GB VRAM at default batch

### Step 4: Present results

```
VP2026 Attacker Results
=======================
System:     <anonymized_path>
Condition:  semi_informed (official VP2026 ranking attacker)
Attacker:   ECAPA-TDNN 512ch, retrained on anonymized train-clean-360
Seed:       42

| Metric                    | Female | Male  | Overall |
|---------------------------|--------|-------|---------|
| EER % (higher = better)   | 38.2   | 35.7  | 36.9    |
| Linkability (ZEBRA Cllr)  | 0.41   | 0.43  | 0.42    |
| min Cllr                  | 0.38   | 0.40  | 0.39    |

Reference points (informational):
  B1 (McAdams)        EER overall: 34.8
  B2 (neural)         EER overall: 28.1
  Random chance       EER overall: 50.0

Verdict: privacy delta vs B2 = +8.8 EER (your system is harder to attack)
```

Color rules (terminal-aware):
- **Green:** EER higher than B2 (you beat the stronger baseline)
- **Yellow:** EER between B1 and B2
- **Red:** EER below B1 (regression on privacy — your "anonymization" is making things WORSE than the simplest baseline)

### Step 5: Log experiment

```python
mcp_client.call("vp_log_experiment", {
    "exp_id": f"attack-{condition}-{timestamp}",
    "metrics": {"attacker": result, "condition": condition},
    "config_hash": result["config_hash"],
})
```

Writes to `~/.vpstack/projects/{slug}/experiments/{id}/` for retrieval by `/vp-search-experiments` and `/vp-writeup`.

### Step 6: Suggest next steps

Based on results:

- If EER drops below B1: regression — suggest `/vp-spike` to ablate which component of your system is leaking speaker identity.
- If condition was `lazy_informed` only: suggest a follow-up `/vp-attack --condition semi_informed` for the official ranking number.
- If EER above B2 and submission-ready: suggest `/vp-eval --official` for the full scorecard (WER + side-channels + all attacker conditions).
- If user wants robustness numbers for a paper rebuttal: suggest running all three conditions and reporting the gap between `ignorant` and `semi_informed` (this is what reviewers ask in every Interspeech rebuttal).

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-attack \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

`OUTCOME`: `success` | `error` | `abort`. On error, include `--error-class` from allowlist: `GPU_OOM`, `DATA_MISSING`, `MCP_UNREACHABLE`, `INVALID_CONFIG`, `TIMEOUT`, `ATTACKER_TRAINING_FAILED`, `MODEL_DOWNLOAD_FAILED`, `ATTACKER_DATA_MISMATCH`.

## Completion status

- DONE — attacker ran for the requested condition(s), per-gender EER and linkability reported, experiment logged
- DONE_WITH_CONCERNS — attacker ran but one of multiple requested conditions failed (note which)
- BLOCKED — MCP unreachable, GPU OOM, VP2026 data missing, or anonymizer_config invalid for semi_informed

## Notes for skill authors

This is a **long-running** skill (semi-informed easily 8+ hours). The MCP layer must stream progress every 30 seconds. The skill should print an explicit time estimate before kicking off any condition that takes more than 15 minutes — never let the user think it's hung. The `all` mode prints a per-condition ETA up front so users can decide whether to go grab lunch or just coffee.

## Why this skill exists

Voice anonymization is *defined* by adversarial threat model. A defense without an attacker run is unfalsifiable. The official VP2026 evaluation runs one attacker (semi-informed); but real research work — paper rebuttals, ablation studies, "is this gain real or a confound?" — needs the full attacker matrix. This skill standardizes that loop and lets researchers iterate against an attacker dozens of times before they're ready for a full `/vp-eval`.
