# Changelog

All notable changes to vpstack are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) with semver versioning.

## [Unreleased]

### Added (post-initial-commit pass)
- **`/vp-attack` skill + `vp_run_attacker` MCP tool** — VPC-conformant ASV attacker against anonymized output. Supports the three official conditions (ignorant / lazy_informed / semi_informed). Per-gender EER + linkability (ZEBRA Cllr). Recipe is stubbed; spec is locked. The wedge feature that makes vpstack research infrastructure, not just a SpeechBrain wrapper.
- **`.vpstack/ask-later` marker** with 60-min validity — fixes the multi-skill-session re-prompt loop (F32 from QA).
- **HEADLESS coercion stderr diagnostic** — users in tmux/CI now see WHY vpstack went silent instead of staring at a blank session (F19 from QA).
- **Reframe to voice-privacy research infrastructure** (CEO review) — drops the VP2026-only ceiling. Multi-challenge support framing for VP2024+VP2026. README opens with "if you don't work on voice anonymization, this isn't for you" so the audience self-selects in 1 line.
- **GitHub starter issues** for B2, eval pipeline, telemetry endpoint deployment.

### Fixed (post-initial-commit pass)
- **F1 P0:** `vpstack-install` non-TTY hang. Defaults to `telemetry=off` (safest) when no TTY / `--yes` / `CI=true`.
- **F18 P0:** `vpstack-config get` no longer silently masks corrupt JSON; surfaces error to stderr with exit 1.
- **F32 P0:** ask-later loop fix as above.
- **F19 P1:** silent HEADLESS coercion now emits diagnostic.

### Repo
- Pushed to https://github.com/khamidov17/vpstack (private)
- About + 12 GitHub topics set
- 3 starter issues filed for known v0.1.x work

### Tests
- 40/40 passing (was 34) — added 6 new tests for `vp_run_attacker` input validation

### Added
- Repo skeleton: 7 `bin/` scripts, 6 SKILL.md skills, MCP server (7 tools), SpeechBrain recipe with B1 McAdams, test suite (31 passing).
- `bin/vpstack-detect` activation gate with hybrid heuristic + first-run prompt + explicit override.
- Three-mode opt-in telemetry (off / anonymous / community), self-hosted endpoint pattern.
- Auto-update preamble with 6h cache, network-failure-safe.
- Atomic three-package release pipeline (npm + 2 PyPI) via `.github/workflows/release.yml`.
- LICENSING.md audit: Apache 2.0 vpstack license; runtime model downloads (no GPLv3 vendoring).
- `B1 McAdams` recipe re-implemented from VP2024 Eval Plan (NOT a port of GPLv3 code).

### Known Limitations
- B2 (neural) baseline is stubbed — week-1+ work.
- `vp_run_eval` MCP tool is stubbed — returns `BASELINE_NOT_IMPLEMENTED`.
- B1 eval pipeline (EER/WER/linkability scoring) returns sentinel `nan` values; anonymization stage works.
- `vp-repro-check` does NOT track vpstack version (per design — researchers note in lab notebook).
- Codex / Cursor / Cline frontend installers are placeholders; v0.1 is Claude Code-first.

### Security & Privacy
- Telemetry strict allowlist (CG3 + CG4 enforced in tests): only `skill`, `outcome`, `vpstack_version`, `ts`, `duration_s`, `device_id`, `error_class` keys ever appear in payload.
- Off mode is hard-coded to short-circuit before any network code path runs.
- Activation `disabled` marker takes precedence over `enabled` (safer default on conflict).

[Unreleased]: https://github.com/vpstack/vpstack/compare/main...HEAD
