# CLAUDE.md — Context for AI agents working IN this repo

This file gives Claude Code / Codex / Cursor / any AI agent the conventions it needs to make sane edits inside the vpstack repo itself.

For context that gets injected into a *user's* voice-anonymization project (not this repo), see [docs/claude-md-template.md](docs/claude-md-template.md).

---

## What this repo is

vpstack is **voice-privacy research infrastructure for AI coding agents**. It encodes domain knowledge for VoicePrivacy 2026 (and VP2024 ports planned) so AI agents stop hallucinating SpeechBrain conventions and inventing baseline numbers.

**Read first if you're editing anything substantial:**
- [DESIGN.md](DESIGN.md) — full architecture with 7 locked premises (P1–P7) and explicit non-goals
- [LICENSING.md](LICENSING.md) — license posture (Apache 2.0, runtime model downloads only, **NO vendoring of VP2024 GPLv3 code**)
- [TEST-PLAN.md](TEST-PLAN.md) — 7 critical CI gates

---

## Architecture in one paragraph

`bin/` is bash scripts (orchestration primitives). `skills/vp-*/SKILL.md` are markdown workflows — Claude reads them and executes bash commands. No MCP server. No Python code in the repo. Skills tell Claude what commands to run; Claude is the intelligence; bash is the execution layer. This is the gstack pattern applied to voice-privacy research. State is written to `~/.vpstack/projects/{slug}/` via the Write tool directly.

---

## Non-negotiable rules

1. **Never `import` or vendor anything from `Voice-Privacy-Challenge-2024`** (GPLv3). Re-implement from the published Eval Plan PDF instead.
2. **Never write Python code in this repo.** Skills are markdown. `bin/` is bash. No MCP server. No Python packages. Zero code in skills. (Note: bash scripts in `bin/` may use inline Python for computation).
3. **Never bundle pretrained model weights.** Users download at runtime via HuggingFace Hub or SpeechBrain.
4. **Never bundle VP2026 trial lists / VoxCeleb audio / IEMOCAP.**
5. **Telemetry payload is a strict allowlist.** Only keys in `bin/vpstack-telemetry-log` are permitted. Never add keys without updating the allowlist.
6. **VP2026 metrics only.** Do not reference VP2020/VP2022/VP2024 numbers as targets. Run baselines on user's actual VP2026 data.
7. **domain_config.yaml is written by /vp-talk engineering mode.** Every skill preamble reads it and adapts behavior (sample rate warnings, compliance checks, method context). Never hardcode domain assumptions in skills.

---

## Where things live

| What | Where | Notes |
|---|---|---|
| Bash CLI primitives | `bin/` | All chmod +x. Each self-documents via `--help`. |
| Skill workflows | `skills/vp-{name}/SKILL.md` | Markdown. Frontmatter: `name`, `version`, `description`, `allowed-tools`. Self-contained preamble — never reference another skill's preamble. |
| Domain knowledge | `docs/domain.md` | VP2026 metrics, component tradeoffs, known issues, bash commands. Read by Claude in every session. |
| User config | `~/.vpstack/config.json` | Managed by `bin/vpstack-config`. |
| Per-project state | `~/.vpstack/projects/{slug}/` | `domain_config.yaml`, `hypotheses/`, `experiments/`, `research-plans/`, `deferred-gates.jsonl` |
| Per-project markers | `<repo>/.vpstack/` | `enabled`, `disabled`, `ask-later` — tiny activation markers |
| Automated tests | `tests/` | Python/pytest smoke tests for binaries. |

---

## AskUserQuestion convention

Every decision point in a skill must use this format:

```
> **Question title**
>
> A) Option one — short description
> B) Option two — short description
>
> Recommendation: A, because [one-line reason].
> Trade-off: [what A gains vs what B gains — one sentence if non-obvious].
```

The `Recommendation:` line is mandatory. Users need to know the right answer, not just the options. Omit `Trade-off:` if the choice is obvious.

---

## Common tasks

### Add a new skill

