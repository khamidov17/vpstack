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

### Step 1: Locate the user's system

Ask via AskUserQuestion:

> "Which anonymization system should I compare against B1 and B2?"
>
> A) Path to a directory with my anonymized audio (already-run system)
> B) Path to a SpeechBrain-style config that I want vpstack to run for me
> C) Just run B1 and B2 — no comparison, I want canonical numbers

If A: ask for the path. Validate it exists and contains `.wav` files.
If B: ask for the config path. Validate it's a YAML and references known components.
If C: skip Step 2.

### Step 2: Run the user's system (if applicable)

If user picked B in Step 1, call MCP tool `vp_run_eval` on their config. Stream progress to stderr every 30s (long-running tool contract).

```python
result = mcp_client.call("vp_run_eval", {
    "system_path": user_config_path,
    "eval_set": "dev",
    "seed": 42,
})
```

If `result.ok` is `False`, report the error to user with hint and stop.

### Step 3: Run B1 and B2 baselines

Call MCP tools in parallel:

```python
b1 = mcp_client.call("vp_run_baseline", {"baseline": "B1", "data_path": ..., "seed": 42})
b2 = mcp_client.call("vp_run_baseline", {"baseline": "B2", "data_path": ..., "seed": 42})
```

These can take hours on first run. Inform user up front: "B1 takes ~5min, B2 takes ~45min on a single GPU. Cached on subsequent runs."

### Step 4: Build the delta table

```
                   B1     B2     yours    Δ vs B1   Δ vs B2
EER (lower=better) 14.2   12.3   11.1     -3.1      -1.2
WER (lower=better) 8.4    8.1    8.0      -0.4      -0.1
Linkability        0.45   0.42   0.39     -0.06     -0.03
```

Color rules (if terminal supports):
- Green: improvement vs B2 (the stronger baseline)
- Yellow: improvement vs B1 only
- Red: regression vs both

### Step 5: Log experiment

Call MCP tool `vp_log_experiment`:

```python
mcp_client.call("vp_log_experiment", {
    "exp_id": f"baseline-compare-{timestamp}",
    "metrics": {"yours": yours, "b1": b1, "b2": b2},
    "config_hash": config_hash,
})
```

This writes to `~/.vpstack/projects/{slug}/experiments/{id}/` for later retrieval by `/vp-search-experiments` and `/vp-writeup`.

### Step 6: Suggest next steps

Based on the results:

- If user's system beats B2 on EER: suggest `/vp-eval` with `--official` to validate against held-out test set.
- If user's system regresses vs B1: suggest `/vp-spike` to ablate components and find the regression source.
- If user has no system yet (Step 1 = C): suggest `/vp-hypothesis` to formalize their first ablation.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-baseline-compare \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

Where `OUTCOME` is one of: `success`, `error`, `abort`. On `error`, include `--error-class` (allowlist: `GPU_OOM`, `DATA_MISSING`, `MCP_UNREACHABLE`, `INVALID_CONFIG`, `TIMEOUT`).

## Completion status

- DONE — table produced, experiment logged
- DONE_WITH_CONCERNS — table produced but one or more baselines failed (note which)
- BLOCKED — MCP server unreachable or VP2026 data missing

## Notes for skill authors

This is the canonical vpstack skill — every other skill follows the same shape:
1. Preamble with `vpstack-skill-init` (handles activation, version check, telemetry start)
2. Activation gate (exit silently on NO_MATCH / DISABLED)
3. First-run gate (AskUserQuestion if DETECTED_FIRST_RUN)
4. Workflow body (calls MCP tools, presents results)
5. Telemetry end (`vpstack-telemetry-log`)

Skills MUST NOT bypass the preamble — that's the privacy and silent-on-non-voice contract.
