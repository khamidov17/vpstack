# Quick Start

vpstack helps voice-anonymization researchers run B1/B2 baselines, score systems against the VP2026 protocol, and track experiments — all from inside Claude Code (or any MCP-aware AI agent).

## Install

```bash
npx vpstack@latest
```

You'll be asked once about telemetry (off / anonymous / community — your choice). vpstack writes 6 skills to `~/.claude/skills/vpstack/`, prints the MCP server config, and sets up your config at `~/.vpstack/config.json`.

If you also want to use vpstack from Claude Desktop, Cursor, Codex, or any other MCP-aware client, install the MCP server separately:

```bash
pip install vpstack-mcp speechbrain-voice-anon
```

Then paste the printed MCP config into your client's MCP server settings.

## First skill use

Open a voice-anonymization project (any repo with `speechbrain` in deps, or a `VP2026` reference, or a path matching `*voice-anon*`). In Claude Code, type:

```
/vp-baseline-compare
```

vpstack detects the project, asks you once whether to enable here (Yes / No / Ask later), then runs B1 + B2 baselines + your system and returns a delta table:

```
                   B1     B2     yours    Δ vs B1   Δ vs B2
EER (lower=better) 14.2   12.3   11.1     -3.1      -1.2
WER (lower=better) 8.4    8.1    8.0      -0.4      -0.1
Linkability        0.45   0.42   0.39     -0.06     -0.03
```

In an unrelated project (Rails app, Go CLI, NLP repo without voice signals), vpstack stays silent. Zero output, zero prompts. The `disabled` marker also lets you opt out of any project explicitly: `mkdir -p .vpstack && touch .vpstack/disabled`.

## The 6 skills

| Skill | When |
|---|---|
| `/vp-hypothesis` | Before any new experiment — formalize what you're testing |
| `/vp-spike` | Run 1–3 focused ablations with given/when/then verdicts |
| `/vp-baseline-compare` | Compare your system against B1/B2 — the daily-use skill |
| `/vp-eval` | Full VP2026 eval (EER + WER + linkability + side channels), submission validation |
| `/vp-repro-check` | Verify seeds, splits, checkpoints — catches silent drift |
| `/vp-writeup` | Generate an internal experiment report (NOT a paper section, NOT citations) |

## The 7 MCP tools

These are exposed by `vpstack-mcp` and callable from any MCP-aware agent:

- `vp_run_baseline(baseline, data_path, seed)` — run B1 or B2
- `vp_run_eval(system_path, eval_set, seed, official_test)` — full eval pipeline
- `vp_check_submission(submission_path)` — validate before upload
- `vp_check_reproducibility(config_path)` — verify config reproducibility
- `vp_get_component_info(component_name)` — tradeoff matrix for known components
- `vp_search_experiments(query, limit)` — search your logged experiments
- `vp_log_experiment(exp_id, metrics, config_hash)` — atomic write to your project log

## Where things live

| What | Where |
|---|---|
| Skill installs | `~/.claude/skills/vpstack/` (Claude Code), `~/.codex/skills/vpstack/` (Codex) |
| User config | `~/.vpstack/config.json` |
| Activation cache | `~/.vpstack/cache/` |
| Experiment logs | `~/.vpstack/projects/{slug}/experiments/{id}/` |
| Hypotheses | `~/.vpstack/projects/{slug}/hypotheses/` |
| Spikes | `~/.vpstack/projects/{slug}/spikes/` |
| Per-project activation marker | `<repo>/.vpstack/enabled` or `<repo>/.vpstack/disabled` |

This split mirrors gstack: the repo only sees a tiny activation marker; everything else is user-level and never accidentally committed.

## Telemetry

| Mode | What gets sent |
|---|---|
| `off` | Nothing. Zero network calls. |
| `anonymous` | `{skill, outcome, duration_s, vpstack_version, ts}` only — no device ID |
| `community` | Anonymous fields + stable `device_id` (hash of machine UUID + user) + `error_class` |

Never sent in any mode: code, file paths, hypothesis text, eval numbers, repo names, branch names, hyperparameters, seeds, config hashes, user prompts, error message bodies.

Change anytime: `vpstack-config set telemetry off`.

## Updating

Skills check for updates in their preamble. When a new version is available you'll see `UPGRADE_AVAILABLE 0.1.0 0.2.0` and a prompt to upgrade. Decline with `D) Don't ask again until next minor` if you're mid-experiment and want to pin until you're ready.

## Uninstall

```bash
npx vpstack@latest --uninstall
```

Removes the `~/.claude/skills/vpstack/` install. Your `~/.vpstack/projects/` history is preserved — delete manually if you want it gone.
