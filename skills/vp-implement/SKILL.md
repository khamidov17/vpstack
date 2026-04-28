---
name: vp-implement
version: 0.1.0-dev
description: |
  Orchestrated implementation of a voice-anonymization recipe component (recipe runner, MCP tool,
  or hparams YAML). Reads the latest /vp-hypothesis, enforces the recipe-shape contract from
  CLAUDE.md (CLI args, JSON output, deterministic mode, lazy weight fetching), gates atomic
  commits with no placeholder hparams, auto-runs /vp-repro-check, verifies the 7 critical CG
  tests still pass, and logs the result so /vp-writeup can find it. Use when implementing B2,
  the attacker, ecapa_farthest, hifigan_anon, or any new MCP tool. Distinct from generic Claude
  Code editing — gates the implementation against the 5 silent-drift failure modes specific to
  voice-privacy research. (vpstack)
  Voice triggers: "implement", "build the recipe", "code up B2", "ship the attacker", "write the recipe".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# /vp-implement

Coding-with-guardrails for VP2026 recipe components. Replaces "agent codes between meta-commands" with an explicit pre/during/post-gate workflow that catches the five failure modes that bite voice-privacy research: unread hypothesis, placeholder hparams, forgotten determinism, skipped repro-check, unlogged experiment.

This skill MUST NOT be used for general dev work — it activates only on voice-anonymization repos and only writes under `your anonymization recipe in ` or ``. For other implementation work in this repo (bash scripts, docs, CI), code directly without this skill.

## Preamble (run first)

