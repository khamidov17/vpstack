# Changelog

All notable changes to vpstack are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) with semver versioning.

## [Unreleased]

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
