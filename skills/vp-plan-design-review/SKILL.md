---
name: vp-plan-design-review
version: 0.1.0-dev
description: |
  Voice-privacy-domain design review of a recipe architecture, attacker spec, or
  reproducibility design BEFORE coding starts. Distinct from generic gstack-style
  design review (which is about visual UI). This reviews: recipe interface contract,
  attacker condition coverage, repro design (seed/splits/checkpoints), eval-set
  safety, and license posture (no GPLv3 vendoring). Use when planning a new
  baseline, attacker, or eval pipeline before touching code. (vpstack)
  Voice triggers: "review my recipe design", "design review my attacker", "vp design review", "is this architecture sound".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-plan-design-review

Review a voice-anonymization recipe / attacker / eval-pipeline design BEFORE implementation. Catches design-level mistakes (missing attacker conditions, accidentally testable test split, GPLv3 license traps, recipe interface drift) while they're still cheap to fix.

## Preamble (run first)

```bash
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

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion (Yes / No / Ask later) — same shape as `vp-baseline-compare`.

## Workflow

### Step 1: Locate the design

Ask via AskUserQuestion:

> "What's being designed?"
>
> A) A new recipe (anonymizer, baseline, vocoder)
> B) A new attacker / attacker condition
> C) A new eval pipeline or metric
> D) Modification to an existing recipe / attacker / eval

For path: ask the user to point at a design doc (e.g., `~/.vpstack/projects/{slug}/research-plans/{date}.md`), a hypothesis doc, or paste the design inline.

### Step 2: Recipe interface contract review (if A or D and recipe-related)

Check the proposed recipe matches the canonical contract:

- **CLI args:** `--data_path` (or domain-specific equivalent), `--seed`, `--output_format json|human`. NOT `argparse` defaults that mask reproducibility (no `--seed` defaulting to a random value).
- **stdout shape:** single JSON line with `{eer, wer, linkability, config_hash, ...}` for baselines; per-gender breakdown for attackers (`eer_female, eer_male, eer_overall`).
- **stderr:** progress every 30 seconds for runs >15min (long-running tool contract).
- **Exit codes:** 0 on success, non-zero on any failure.
- **Determinism:** honors `torch.use_deterministic_algorithms(True)` if hparams request it.
- **Lazy weight fetch:** uses `huggingface_hub.snapshot_download()`; never bundles weights.

If any of these is missing, surface as P0 — recipe contract drift breaks every downstream skill.

### Step 3: Attacker condition coverage (if B or D and attacker-related)

VP2026 defines three attacker conditions: `ignorant`, `lazy_informed`, `semi_informed`. The official ranking attacker is `semi_informed`. Check:

- Does the design support all three conditions, or only one? **Single-condition attackers are a P1 finding** — paper reviewers will ask about robustness across conditions.
- For semi_informed: is the design fine-tuning ECAPA-TDNN on anonymized train-clean-360, per the VP2024 Eval Plan?
- "Fully informed" / Attacker Challenge style: NOT a VPC official condition — if the design claims this, flag and ask if user means semi_informed or an open Attacker Challenge submission.

### Step 4: Reproducibility design review (always)

Walk through the 5 reproducibility checks BEFORE the code is written:

1. **Seed pinned?** Does the design specify a single integer seed in hparams? Not "auto", not list-of-seeds-without-aggregation, not derived from time.
2. **Splits explicit?** train/dev/test paths are concrete (LibriSpeech-train-clean-360, VP2026 trial list v...). Not "auto-detect from directory".
3. **Checkpoint hashes?** Does the design include a `checkpoints.lock` file with SHA256 of every pretrained model fetched at install/runtime?
4. **Hparams completeness?** Are all hparams declared with concrete values? (Will the implementer be tempted to leave `TODO` placeholders?)
5. **Determinism strategy?** `torch.use_deterministic_algorithms(True)` OR `n_seeds >= 3`. Address CUDA non-determinism in the design now, not after the first reproducibility bug report.

Each gap → P0 finding. Reproducibility is the correctness story; design-time gaps are 10x cheaper than post-hoc fixes.

### Step 5: Eval-set safety review

If the design touches evaluation:

- **Held-out test split:** does the design accidentally let test data leak into training? Common mistakes: training ASR on dev+test pooled, fine-tuning vocoder on dev set, evaluating on dev WHILE selecting hparams on dev.
- **Cross-gender (VP2026):** does the eval report Mixed-gender EER (F-F + M-M + F-M + M-F)? VP2026 specifies this explicitly per Eval Plan §7.1.
- **Per-language (Track 2):** if Track 2 work, does the design cover French/English/Spanish/German + IEMOCAP for emotion?

### Step 6: License posture review

Critical for any recipe / attacker design that fetches code or models:

- **VP2024 GitHub code:** the canonical baselines repo at `Voice-Privacy-Challenge/Voice-Privacy-Challenge-2024` is **GPLv3**. Any design that imports / vendors / copies from it forces vpstack itself to GPLv3 (viral). **P0 BLOCKER.** Re-implement from the published Eval Plan PDF instead.
- **Model weights:** does the design ship model weights with the recipe? Don't. Lazy-fetch from HuggingFace Hub at runtime per `LICENSING.md`.
- **Datasets:** does the design bundle VoxCeleb / IEMOCAP / VP2026 trial lists? Don't. Use LibriSpeech (CC-BY 4.0) for fixtures only.
- **New dependency:** does any new pretrained model have a non-permissive license (CC-BY-NC, GPL, etc.)? Audit before locking the design.

### Step 7: Recipe-specific architecture review

For recipe designs, the canonical components and tradeoffs:

| Component | Canonical default | Tradeoff |
|---|---|---|
| Content encoder | HuBERT-base layer 7-9 (per Pasad et al. ASRU 2021) | Earlier layers leak speaker; layer 12 is content-leaning |
| Speaker representation | ECAPA-TDNN (speechbrain/spkrec-ecapa-voxceleb) | VoxCeleb training data — caveat for production deployment |
| Anonymization strategy | Farthest-point selection | vs random target — better disentanglement, slight time cost |
| Vocoder | HiFi-GAN (jik876, MIT) fine-tuned on LibriTTS | Universal v1 weights are MIT, fine-tune output also MIT |

If the design diverges from a canonical default, ask why. "Vibes" is not a reason — cite a published comparison or run a `/vp-component-tradeoff` (post-v0.1).

### Step 8: Synthesize findings

Group findings by severity:

- **P0 (BLOCKING):** GPLv3 import, missing seed pin, recipe contract drift, eval-set safety violation, semi-informed condition missing
- **P1 (should fix before code):** single-condition attacker, hparams placeholder risk, checkpoint hash missing, license-acceptance prompt missing for non-permissive models
- **P2 (note in plan):** style / clarity / missing tradeoff justification

Write to `~/.vpstack/projects/{slug}/design-reviews/{date}-{type}.md`:

```markdown
# Design Review: {what was reviewed}
Date: {ISO 8601}
Status: APPROVED / NEEDS_REVISION / BLOCKED

## Findings
### P0 (blocking)
- [file:line / design section] — issue — fix

### P1 (should fix)
- ...

### P2 (note)
- ...

## Verdict
{paragraph: ready to /vp-implement, needs revision, or fundamentally re-think}
```

### Step 9: Suggest next step

- All P0 resolved → `/vp-implement` to start coding
- P0 outstanding → revise the design and re-run `/vp-plan-design-review`
- Fundamental issues (e.g., GPLv3 contamination) → back to `/vp-talk` to re-think direction

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-plan-design-review \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

## Completion status

- DONE — review complete, design doc written, verdict APPROVED or NEEDS_REVISION clearly marked
- DONE_WITH_CONCERNS — review complete but design has P1 issues user opted to defer
- BLOCKED — design has P0 issue that requires user re-think (e.g., GPLv3 contamination)
