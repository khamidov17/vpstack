# vpstack

> Voice-privacy research infrastructure for AI coding agents.

vpstack gives AI agents — Claude Code, Codex, Cursor — the domain knowledge and workflow automation they need for VoicePrivacy 2026. They stop hallucinating baseline numbers. They know what EER means and which direction is better. They run the right attacker condition. They check reproducibility before you submit.

**Zero code in the repo.** Skills are markdown. Bash is the executor. Claude is the intelligence.

**Auto-activates on voice-anonymization projects. Silent everywhere else.**

---

## How it works

```
You:    My content encoder is HuBERT layer 12. I want to test layer 6.

You:    /vp-hypothesis

Claude: [7 questions: what changes, which baseline, acceptance criteria, magnitude]
        "Domain note: Layer 6 is pre-content peak — some phonetic + residual speaker.
         Layers 7–9 are the phonetic content peak per Pasad et al. (ASRU 2021).
         Your hypothesis is consistent with standard VP2026 disentanglement practice."
        → Writes ~/.vpstack/projects/my-system/hypotheses/20260429-hubert-l6-test.md
```

```
You:    /vp-spike

Claude: "Note: anonymization will run but EER/WER scoring is not yet wired.
         You'll get anonymized audio + output paths. Run /vp-attack for privacy numbers."
        You: proceed

        [writes /tmp/vp_b1_run.py, runs 3 alpha variants]

        | Variant   | Files anonymized | Output            |
        | layer-6   | 847 WAV files    | /data/anon_l6/    | INCONCLUSIVE (eval pending)
        | layer-9   | 847 WAV files    | /data/anon_l9/    | INCONCLUSIVE (eval pending)
        | layer-12  | 847 WAV files    | /data/anon_l12/   | INCONCLUSIVE (eval pending)

        → Run /vp-attack to get EER for each variant
```

```
You:    /vp-attack

Claude: Which condition? semi-informed is the VP2026 ranking metric (~4-12h GPU).
You:    lazy-informed first, 10 minutes.

Claude: [runs attacker, streams progress to terminal]

        VP2026 Attacker Results — lazy_informed condition
        ─────────────────────────────────────────────────
        EER overall:  38.2%    (↑ = more private, 50% = random)
        EER female:   40.1%
        EER male:     36.3%
        Linkability:   0.38

        vs B1 reference: run /vp-baseline-compare to populate
        → Run semi-informed before citing this number in a paper
```

```
You:    /vp-repro-check

Claude: [runs 5 bash checks on your config]

        Reproducibility check: PASS_STRONG
        ✓ seed pinned: 42
        ✓ splits: explicit (VP2026 dev-clean trial list v2026.03.17)
        ✓ checkpoints: 3/3 hash-verified against checkpoints.lock
        ✓ hparams: no placeholder values
        ✓ determinism: torch_deterministic: true

        PASS_STRONG: this experiment reproduces exactly given the same hardware.
```

```
You:    /vp-ship

Claude: [runs pytest, repro-check, checks deferred gates]

        Tests: 23 → 27 (+4 new regression tests)
        Repro: PASS_STRONG
        Deferred gates: 0
        VERSION: 0.2.0-dev → 0.2.1-dev

        Commit: abc1234 — "feat: HuBERT layer ablation experiment + repro-verified results"
        PR: github.com/you/vp2026-system/pull/7
```

That's one complete experiment cycle. Hypothesis → spike → attack → repro-check → ship. Every skill knows VP2026. None of them hallucinate baseline numbers.

---

## Install

### Claude Code

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
```

Restart Claude Code. Open a voice-anonymization project. Type `/vp-hypothesis`.

vpstack auto-activates on voice-anonymization projects (detects `VP2026`, `voice-anonymization`, `speechbrain`, British spelling `anonymisation`, and more). Silent everywhere else.

### Codex

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
```

Copy `AGENTS.md` from this repo into your voice-anonymization project root. Codex reads it for domain context.