```bash
TEL_START=$(date +%s)
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

Same shape as `vp-baseline-compare`. On C: `mkdir -p .vpstack && touch .vpstack/ask-later`, exit silently.

## Workflow

### Step 1: Pre-flight load

Read in parallel:
- `~/.vpstack/projects/$SLUG/hypotheses/*.md` — most recent 5 (mtime ≤ 14 days)
- `~/.vpstack/projects/$SLUG/research-plans/*.md` — locked plans (from `/vp-talk`)
- `CLAUDE.md` (repo root) — local rules
- `your anonymization recipe in baseline_B1/run.py` — canonical recipe shape

### Step 2: Hypothesis selection

If no recent hypothesis docs exist:

> "No recent hypothesis found. /vp-implement requires either a hypothesis OR explicit exploratory-mode acknowledgement."
>
> A) Run /vp-hypothesis first (recommended)
> B) Continue exploratory (logged as no-hypothesis)
> C) Abort

On A: emit hand-off message, exit DONE.
On B: `touch ~/.vpstack/projects/$SLUG/exploratory-$(date +%s).flag`. Hypothesis-update step (Step 11) is skipped.
On C: exit ABORT.

If hypotheses exist, ask which one. Surface its **acceptance criteria verbatim** — that's what `/vp-baseline-compare` will measure later.

### Step 3: Target + contract confirmation

> "What are you implementing? (paths, comma-separated)"

Validate every path resolves under `your project code in recipes/` or ``. Otherwise BLOCK with `error_class=TARGET_OUT_OF_SCOPE`.

> "Which contract?"
>
> A) Recipe runner (run.py shape: --data_path, --seed, --output_format, single JSON line on stdout)
> B) MCP tool (returns ToolResult; codes from ERROR_CODES allowlist)
> C) Hparams YAML only
> D) Combination

Persist `$CONTRACT_TYPE`.

### Step 4: License + clean-tree + baseline-tests gate

```bash
# License audit — non-negotiable rule #1
if git grep -nE 'Voice-Privacy-Challenge-2024' -- ':!LICENSING.md' ':!THIRD_PARTY_LICENSES.md' >/dev/null 2>&1; then
  echo "BLOCKED: LICENSE_VIOLATION — VP2024 GPLv3 reference detected." >&2
  OUTCOME=error; ERROR_CLASS=LICENSE_VIOLATION
  exit 1
fi

# Clean tree
if [ -n "$(git status --porcelain)" ]; then
  # AskUserQuestion: A) Stash/commit first  B) Continue (NOT recommended)  C) Abort
  :
fi

# Baseline tests snapshot — captures green test set BEFORE any change
pytest -m "not gpu" -q --tb=no > /tmp/vpstack-impl-baseline.txt 2>&1
BASELINE_RC=$?
if [ $BASELINE_RC -ne 0 ]; then
  echo "BLOCKED: BASELINE_TESTS_RED — fix tree before /vp-implement." >&2
  exit 1
fi
```

### Step 5: Implementation loop (agent codes here)

Inform the agent of these invariants — re-check before EACH commit:

1. **Atomic commit per logical unit.** One file group + its tests = one commit.
2. **No placeholder hparams (YAML recipes only — skip for B1/argparse-only).** If implementing a YAML-configured recipe (B2, custom neural, attacker), YAML values must not equal `TODO`, `FILL_ME`, `null`, or `""`. B1 (McAdams) uses only argparse — skip this check entirely for B1.
   ```bash
   python -c "import sys, yaml; cfg=yaml.safe_load(open(sys.argv[1])); \
     bad=[k for k,v in (cfg.get('hparams') or {}).items() if v in ('TODO','FILL_ME',None,'')]; \
     sys.exit(1 if bad else 0); print('placeholder keys:', bad)" "$YAML_PATH" \
     || { echo BLOCKED: PLACEHOLDER_HPARAMS; exit 1; }
   ```
3. **Tests added alongside code.** MCP tool → `tests/mcp/test_{tool}.py`. Recipe → `tests/recipes/test_{name}_smoke.py`. Never edit existing CI workflows or existing tests (rule #6).
4. **Recipe-runner contract** (`$CONTRACT_TYPE` ∈ {A, D}):
   - argparse: `--data_path`, `--seed` (int, default 42), `--output_format` ∈ {json, human}
   - `output_format == "json"` → single `print(json.dumps({...}))` on stdout
   - Progress to stderr ≥ every 30s
   - `torch.use_deterministic_algorithms(True)` if hparams set `deterministic: true`
   - Lazy weights via `huggingface_hub.snapshot_download` — never bundle
5. **MCP-tool contract** (`$CONTRACT_TYPE` ∈ {B, D}):
   - Returns `ToolResult` via `ok()` / `err()` (from `vpstack_mcp.errors`)
   - Every `err()` code is in `ERROR_CODES` frozenset
   - No unhandled exceptions
   - Registered in `_TOOLS` in `server.py`, imported in `tools/__init__.py`

If any invariant fails before commit, BLOCK and surface the specific issue.

### Step 6: Lint pass

```bash
ruff check . --fix && ruff format --check . || { OUTCOME=error; ERROR_CLASS=RUFF_DIRTY; exit 1; }
```

### Step 7: Contract verification

Branch by `$CONTRACT_TYPE`:

**A — Recipe runner:**
```bash
python3 /tmp/vp_b1_run.py  # use the McAdams script from vp-baseline-compare for B1; adapt for other recipes \
    --data_path tests/fixtures/librispeech_clip \
    --seed 42 --output_format json | tail -1 > /tmp/impl-out.json
python -c "
import json, sys
d = json.load(open('/tmp/impl-out.json'))
required = {'eer', 'wer', 'linkability', 'config_hash'}
missing = required - d.keys()
sys.exit(1 if missing else 0)
" || { echo BLOCKED: CONTRACT_VIOLATION; exit 1; }
```

**B — MCP tool:** import the new module, call its `handle(...)` with synthetic args, assert `ToolResult` shape and `error.code in ERROR_CODES`.

**C — Hparams YAML only:** Step 8 covers it.

### Step 8: Repro-check auto-run

If any YAML was created/modified:

Run the repro check via bash:

```bash
# Check seed
grep -E "^seed: [0-9]+" "$yaml_path" || echo "FAIL: seed missing or not an integer"
# Check splits
grep -E "^(data|splits):" "$yaml_path" || echo "FAIL: no data/splits section"
grep -v "auto" <(grep -A5 "^data:" "$yaml_path" 2>/dev/null) || echo "WARN: auto-detected split"
# Check placeholder hparams
grep -E "TODO|FILL_ME" "$yaml_path" && echo "FAIL: placeholder hparams"
# Check determinism
grep -E "deterministic: true|torch_deterministic: true" "$yaml_path" || echo "WARN: not deterministic"
# Check checkpoint lockfile
ls "$(dirname $yaml_path)/checkpoints.lock" 2>/dev/null || echo "WARN: no checkpoints.lock"
```

If any FAIL lines appear → BLOCKED: REPRO_CHECK_FAIL. Surface the specific failing checks verbatim. Do NOT auto-fix.

### Step 9: Test-regression gate

```bash
pytest -m "not gpu" -q --tb=short > /tmp/vpstack-impl-after.txt 2>&1
if [ $? -ne 0 ]; then
  diff /tmp/vpstack-impl-baseline.txt /tmp/vpstack-impl-after.txt
  echo "BLOCKED: TESTS_REGRESSED" >&2
  exit 1
fi
```

The 7 critical CG tests live in this set — they're checked here.

### Step 10: Log to experiment tracker

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
EXP_ID="impl-$(basename $TARGET_PATH | tr '/' '-')-$(date +%Y%m%dT%H%M%S)"
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json`:

```json
{
  "id": "<EXP_ID>",
  "date": "<ISO 8601>",
  "skill": "vp-implement",
  "config_hash": "<config_hash from recipe or 'n/a'>",
  "metrics": {
    "tests_passed": "<count>",
    "ruff_clean": true,
    "repro_check": "<PASS or N/A>",
    "contract_type": "<CONTRACT_TYPE>"
  }
}
```

### Step 11: Update hypothesis status (skip if exploratory)

Append to the hypothesis doc:

```markdown
## Implementation
Status: IMPLEMENTED (pending /vp-baseline-compare)
Files: <paths>
Commits: <git log --format='%h %s' base..HEAD>
Repro-check: PASS
Date: <ISO 8601>
```

### Step 12: Suggest next step

- Recipe runner / MCP tool → "Next: `/vp-baseline-compare` to measure vs B1/B2."
- Hparams-only → "Next: `/vp-spike` to test variants with this config."
- Exploratory → "Implementation done. Consider `/vp-hypothesis` to formalize before more time."
- Attacker component → "Next: `/vp-attack` to validate against the three official conditions."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-implement \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME" \
  ${ERROR_CLASS:+--error-class "$ERROR_CLASS"}
```

## Completion status

- DONE — all 9 post-gates passed; experiment logged; hypothesis updated; next-step shown.
- DONE_WITH_CONCERNS — implementation complete in exploratory mode (no hypothesis to update). Other gates passed.
- BLOCKED — any pre-gate, mid-loop invariant, or post-gate failed. Work is preserved (commits not reverted) but skill exits non-zero with a specific error class so the agent knows what to fix.

## Failure modes (BLOCKED states)

- `LICENSE_VIOLATION` — diff introduces VP2024 GPLv3 reference
- `BASELINE_TESTS_RED` — tests already failing before implementation
- `TARGET_OUT_OF_SCOPE` — path not under recipes/ or mcp-server/tools/
- `PLACEHOLDER_HPARAMS` — YAML has TODO / FILL_ME / null / ""
- `CONTRACT_VIOLATION` — recipe runner missing required CLI arg or JSON output shape; MCP tool raises unhandled exception
- `REPRO_CHECK_FAIL` — `vp_check_reproducibility` returned FAIL
- `TESTS_REGRESSED` — at least one test that passed at Step 4 fails at Step 9
- `RUFF_DIRTY` — `ruff check .` reports issues `--fix` didn't resolve
- `MCP_UNREACHABLE` — `vp_log_experiment` or `vp_check_reproducibility` transport error
