# vpstack

> Voice-privacy research infrastructure for AI coding agents.

**If you don't work on voice anonymization, this isn't for you.** vpstack auto-activates on voice-privacy projects and stays completely silent everywhere else.

For researchers in the voice-privacy field: vpstack gives AI agents (Claude Code, Codex, Cursor) the domain knowledge and workflow automation they need for VoicePrivacy 2026 — so they stop hallucinating baseline numbers and inventing SpeechBrain conventions.

**Architecture:** Pure markdown skills + bash. No MCP server. No Python packages to install beyond the actual ML dependencies you already need. Claude is the intelligence; the recipe scripts are the executor.

**Status: v0.2.0-dev — pre-release.** Install from source.

---

## Install

```bash
# 1. Clone skills + bin scripts
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*

# 2. Install the SpeechBrain recipe (B1 McAdams baseline)
cd ~/.claude/skills/vpstack/speechbrain_voice_anon && pip install -e .

# 3. (Optional) Restart Claude Code and open a voice-anonymization project
```

That's it. No MCP server. No additional config. Restart Claude Code and type `/vp-baseline-compare` in a voice-anonymization project.

### For Codex

Copy `AGENTS.md` from this repo into your voice-anonymization project root. It gives Codex the same domain context Claude gets automatically.

### For Cursor

Add the `docs/claude-md-template.md` content to your project's `.cursorrules` or CLAUDE.md.

---

## How It Works

vpstack skills are markdown files that tell Claude exactly what to do. When you run `/vp-baseline-compare`, Claude reads the skill and follows it step by step: runs bash commands, interprets output, asks you questions, logs results. No intermediate layer.

```
You → /vp-baseline-compare → Claude reads SKILL.md →
  Claude runs: python3 -m speechbrain_voice_anon.recipes.VP2026.baseline_B1.run --data_path ...
  Claude reads: stdout JSON
  Claude shows: comparison table
  Claude writes: ~/.vpstack/projects/{slug}/experiments/{id}/summary.json
```

All experiment state lives in `~/.vpstack/projects/{slug}/`. Skills write there using the Write tool directly. No database, no server, no daemon.

---

## Skills

Type these in Claude Code (or any AI agent with the skills installed).

| Skill | When to use |
|---|---|
| `/vp-hypothesis` | Formalize an experiment before running anything |
| `/vp-spike` | Run 1-3 quick variants, get CONFIRMED/REFUTED/INCONCLUSIVE verdicts |
| `/vp-baseline-compare` | "Am I beating B1?" — runs B1 + shows delta table |
| `/vp-attack` | Run ASV attacker (ignorant / lazy-informed / semi-informed) |
| `/vp-eval` | Full VP2026 scorecard (B1 anonymization + attacker; full eval pipeline pending) |
| `/vp-repro-check` | Verify seeds, splits, checkpoint hashes before submission |
| `/vp-implement` | Implement a recipe with license + repro + test gates |
| `/vp-investigate` | Domain-aware debugging: "my EER looks wrong" |
| `/vp-writeup` | Internal experiment report from logged data (no LLM citations) |
| `/vp-talk` | Research planning — threat model, contribution claim, open questions |
| `/vp-ship` | Ship with VP-specific gates (attacker smoke, repro check, submission format) |
| `/vp-qa` | Multi-tier QA of anonymization system + codebase |
| `/vp-plan-eng-review` | Engineering review with 18 VP-specific quality gates |
| `/vp-plan-design-review` | Design review for recipe architecture |
| `/vp-autoplan` | Chain hypothesis → spike → baseline-compare end-to-end |

---

## What's Implemented vs Pending

| Component | Status |
|---|---|
| B1 McAdams baseline (anonymization) | ✅ Implemented |
| B2 neural baseline (HuBERT+ECAPA+HiFi-GAN) | ⏳ Pending v0.3 |
| ASV attacker (all 3 conditions) | ✅ Implemented (recipe structure; needs GPU + VP2026 data) |
| Full eval pipeline (EER + WER + linkability) | ⏳ Pending v0.3 |
| All 15 skills | ✅ Markdown complete |
| Experiment logging | ✅ (Write tool → ~/.vpstack/) |

---

## Typical Session

```
$ cd ~/work/vp2026-my-system
# First time: vpstack asks once whether to activate here

Claude Code> /vp-hypothesis
  → 7 questions about your experiment
  → Writes ~/.vpstack/projects/{slug}/hypotheses/{id}.md

Claude Code> /vp-spike
  → Runs 3 B1 variants via bash, reads JSON output
  → Returns CONFIRMED / REFUTED / INCONCLUSIVE per variant

Claude Code> /vp-baseline-compare
  → Runs B1, builds delta table
  → "Your system shows stronger privacy than B1."

Claude Code> /vp-attack --condition semi_informed
  → Runs attacker recipe, reads EER from stdout
  → "semi-informed EER: 38.2% — above random, privacy holds"

Claude Code> /vp-repro-check
  → bash grep checks on your config YAML
  → PASS / FAIL with specific reasons

Claude Code> /vp-writeup
  → Reads your experiment JSONs, generates structured report
  → No citations (LLM citations hallucinate — deliberately excluded)
```

---

## Project State

Logged experiments live at `~/.vpstack/projects/{slug}/experiments/`. Each is a directory with `summary.json`. Browse them:

```bash
ls ~/.vpstack/projects/$(~/.claude/skills/vpstack/bin/vpstack-slug)/experiments/
cat ~/.vpstack/projects/$(~/.claude/skills/vpstack/bin/vpstack-slug)/experiments/b1-reference/summary.json
```

No dashboard, no server. Raw filesystem. Skills read these files directly via bash.

---

## Domain Knowledge

The full VP2026 domain reference (metrics, components, attacker conditions, common mistakes) lives at [`docs/domain.md`](docs/domain.md). Claude reads this when skills invoke it. You can also append it to your project's CLAUDE.md for richer context.

---

## License

Apache 2.0. Never import or vendor VP2024 GPLv3 code. Implement from the [VP2024 Eval Plan PDF](https://inria.hal.science/hal-04531444v1/) instead.
