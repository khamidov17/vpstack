# vpstack

> Voice-privacy research infrastructure for AI coding agents — Claude Code, Codex, Cursor, Claude Desktop.

**If you don't work on voice anonymization, this isn't for you.** vpstack auto-activates on voice-privacy projects and stays completely silent everywhere else.

For researchers in the voice-privacy field: vpstack encodes domain knowledge for [VoicePrivacy 2026](https://www.voiceprivacychallenge.org/) (and VP2024 ports planned) — reproducible B1/B2 baselines, official-conformant ASV attackers, full eval (EER + WER + linkability + side-channels), and reproducibility checks — so AI agents stop hallucinating SpeechBrain conventions and inventing baseline numbers. Cite "evaluated with vpstack 0.1.0" the way you cite "trained with SpeechBrain 1.0".

**Challenges supported:** VP2026 (in progress). VP2024 baseline ports planned for v0.2.

**Status: 0.1.0-dev — pre-release.** The packages are not yet on npm/PyPI. Install from source for now (instructions below). APIs may change before v0.1.0.

---

## Install

### From source (current — 0.1.0-dev)

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
```

That puts the 6 skills + 7 bin scripts where Claude Code expects them. Restart Claude Code and try `/vp-baseline-compare` in a voice-anonymization project.

For the MCP server (Claude Desktop / Cursor / Codex):

```bash
cd ~/.claude/skills/vpstack/mcp-server && pip install -e .
```

Then point your MCP client at the `vpstack-mcp` console script.

For the SpeechBrain recipe:

```bash
cd ~/.claude/skills/vpstack/speechbrain_voice_anon && pip install -e .
```

### After v0.1.0 publish

Once the packages are on the registries (target: when B2 baseline reproducibility lands), install via:

```bash
npx vpstack@latest                    # skills + bin
pip install vpstack-mcp               # MCP server only
pip install speechbrain-voice-anon    # recipe only
```

The installer auto-detects which AI coding agent you have (Claude Code, Codex, Cursor, Cline) and installs accordingly.

---

## Quick Start

In a voice-anonymization project, just type `/vp-baseline-compare` in Claude Code. vpstack detects the project, asks once whether to enable, then runs B1 + B2 + your system and returns a delta table:

```
EER (lower=better)    B1     B2     yours    Δ vs B1
                      14.2   12.3   11.1     -3.1
WER (lower=better)    8.4    8.1    8.0      -0.4
Linkability           0.45   0.42   0.39     -0.06
```

(*Numbers above are illustrative — your actual numbers will differ.*)

In an unrelated project, vpstack stays completely silent — no prompts, no output, nothing.

---

## Skills reference

Type these in Claude Code (or your MCP-aware agent of choice). Each skill writes its artifacts to `~/.vpstack/projects/{slug}/` and logs to opt-in telemetry if enabled.

### `/vp-hypothesis` — Formalize an experiment before code runs

> Researcher: *"I want to test if HuBERT layer 6 gives better anonymization than layer 12."*

vpstack walks them through 7 questions: hypothesis text, component changed, baseline, expected metric direction, expected magnitude, acceptance criteria, components held constant. Writes a structured doc to `~/.vpstack/projects/{slug}/hypotheses/{id}.md`. The doc is what you refer back to when interpreting results — it stops "I'll know it when I see it" experiments before they consume GPU time.

```
/vp-hypothesis
→ "What's the hypothesis?"
→ "Replacing HuBERT layer 12 with layer 6 improves EER by ≥0.5pp without WER regression."
→ ... 6 more questions ...
→ Writes ~/.vpstack/projects/my-vp-system/hypotheses/20260428-141503-replacing-hubert-layer-12.md
→ "Hypothesis logged. Next: run /vp-spike to test it."
```

### `/vp-spike` — Run 1–3 focused ablations with given/when/then verdicts

> Researcher: *"Run my hypothesis as 3 variants: layer 6, layer 9, layer 12."*

Time-boxed ablation runner. Loads the hypothesis (if you ran `/vp-hypothesis` first), prompts for 1–3 variants, runs each on the dev set, returns a verdict per variant (CONFIRMED / REFUTED / INCONCLUSIVE). Replaces ad-hoc "I'll just try a few things" with a structured trace.

```
/vp-spike
→ Found hypothesis: "Replacing HuBERT layer 12..."  Use it?
→ How many variants?  3 (three-way)
→ Variant 1: name="layer-6"  config: hparams.content_encoder.layer_idx=6
→ Variant 2: name="layer-9"  config: hparams.content_encoder.layer_idx=9
→ Variant 3: name="layer-12" config: hparams.content_encoder.layer_idx=12
→ ETA: 3 × 45min = 2h15min on a single GPU. Continue?
→ ... runs ...
→ | Variant   | EER | WER | Verdict     |
  | layer-6   | 11.1 | 8.0 | CONFIRMED   |
  | layer-9   | 11.8 | 8.1 | CONFIRMED   |
  | layer-12  | 12.3 | 8.0 | REFUTED     |
→ Hypothesis confirmed: layer 6 < layer 9 < layer 12 EER. Decision: ship layer-6.
```

### `/vp-baseline-compare` — How does my system stack up against B1 and B2?

> Researcher: *"Quick check — am I beating the strong baseline?"*

The daily-use skill. Runs B1 (McAdams) + B2 (neural) on the same eval set as your system, returns a delta table. Run after every meaningful change to know if you're improving against the canonical references.

```
/vp-baseline-compare
→ Which system?  Path to anonymized audio: ~/work/vp2026/anon-output/
→ Running B1 (~5min) + B2 (~45min) + scoring your system (~20min)...
→ | Metric              | B1    | B2    | yours | Δ vs B2 |
  | EER (lower=better)  | 14.2  | 12.3  | 11.1  | -1.2    |
  | WER (lower=better)  |  8.4  |  8.1  |  8.0  | -0.1    |
  | Linkability         |  0.45 |  0.42 |  0.39 | -0.03   |
→ You beat B2 on EER. Suggest /vp-eval --official for a full submission scorecard.
```

### `/vp-attack` — Run an ASV attacker against my anonymized output

> Researcher: *"Did I actually hide the speaker, or am I fooling myself?"*

The privacy skill. Runs an ASV attacker (the official VP2026 semi-informed ECAPA-TDNN by default) against your anonymized output and reports the EER an attacker would achieve when trying to re-identify the original speaker. **A defense without an attacker run is unfalsifiable** — this is the central privacy question.

Three official VPC conditions: `ignorant` (~5min sanity floor), `lazy_informed` (~10min, pretrained ECAPA + anonymized enrollment), `semi_informed` (~4–12h, ECAPA retrained on your anonymized train-clean-360 — the official ranking attacker).

```
/vp-attack
→ Which anonymized output?  ~/work/vp2026/anon-output/
→ Attacker condition?  semi-informed (recommended, official ranking)
→ Note: this anonymizes train-clean-360 (~360h audio) then trains ECAPA. ETA: 8h. Continue?
→ ... runs ...
→ VP2026 Attacker Results
  Condition: semi_informed
  | Metric                  | Female | Male  | Overall |
  | EER % (higher = better) | 38.2   | 35.7  | 36.9    |
  | Linkability (Cllr)      | 0.41   | 0.43  | 0.42    |
  Reference points:  B1: 34.8  B2: 28.1  Random: 50.0
  Verdict: privacy delta vs B2 = +8.8 EER (your system is harder to attack)
→ Suggest /vp-eval --official for the full submission scorecard.
```

### `/vp-eval` — Full VP2026 evaluation pipeline

> Researcher: *"I'm submitting to the challenge — give me the complete scorecard."*

The submission-prep skill. Runs the full VP2026 protocol: per-gender EER under all attacker conditions, WER, linkability, side-channel scores (age / pitch / emotion preservation). Validates submission format. Distinct from `/vp-baseline-compare` (which is the daily quick check) — `/vp-eval` is the publication-grade run.

```
/vp-eval --official
→ Confirms held-out 'test' split usage (blocks accidental overfitting)
→ Runs all 3 attacker conditions + WER + side-channels (~12h on single GPU)
→ Validates submission directory layout
→ Outputs: ~/.vpstack/projects/{slug}/experiments/{id}/submission/
→ "Submission validation: PASS. Ready to upload to voiceprivacychallenge.org."
```

### `/vp-repro-check` — Will my numbers reproduce?

> Researcher: *"My collaborator can't reproduce my EER. What's wrong?"*

Validates that an experiment can be reproduced. Checks: pinned seed, explicit dataset splits, hash-verified model checkpoints, complete hparams (no `TODO` placeholders), deterministic mode. Returns PASS or FAIL with specific reasons. Catches silent drift before it costs you a submission rejection.

```
/vp-repro-check
→ Most recent experiment? exp-2026-04-28-141503
→ Reproducibility check: FAIL
  ✗ seed: missing — config has no 'seed' key
  ✗ checkpoints: hifigan_anon hash mismatch (expected sha256:abc..., got sha256:def...)
  Other items (passed): splits, hparams, determinism
  Fix the marked issues and re-run /vp-repro-check.
```

**Limitation:** does NOT track vpstack version itself — that's a deliberate tradeoff per DESIGN.md. Record vpstack version in your lab notebook.

### `/vp-writeup` — Generate an internal experiment report

> Researcher: *"Pull together what we did this week so I can show my advisor."*

Generates a structured engineering log from your `~/.vpstack/projects/{slug}/` artifacts: methods, hyperparameters, results table, config hash. **Does NOT generate citations or research-paper prose** — that's the researcher's job. Produces a Markdown report you can paste into your notes, share with a labmate, or attach to a PR.

```
/vp-writeup
→ Which experiments?  Most recent 5
→ Generates ~/.vpstack/projects/{slug}/reports/report-20260428.md
  with: methods table, hparams dump, results table, config hashes, repro status.
  No abstract. No related work. No citations.
```

This decision was deliberate: LLM-generated citations hallucinate, and a wrong citation in someone's published paper is exactly the harm vpstack's correctness bar forbids.

---

## MCP tools reference

These are the tools the MCP server (`vpstack-mcp`) exposes to any MCP-aware agent. Skills call them; advanced users can call them directly.

| Tool | Returns | Cost | What it does |
|---|---|---|---|
| `vp_run_baseline(baseline, data_path, seed)` | `{eer, wer, linkability, config_hash}` | B1: ~5min CPU. B2: ~45min GPU. | Run canonical B1 (McAdams) or B2 (neural) baseline. |
| `vp_run_eval(system_path, eval_set, seed, official_test)` | full scorecard | ~12h GPU for full run | Full VP2026 eval pipeline (currently stubbed pending B2). |
| `vp_run_attacker(anonymized_path, ..., attacker_condition)` | per-gender EER + Cllr | semi-informed: 4–12h GPU | Run ASV attacker. Three VPC conditions supported. |
| `vp_check_submission(submission_path)` | `{valid, errors, warnings}` | <1s | Validate submission directory format before upload. |
| `vp_check_reproducibility(config_path)` | `{status, issues, passed}` | <1s | Check if config is reproducible (5 criteria). |
| `vp_get_component_info(component_name)` | `{description, tradeoffs, papers, license}` | <1s | Look up tradeoff info for a known component. |
| `vp_search_experiments(query, limit)` | matching experiments | <1s for 1k experiments | Search logged experiments by substring match. |
| `vp_log_experiment(exp_id, metrics, config_hash)` | `{logged, path}` | <100ms | Atomically log an experiment (no half-state on kill -9). |

Every tool returns the same structured contract: `{"ok": bool, "result": Optional[Dict], "error": Optional[{"code": str, "message": str, "hint": str}]}`. Error codes are from a strict allowlist defined in `mcp-server/vpstack_mcp/errors.py`.

---

## Typical session walkthrough

What a researcher's first VP2026 work session with vpstack looks like:

```
$ cd ~/work/vp2026-my-system
$ # First time using vpstack here — first-run prompt fires once

Claude Code> /vp-hypothesis
  → answers 7 questions about the experiment they want to run
  → ~/.vpstack/projects/vp2026-my-system-{hash}/hypotheses/20260428-...md written

Claude Code> /vp-spike
  → "Found hypothesis. Use it?  Yes."
  → 3 variants run on dev set, ~2h15min on single GPU
  → spike doc written, hypothesis updated with verdict

Claude Code> /vp-baseline-compare
  → quick "did I beat B2?" check, ~70min on GPU
  → delta table printed

Claude Code> /vp-attack --condition lazy_informed
  → 10-minute sanity check: does even a weak attacker re-identify?
  → if EER below 30, suggest /vp-spike to ablate

Claude Code> /vp-attack --condition semi_informed
  → 8h overnight run with the official ranking attacker
  → wakes up to a privacy-vs-utility scorecard

Claude Code> /vp-repro-check
  → verify the run is reproducible before sharing or submitting
  → PASS / FAIL with specific reasons

Claude Code> /vp-eval --official
  → full submission scorecard, ~12h
  → submission directory ready to upload

Claude Code> /vp-writeup
  → engineering log for advisor / labmate / PR
  → no citations, just structured facts from logs
```

In an unrelated project (Rails, Go CLI, NLP repo with no voice signals), none of these skills surface. vpstack stays silent.

---

## What's in v0.1

| Component | Purpose |
|---|---|
| **7 Claude Code skills** | `/vp-hypothesis`, `/vp-spike`, `/vp-baseline-compare`, `/vp-attack`, `/vp-eval`, `/vp-repro-check`, `/vp-writeup` |
| **MCP server** | 8 tools for any MCP-aware agent: `vp_run_baseline`, `vp_run_eval`, `vp_run_attacker`, `vp_check_submission`, `vp_check_reproducibility`, `vp_get_component_info`, `vp_search_experiments`, `vp_log_experiment` |
| **SpeechBrain recipe** | Reference implementations of B1 (McAdams — implemented), B2 (HuBERT + ECAPA + HiFi-GAN — stub), stronger starters, and the ASV attacker recipe |
| **Auto-activation** | Detects voice-anonymization projects via heuristic + first-run prompt + explicit override |
| **Auto-update** | Preamble version check, user always confirms upgrade |
| **Opt-in telemetry** | Three modes (off / anonymous / community); never sends code, paths, or research data |

---

## Give your AI agent voice-anon context (recommended)

When you enable vpstack in a project, drop the domain-context template into your project's `CLAUDE.md` so any AI agent (Claude Code, Codex, Cursor) has the right priors immediately:

```bash
# In your voice-anonymization project root, after enabling vpstack:
cat ~/.claude/skills/vpstack/docs/claude-md-template.md >> CLAUDE.md
# Then edit the <TODO: ...> section at the top to describe your specific project.
```

The template gives the agent: VP2026 metric directions (privacy = HIGHER EER, utility = LOWER WER), canonical baselines, attacker conditions, dataset conventions, model licenses, and routing rules ("when user asks X, use vpstack skill Y instead of writing a one-off script"). Without this, agents tend to invent SpeechBrain conventions or hallucinate baseline numbers; with it, they stay on-rails.

See [docs/claude-md-template.md](docs/claude-md-template.md) for the full template.

---

## Documentation

- [CLAUDE.md](CLAUDE.md) — context for AI agents working IN this repo (contributing to vpstack itself)
- [docs/claude-md-template.md](docs/claude-md-template.md) — context to drop into YOUR voice-anon project's CLAUDE.md
- [DESIGN.md](DESIGN.md) — full architecture and design decisions
- [TEST-PLAN.md](TEST-PLAN.md) — 73 tests, 7 critical CI gates
- [LICENSING.md](LICENSING.md) — license audit and redistribution posture
- [docs/quick-start.md](docs/quick-start.md) — getting started in 30 minutes
- [docs/activation.md](docs/activation.md) — how auto-activation works
- [docs/telemetry.md](docs/telemetry.md) — what gets sent, what doesn't

---

## License

Apache 2.0. See [LICENSE](LICENSE) and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

## Contributing

vpstack is built for the VP2026 research community. Issues, PRs, and feedback all welcome. The bar is correctness — wrong baseline numbers propagate to citations, so we hold the recipe to a higher standard than mass-market dev tools.
