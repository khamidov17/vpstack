---
name: vp-ship
version: 0.1.0-dev
description: |
  Ship a voice-anonymization change: run vp-domain quality gates first (vp-repro-check,
  attacker smoke, submission format if applicable), then bump VERSION + commit + push +
  optional PR. Distinct from generic gstack /ship by gating on vp-specific checks BEFORE
  pushing — a regression on EER or repro-check fail blocks the ship. Use when ready to
  hand work off, before submission upload, or before merging into main. (vpstack)
  Voice triggers: "ship it", "vp ship", "ready to commit", "push my changes",
  "land this branch", "create a PR for this".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-ship

Voice-anonymization-aware ship workflow. Runs domain-specific quality gates BEFORE pushing — so a regression on EER, a repro-check failure, or a malformed submission is caught locally instead of after a labmate or reviewer hits it.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-ship 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-ship 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

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

### Step 1: Detect base branch and clean state

```bash
# Use git-native detection (works on GitHub, GitLab, self-hosted)
BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
[ -z "$BASE" ] && git rev-parse --verify origin/main >/dev/null 2>&1 && BASE="main"
[ -z "$BASE" ] && git rev-parse --verify origin/master >/dev/null 2>&1 && BASE="master"
[ -z "$BASE" ] && BASE="main"

CURRENT=$(git branch --show-current)
DIRTY=$(git status --porcelain)
```

If working tree is dirty AND user hasn't passed `--no-stash`: ask via AskUserQuestion whether to commit, stash, or abort. Same shape as gstack `/ship`.

### Step 2: Detect what changed

```bash
git diff "$BASE"...HEAD --name-only | head -20
```

Categorize:
- **Recipe changed** (under `your project code in `) → must run repro-check + baseline compare before ship
- **MCP tool changed** (under `mcp-server/`) → must run pytest -m "not gpu"
- **Skill changed** (under `skills/`) → must validate SKILL.md frontmatter
- **bin/ changed** → must `bash -n` syntax-check
- **Test changed only** → run those tests
- **Docs only** → fast-path, skip gates

### Step 3: VP-specific gate — pytest

```bash
pytest -q --tb=short -m "not gpu" 2>&1 | tail -10
```

If exit non-zero → **BLOCK SHIP**. Surface the failure; suggest `/vp-investigate` if unclear.

### Step 3.5: Check for deferred plan-eng-review gates

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(pwd)")
DEFERRED_LOG="$HOME/.vpstack/projects/$SLUG/deferred-gates.jsonl"
if [ -f "$DEFERRED_LOG" ]; then
  DEFERRED_COUNT=$(wc -l < "$DEFERRED_LOG" | tr -d ' ')
  if [ "$DEFERRED_COUNT" -gt 0 ]; then
    echo "WARN: $DEFERRED_COUNT gate(s) were deferred during /vp-plan-eng-review:"
    tail -"$DEFERRED_COUNT" "$DEFERRED_LOG"
  fi
fi
```

If deferred gates exist, surface them to the user and ask:
> "You deferred N gate(s) during plan-eng-review (shown above). Ship anyway?"
> A) Review and resolve them first (recommended)
> B) Ship anyway — I accept the deferred risk

If A: exit, let user resolve deferred gates, re-run /vp-ship.
If B: log that user accepted deferred gates, continue.

### Step 4: VP-specific gate — repro-check (if recipe changed)

Call `/vp-repro-check` on the changed config. Skip if no recipe change.

If FAIL → BLOCK SHIP. Reproducibility regression is a P0 — would silently invalidate every researcher who tries to use this version.

### Step 5: VP-specific gate — submission format (if eval pipeline changed)

If the diff touches `run_eval.py`, `check_submission.py`, or any recipe `run.py`:

```bash
# Validate VP2026 submission directory structure
SUBMISSION_DIR="<test fixture or recent run>"
ls "$SUBMISSION_DIR"/eer.json 2>/dev/null || echo "MISSING: eer.json"
ls "$SUBMISSION_DIR"/wer.json 2>/dev/null || echo "MISSING: wer.json"
ls "$SUBMISSION_DIR"/anonymized/ 2>/dev/null || echo "MISSING: anonymized/"
find "$SUBMISSION_DIR" -name "*.wav" | wc -l
```

If errors → BLOCK if user passed `--official` flag, else surface as a warning.

### Step 6: VP-specific gate — attacker smoke (optional)

For changes to recipe / anonymizer / vocoder code: ask user via AskUserQuestion:

> "Recipe / anonymizer code changed. Run a 10-min lazy_informed attacker smoke before ship?"
>
> A) Yes — run smoke (~10 min)
> B) Skip — trust the tests

If A and result.eer < B1's ~14% → flag privacy regression; ask whether to proceed.

### Step 7: VERSION bump (if not docs-only)

```bash
CURRENT_VERSION=$(cat VERSION | tr -d '[:space:]')
```

Ask via AskUserQuestion:

> "Current VERSION: $CURRENT_VERSION. Bump to:"
>
> A) Patch (0.1.0-dev → 0.1.1-dev) — bug fix
> B) Minor (0.1.0-dev → 0.2.0-dev) — new skill / new MCP tool / non-breaking change
> C) Major (0.1.0-dev → 1.0.0-dev) — breaking API change
> D) No bump — just commit and push at current version

If user picks A/B/C: update `VERSION`, `package.json::version`, `mcp-server/pyproject.toml::version`, `your project code in pyproject.toml::version` together (the CI workflow `package-lint` enforces they match).

### Step 8: CHANGELOG entry

If user accepted a version bump, append entry to CHANGELOG.md under `## [Unreleased]` (or move Unreleased to a versioned heading if minor/major):

```markdown
### Added / Fixed / Changed
- {one bullet per logical change in the diff, terse}
```

### Step 9: Commit

Stage only files in the diff (NOT `git add -A` — risk of bundling secrets). Commit message follows gstack pattern:

```
{type}: {one-line summary}

{body — what changed, why, any user-impacting notes}

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Where `{type}` is one of: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`.

### Step 10: Push

```bash
git push origin "$CURRENT" 2>&1
```

If branch isn't tracked, `git push -u origin "$CURRENT"`.

### Step 11: PR (optional)

Ask via AskUserQuestion:

> "Push complete. Create a PR against $BASE?"
>
> A) Yes, create PR with auto-generated title and body
> B) No, just push (I'll create the PR manually if needed)
> C) Yes, but let me edit the title/body first

If A or C: use `gh pr create` with title from commit subject and body summarizing the diff. If `gh` unavailable, fall back to `glab` (GitLab) or skip.

### Step 12: Report

Print:

```
✓ Tests passed (M tests)
✓ Repro-check PASS (or N/A if no recipe change)
✓ Submission format valid (or N/A)
✓ Attacker smoke EER {X}% (vs B2 {Y}%) — or N/A if skipped
✓ VERSION bumped: {old} → {new}
✓ Commit: {sha}
✓ Pushed to origin/{branch}
✓ PR: {url}  (or skipped)
```

If any gate failed, the report shows ✗ and the skill exited with BLOCKED earlier.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-ship \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

## Completion status

- DONE — all gates passed, version bumped, committed, pushed, PR created (if requested)
- DONE_WITH_CONCERNS — pushed but with P1 warnings the user accepted (e.g., minor utility regression)
- BLOCKED — gate failed (test fail, repro fail, attacker EER below B1, malformed submission with `--official`)
