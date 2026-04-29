---
name: vp-writeup
version: 0.1.0-dev
description: |
  Generate an INTERNAL experiment report from logs in ~/.vpstack/projects/{slug}/. Captures what
  was done, the method, hyperparameters, results table, and config hash. Does NOT generate citations
  or research-paper prose — that's the researcher's job. Use when a researcher wants a structured
  engineering log to share with a labmate, attach to a PR, or paste into their own notes. Output is
  a Markdown report, not a manuscript section. (vpstack)
  Voice triggers: "write up the experiment", "internal report", "engineering log".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-writeup

**Constraint:** This skill produces engineering reports, not academic prose. It NEVER generates citations, NEVER fabricates references, NEVER writes "Related Work" or "Discussion" sections. The output is structured facts from the logs — methods, parameters, numbers, config hashes — that a researcher can review, edit, and incorporate into their own writeup.

The decision was explicit (see DESIGN.md): LLM-generated citations are a hallucination risk, and a wrong citation in someone's paper is exactly the harm vpstack's correctness bar forbids.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-writeup 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init vp-writeup 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT) exit 0 ;;
  DETECTED_FIRST_RUN) ;;        # Skill body handles AskUserQuestion below
  ENABLED_EXPLICIT|DETECTED_CONFIRMED) ;;
esac

if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi

SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TEL_START=$(date +%s)
VPBRAIN=~/.claude/skills/vpstack/bin/vpstack-brain
[ -x "$VPBRAIN" ] || VPBRAIN=.claude/skills/vpstack/bin/vpstack-brain
EXP_ROOT="$HOME/.vpstack/projects/$SLUG/experiments"
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as in `vp-baseline-compare`.

## Workflow

### Step 1: Locate experiments to summarize

First, surface what's available so the user picks against real data, not guesses:

```bash
$VPBRAIN list
echo
$VPBRAIN stats
```

Then ask via AskUserQuestion:

> **Which experiments to include in the report?**
>
> A) Most recent N (ask for N)
> B) All experiments in this project
> C) By experiment IDs (paste comma-separated)
> D) Filter by hypothesis or method substring (uses `vpstack-brain query`)
>
> Recommendation: A with N=5, because reports stay readable and reviewers can ask for older data on demand.

Resolve to a concrete list of EXP_IDs:

- A → `ls "$EXP_ROOT" | sort -r | head -N`
- B → `ls "$EXP_ROOT"`
- C → user-provided list, validate each `[ -f "$EXP_ROOT/$EXP_ID/summary.json" ]`
- D → `$VPBRAIN query "$TEXT"` and parse the EXP_IDs out of the output

If `$EXP_ROOT` does not exist or is empty: stop with "No experiments logged yet for project $SLUG. Run /vp-spike, /vp-baseline-compare, /vp-attack, /vp-implement, or /vp-eval first — they write the summaries this report reads."

### Step 2: Generate report (deterministic; no LLM prose)

For each EXP_ID, read its `summary.json` directly (this is the same file vpstack-brain reads):

```bash
for ID in $EXP_IDS; do
  cat "$EXP_ROOT/$ID/summary.json"
done
```

Also pull project-level context for the report header:

```bash
$VPBRAIN stats          # total experiments, best EER, trend
$VPBRAIN learnings --limit 5   # confirmed findings to attach as Notes
```

The report is **mostly mechanical concatenation** from logged data — not LLM generation. The structure:

```markdown
# Experiment Report: <project slug>

Date: <ISO 8601>
vpstack version: <version>
Project: <slug>
Experiments included: <N>

## Methods

(For each unique method/system across the experiments, one short paragraph
extracted directly from the experiment's `method_summary` log field —
NOT generated, NOT embellished.)

### System: <name>
- Content encoder: <component + version>
- Speaker representation: <component + version>
- Vocoder: <component + version>
- Anonymization strategy: <description from logs>

## Results

| Exp ID | System | EER (dev) | WER (dev) | Linkability | Verdict | Config Hash |
|--------|--------|-----------|-----------|-------------|---------|-------------|
| ...    | ...    | ...       | ...       | ...         | ...     | abc123...   |

## Hyperparameters

(For each system, dump the relevant hparams from the config file — direct extraction.)

## Reproducibility

(Per-experiment status from /vp-repro-check logs, if present.)

## Notes

(Any free-form notes the researcher attached to /vp-hypothesis or /vp-spike docs — passed through verbatim.)
```

### Step 3: What this skill explicitly does NOT generate

- **No "Abstract" or "Introduction"** — that's the researcher's framing.
- **No citations or "Related Work"** — citation hallucination is the failure mode this design forbids.
- **No "Discussion" or "Conclusion"** — interpretation requires the researcher's domain judgment.
- **No claims of novelty or significance** — vpstack has no way to verify these.

If the user asks for any of the above, respond:

> "/vp-writeup is intentionally limited to structured facts from your experiment logs. For abstract/intro/discussion/citations, those need to come from you — vpstack can't verify them and won't fabricate them. That's the design tradeoff for not producing wrong citations in published papers. See DESIGN.md `/vp-writeup` row."

### Step 4: Save the report

Write to `~/.vpstack/projects/{slug}/reports/report-{date}.md`. Print the path. Offer to open it.

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log --skill vp-writeup --duration "$TEL_DUR" --outcome "$OUTCOME"
```

## Completion status

- DONE — report written to disk, path printed
- DONE_WITH_CONCERNS — report written but some experiments couldn't be loaded (listed)
- BLOCKED — `~/.vpstack/projects/{slug}/` unreadable