```bash
cp ~/.claude/skills/vpstack/AGENTS.md /path/to/your/vp2026-project/AGENTS.md
```

Skills don't auto-invoke in Codex — follow the steps in `skills/*/SKILL.md` manually or tell Codex to follow them.

### Cursor

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
```

Copy the `.cursor/rules` file from this repo into your voice-anonymization project:

```bash
mkdir -p /path/to/your/vp2026-project/.cursor
cp ~/.claude/skills/vpstack/.cursor/rules /path/to/your/vp2026-project/.cursor/rules
```

Or copy `docs/claude-md-template.md` into your project's CLAUDE.md for full domain context.

In Cursor Composer, open the relevant `skills/*/SKILL.md` in the sidebar and follow steps inline.

### All clients — add domain context to your project

```bash
# In your voice-anonymization project root:
cat ~/.claude/skills/vpstack/docs/claude-md-template.md >> CLAUDE.md
```

This gives Claude/Codex/Cursor the VP2026 domain facts (metric directions, baseline notes, component tradeoffs, common mistakes) upfront — so it stops asking you what EER means.

---

## Skills

| Skill | What it does |
|---|---|
| `/vp-talk` | Threat model, research framing, contribution scope |
| `/vp-hypothesis` | Formalize an experiment — 7 questions, structured doc |
| `/vp-spike` | Run 1–3 B1 ablation variants, get CONFIRMED/REFUTED/INCONCLUSIVE |
| `/vp-baseline-compare` | B1 baseline + delta table (B2 pending v0.3) |
| `/vp-attack` | ASV attacker — ignorant / lazy-informed / semi-informed |
| `/vp-eval` | Full VP2026 scorecard (wired in v0.3) |
| `/vp-repro-check` | PASS_STRONG / PASS_WEAK — seeds, splits, checkpoint hashes |
| `/vp-implement` | 14-step dev workflow with license + repro gates |
| `/vp-investigate` | Domain-specific debugging — "my EER looks wrong" |
| `/vp-writeup` | Engineering report from experiment logs. No LLM citations. |
| `/vp-qa` | QA pass: repro + attacker smoke + submission format |
| `/vp-ship` | Version bump + repro gate + deferred gate check + PR |
| `/vp-plan-eng-review` | 18 VP-specific engineering gates |
| `/vp-plan-design-review` | Architecture review before implementation |
| `/vp-autoplan` | Chains all skills end-to-end |

---

## What's implemented

| Component | Status |
|---|---|
| B1 McAdams anonymization | ✅ Working — inline script, CPU, ~5min |
| All 15 skills | ✅ Complete markdown workflows |
| Experiment logging | ✅ `~/.vpstack/projects/{slug}/experiments/` |
| Reproducibility check (PASS_STRONG / PASS_WEAK) | ✅ |
| Activation gate | ✅ Auto-detects VP2026 projects |
| Claude Code | ✅ Full skill invocation |
| Codex | ✅ AGENTS.md context + manual skill steps |
| Cursor | ✅ `.cursor/rules` + SKILL.md in Composer |
| B2 neural baseline | ⏳ v0.3 |
| Full eval pipeline (EER + WER) | ⏳ v0.3 |
| ASV attacker recipe | ⏳ v0.3 (requires official VP2026 scripts) |

---

## Domain knowledge

Everything Claude needs to know about VP2026 lives in `docs/domain.md`:
- Metric directions and what "good" looks like
- Component tradeoffs (HuBERT layers, ECAPA-TDNN, HiFi-GAN, McAdams)
- Known component failure modes and common pitfalls
- checkpoints.lock format for hash-verified reproducibility
- VP2026 submission format requirements

---

## License

Apache 2.0. Do NOT import VP2024 baseline code — it's GPLv3. Implement from the [VP2024 Eval Plan PDF](https://inria.hal.science/hal-04531444v1/) instead.
