# vpstack

> VP2026 voice-privacy toolkit for AI coding agents — Claude Code, Codex, Cursor, Claude Desktop.

vpstack auto-activates on voice-anonymization projects and stays silent everywhere else. It encodes domain knowledge for the [VoicePrivacy 2026 challenge](https://www.voiceprivacychallenge.org/) — real B1/B2 baselines, real EER/WER/linkability eval, real reproducibility checks — so AI agents stop hallucinating SpeechBrain conventions and inventing baseline numbers.

**Status: 0.1.0-dev — pre-release. APIs may change.**

---

## Install

```bash
npx vpstack@latest
```

The installer detects which AI coding agent you have (Claude Code, Codex, Cursor, Cline) and installs accordingly. Run again any time to upgrade.

For the MCP server only (Claude Desktop, Cursor, etc.):

```bash
pip install vpstack-mcp
```

For the SpeechBrain recipe only:

```bash
pip install speechbrain-voice-anon
```

---

## Quick Start

In a voice-anonymization project, just type `/vp-baseline-compare` in Claude Code. vpstack detects the project, asks once whether to enable, then runs B1 + B2 + your system and returns a delta table:

```
EER (lower=better)    B1     B2     yours    Δ vs B1
                      14.2   12.3   11.1     -3.1
WER (lower=better)    8.4    8.1    8.0      -0.4
Linkability           0.45   0.42   0.39     -0.06
```

In an unrelated project, vpstack stays silent.

---

## What's in v0.1

| Component | Purpose |
|---|---|
| **6 Claude Code skills** | `/vp-hypothesis`, `/vp-spike`, `/vp-baseline-compare`, `/vp-eval`, `/vp-repro-check`, `/vp-writeup` |
| **MCP server** | 7 tools for any MCP-aware agent: `vp_run_baseline`, `vp_run_eval`, `vp_check_submission`, `vp_check_reproducibility`, `vp_get_component_info`, `vp_search_experiments`, `vp_log_experiment` |
| **SpeechBrain recipe** | Reference implementations of B1 (McAdams), B2 (HuBERT + ECAPA + HiFi-GAN), and stronger starters |
| **Auto-activation** | Detects voice-anonymization projects via heuristic + first-run prompt + explicit override |
| **Auto-update** | Preamble version check, user always confirms upgrade |
| **Opt-in telemetry** | Three modes (off / anonymous / community); never sends code, paths, or research data |

---

## Documentation

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
