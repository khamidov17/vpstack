# CLAUDE.md — Context for AI agents working IN this repo

This file gives Claude Code / Codex / Cursor / any AI agent the conventions it needs to make sane edits inside the vpstack repo itself.

For context that gets injected into a *user's* voice-anonymization project (not this repo), see [docs/claude-md-template.md](docs/claude-md-template.md).

---

## What this repo is

vpstack is **voice-privacy research infrastructure for AI coding agents**. It encodes domain knowledge for VoicePrivacy 2026 (and VP2024 ports planned) so AI agents stop hallucinating SpeechBrain conventions and inventing baseline numbers.

**Read first if you're editing anything substantial:**
- [DESIGN.md](DESIGN.md) — full architecture with 7 locked premises (P1–P7) and explicit non-goals
- [LICENSING.md](LICENSING.md) — license posture (Apache 2.0, runtime model downloads only, **NO vendoring of VP2024 GPLv3 code**)
- [TEST-PLAN.md](TEST-PLAN.md) — 7 critical CI gates, including B1/B2 reproducibility ±0.5% EER

---

## Architecture in one paragraph

`bin/` is bash scripts (orchestration primitives). `skills/*/SKILL.md` are markdown workflows for Claude Code. `mcp-server/vpstack_mcp/` is the Python MCP server (8 tools, structured error contract). `speechbrain_voice_anon/` is the actual SpeechBrain recipe — re-implemented from VP2024 Eval Plan PDF, NEVER ported from VP2024 GitHub (which is GPLv3 and would force the whole project to GPL). The split: orchestration stays in bash + markdown (gstack pattern), heavy lifting lives in Python because SpeechBrain + PyTorch + HuggingFace Hub do.

---

## Non-negotiable rules

1. **Never `import` or vendor anything from `Voice-Privacy-Challenge-2024`** (GPLv3). Re-implement from the published Eval Plan PDF instead. License audit in [LICENSING.md](LICENSING.md).
2. **Never write code that ships pretrained model weights**. We fetch from HuggingFace Hub at runtime. Never bundle weights into a release artifact.
3. **Never bundle VP2026 trial lists / VoxCeleb audio / IEMOCAP** in CI fixtures. Use small LibriSpeech-derived clips (CC-BY 4.0).
4. **Telemetry payload is a strict allowlist.** If you add a new key to the payload, update both the constructor in `bin/vpstack-telemetry-log` AND the test in `tests/telemetry/test_payload_sanitization.py::test_payload_keys_are_strict_allowlist`. The CG3/CG4 tests in `tests/telemetry/` are non-negotiable.
5. **Every MCP tool returns the structured `ToolResult` contract** from `mcp-server/vpstack_mcp/errors.py`. Never raise unhandled exceptions; catch and return `err(...)` with a code from the `ERROR_CODES` allowlist.
6. **Never modify CI workflows or existing tests** unless explicitly fixing a bug. New tests go in new files.
7. **Atomic writes for state files.** Pattern: write-to-tmp → fsync → rename → fsync-parent-dir. See `mcp-server/vpstack_mcp/tools/log_experiment.py::_atomic_write_json`.

---

## Where things live

| What | Where | Notes |
|---|---|---|
| Bash CLI primitives | `bin/` | All chmod +x. Each script self-documents via `--help`. |
| Skill workflows | `skills/{name}/SKILL.md` | gstack-style frontmatter (`name`, `version`, `description`, `allowed-tools`). Self-contained preamble — never reference another skill's preamble. |
| MCP server | `mcp-server/vpstack_mcp/` | Python package. `server.py` registers tools, `tools/*.py` implement them, `errors.py` enforces error contract. |
| SpeechBrain recipe | `speechbrain_voice_anon/recipes/VP2026/` | One subdir per system: `baseline_B1/` (real), `baseline_B2/` (stub), `attacker/` (stub), `ecapa_farthest/` (stub), `hifigan_anon/` (stub). |
| Tests | `tests/` | Five subdirs: `activation/`, `telemetry/`, `mcp/`, `recipes/`. Run with `pytest`. |
| User-level state at runtime | `~/.vpstack/` | `config.json`, `cache/`, `projects/{slug}/` — never in this repo. |
| Per-project markers | `<repo>/.vpstack/` | Just `enabled` / `disabled` / `ask-later` files. Tiny. |

---

## Common tasks

### Add a new MCP tool

1. Create `mcp-server/vpstack_mcp/tools/{tool_name}.py` matching the shape of existing tools (returns `ToolResult` via `ok()` / `err()`).
2. Add the tool to the `_TOOLS` registry in `mcp-server/vpstack_mcp/server.py` with description + JSON schema.
3. Import it in `mcp-server/vpstack_mcp/tools/__init__.py`.
4. Add any new error codes to `ERROR_CODES` frozenset in `errors.py`.
5. Write input-validation unit tests in `tests/mcp/test_{tool_name}.py` — no GPU dependency, no real ML.

### Add a new skill

1. Create `skills/{skill_name}/SKILL.md`. Copy the frontmatter + preamble + first-run gate from `skills/vp-baseline-compare/SKILL.md` (the canonical template). **Do not** write "see vp-baseline-compare" — every skill is self-contained.
2. The preamble must use the absolute path: `eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"`. Never bare `vpstack-skill-init` (won't be on PATH).
3. The telemetry tail must use the absolute path too: `~/.claude/skills/vpstack/bin/vpstack-telemetry-log`.
4. Update README's "Skills reference" section with the new skill + an example.
5. Update CHANGELOG.

### Implement a recipe (B2, attacker, etc.)

Each `recipes/VP2026/{name}/run.py` has a docstring with the full implementation specification. Read it. The contract is:
- CLI args: `--data_path` (or `--anonymized_path` etc.), `--seed`, `--output_format json|human`
- On success: print a single JSON line on stdout with the documented schema
- On failure: print to stderr, exit non-zero
- Stream progress to stderr every 30 seconds for runs >15min (per MCP long-running-tool contract)
- Honor `torch.use_deterministic_algorithms(True)` if hparams request it
- Lazy-fetch model weights via `huggingface_hub.snapshot_download()` — never bundle

### Run tests

```bash
pytest                 # 40 deterministic tests
pytest -m gpu          # additionally run GPU-marked tests (CG1/CG2 reproducibility — needs GPU + VP2026 data)
pytest tests/activation tests/telemetry  # quick subset (~10s)
```

### Update a release version

Bump `VERSION` AND `package.json::version` AND `mcp-server/pyproject.toml::version` AND `speechbrain_voice_anon/pyproject.toml::version` together. The CI workflow (`.github/workflows/ci.yml::package-lint`) verifies they all match.

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