1. Create `skills/{skill_name}/SKILL.md`. Copy the frontmatter + preamble from `skills/vp-baseline-compare/SKILL.md` (canonical template). Every skill is self-contained — never reference another skill's preamble.
2. Preamble must call `vpstack-skill-init` with the absolute path. Skills can pass their name as `$1` for timeline logging: `eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init vp-{name} 2>/dev/null || ...)"`.
3. Telemetry tail must call `vpstack-telemetry-log` with absolute path.
4. Log skill start to timeline in preamble (background): `~/.claude/skills/vpstack/bin/vpstack-timeline-log "{...}" 2>/dev/null &`
5. Log confirmed findings to learnings at the end: `~/.claude/skills/vpstack/bin/vpstack-learnings-log "{...}" 2>/dev/null`
6. Update README skills table and CHANGELOG.

### Add a new skill

1. Create `skills/{skill_name}/SKILL.md`. Copy the frontmatter + preamble + first-run gate from `skills/vp-baseline-compare/SKILL.md` (the canonical template). **Do not** write "see vp-baseline-compare" — every skill is self-contained.
2. The preamble must use the absolute path: `eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"`. Never bare `vpstack-skill-init` (won't be on PATH).
3. The telemetry tail must use the absolute path too: `~/.claude/skills/vpstack/bin/vpstack-telemetry-log`.
4. Update README's "Skills reference" section with the new skill + an example.
5. Update CHANGELOG.


### Run tests

```bash
pytest                 # 40 deterministic tests
pytest -m gpu          # additionally run GPU-marked tests (CG1/CG2 reproducibility — needs GPU + VP2026 data)
pytest tests/activation tests/telemetry  # quick subset (~10s)
```

### Update a release version

Bump `VERSION` AND `package.json::version` together. The CI workflow (`.github/workflows/ci.yml::package-lint`) verifies they all match.

---

## Skill routing

When a user types `/vp-*` in Claude Code, the corresponding skill in `skills/` runs. When they ask in natural language ("how does my system compare to baseline"), match against the voice triggers in each SKILL.md `description` field and invoke the right one.

| User intent | Skill |
|---|---|
| Formalize an experiment | `/vp-hypothesis` |
| Run 1–3 quick variants | `/vp-spike` |
| "Am I beating baseline?" | `/vp-baseline-compare` |
| "Run the attacker", "is my anonymization strong?" | `/vp-attack` |
| Submission-grade full eval | `/vp-eval` |
| "Will this reproduce?" | `/vp-repro-check` |
| Engineering log / writeup | `/vp-writeup` |

Never bypass `vpstack-skill-init`. The activation gate (silent on non-voice repos) is the headline UX promise.

---

## Domain primer (for Claude reading this fresh)

**VoicePrivacy 2026** is an academic challenge that evaluates voice-anonymization systems. The two metrics that matter:

- **Privacy:** how hard is it for an automatic speaker verification (ASV) attacker to re-identify the original speaker from anonymized speech? Reported as **EER** (Equal Error Rate). **Higher EER = more private.** Random chance is 50%.
- **Utility:** is the anonymized speech still useful? Measured by ASR **WER** (Word Error Rate) — lower is better.

The two canonical baselines:
- **B1 (McAdams):** classical signal processing. Modifies LPC pole angles by a coefficient α ≈ 0.8. No ML needed. Fast (CPU). Weak privacy, low utility cost.
- **B2 (neural):** HuBERT content encoder + ECAPA-TDNN speaker embedding + HiFi-GAN vocoder. Strong privacy, more utility cost. The bar to beat.

Three official ASV attacker conditions (run by `/vp-attack`):
- **Ignorant:** attacker doesn't know about anonymization. Sanity floor.
- **Lazy-informed:** attacker knows but doesn't adapt.
- **Semi-informed:** attacker retrains ASV on anonymized data. **The official ranking attacker.**

When you see EER reported, default assumption is "semi-informed condition" unless stated otherwise.

---

## What's deliberately not here

Per [DESIGN.md](DESIGN.md) "v0.1 Explicit Non-Goals":

- No SLURM / async job model. v0.1 assumes laptop or single-GPU server.
- No per-project version pinning. (gstack pattern; tradeoff acknowledged.)
- No citation generation in `/vp-writeup` (LLM hallucination risk).
- No HuggingFace leaderboard, no GitHub Action CI integration in v0.1.
- No remote MCP server (stdio-only).

Don't add any of these without updating DESIGN.md and getting explicit user sign-off.
