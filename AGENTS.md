# AGENTS.md — Context for Codex (and other AI agents) working in this repo

This file is the Codex-equivalent of CLAUDE.md. For full context, read CLAUDE.md.

## What this repo is

vpstack is **voice-privacy research infrastructure for AI coding agents**. It encodes
VoicePrivacy 2026 domain knowledge so AI agents stop hallucinating SpeechBrain conventions
and inventing baseline numbers.

## MCP server setup for Codex

The vpstack MCP server exposes 8 tools (run_baseline, run_eval, run_attacker, check_submission,
check_reproducibility, get_component_info, search_experiments, log_experiment).

Register it with Codex:

```bash
# Activate the venv where you pip-installed vpstack-mcp, then:
codex mcp add vpstack -- /path/to/venv/bin/vpstack-mcp

# Or using the absolute path (safer — Codex may not inherit your shell PATH):
codex mcp add vpstack -- $(which vpstack-mcp)
```

Verify it registered:

```
codex mcp list
# Name     Command      Args  Status
# vpstack  vpstack-mcp  -     enabled
```

## Key rules (same as CLAUDE.md, condensed)

1. **Never import from `Voice-Privacy-Challenge-2024`** (GPLv3). Re-implement from the Eval Plan PDF.
2. **Never bundle pretrained weights** — fetch via HuggingFace Hub at runtime.
3. **Every MCP tool returns `{"ok": bool, "result": ..., "error": ...}`** from errors.py.
4. **Atomic writes** for state files: write-tmp → fsync → rename → fsync-parent-dir.
5. **New error codes** must be added to `ERROR_CODES` in errors.py AND tested.

## Domain primer (short)

- **EER** = Equal Error Rate. Privacy metric. **Higher = more private.** Random = 50%.
- **WER** = Word Error Rate. Utility metric. Lower = better.
- **B1** = McAdams baseline (signal processing, CPU, fast). **B2** = HuBERT+ECAPA+HiFi-GAN (neural, GPU, strong).
- **Semi-informed attacker** = official VP2026 ranking condition. Always run this for privacy numbers.

## Where to look

| What | Where |
|---|---|
| MCP tools | `mcp-server/vpstack_mcp/tools/*.py` |
| Error contract | `mcp-server/vpstack_mcp/errors.py` |
| B1 recipe (real) | `speechbrain_voice_anon/recipes/VP2026/baseline_B1/` |
| Skills | `skills/*/SKILL.md` |
| Tests | `tests/` — run with `pytest` |
