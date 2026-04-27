# Changelog

All notable changes to vpstack are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) with semver versioning.

## [Unreleased]

### Added (full domain command set, 2026-04-28)
- **`/vp-talk`** — voice-anonymization research-direction office hours. 8 forcing questions covering open question, threat model, contribution claim, baseline selection, eval scope, failure modes, scope discipline, and (clinical-only) HIPAA-grade threat surface. Writes locked research-plan docs to `~/.vpstack/projects/{slug}/research-plans/`. Includes domain knowledge for OHNN (Orthogonal Householder Neural Network, Miao et al. 2023, arXiv:2305.18823) and three architectural families (classical / selection / transformation).
- **`/vp-plan-design-review`** — review recipe / attacker / eval architecture BEFORE coding. Validates recipe interface contract, attacker condition coverage, the 5 reproducibility checks, eval-set safety (no test-split leakage), and license posture. Distinct from gstack's visual-UI design review.
- **`/vp-plan-eng-review`** — 18 VP-specific engineering gates layered on top of gstack `/plan-eng-review`. P0 gates: GPLv3 isolation, runtime model fetch, test-split blocking, fixture audit, telemetry allowlist, MCP `ToolResult` contract, VP2026 submission format, atomic state writes, repro-check, attacker-training determinism. P1: three attacker conditions, F-F/M-M/Mixed gender, recipe interface, 16kHz PCM, model dependency declarations, activation silence. P2: Track 2 multilingual, headless mode.
- **`/vp-implement`** — orchestrated implementation with pre/during/post gates. Reads latest hypothesis, enforces recipe-shape contract from CLAUDE.md, blocks placeholder hparams, auto-runs `/vp-repro-check`, verifies the 7 critical CG tests stay green, logs to experiment tracker for `/vp-writeup`. 14-step workflow with 9 explicit BLOCKED states (LICENSE_VIOLATION, REPRO_CHECK_FAIL, TESTS_REGRESSED, CONTRACT_VIOLATION, PLACEHOLDER_HPARAMS, BASELINE_TESTS_RED, TARGET_OUT_OF_SCOPE, RUFF_DIRTY, MCP_UNREACHABLE).
- **`/vp-qa`** — multi-tier QA orchestration: repro-check + lazy-informed attacker smoke + submission format + project pytest. Three tiers (Quick ~15min / Standard ~1h / Pre-submission ~12h). Computes 0–100 QA score across tests/repro/privacy/utility/submission categories.
- **`/vp-attack`** — already shipped; documented in CHANGELOG above.
- **`/vp-investigate`** — domain-aware debugging with VP2026 priors. Decision tree for the most-common failure modes: EER > 50% (polarity flip), EER ≈ 50% (broken attacker), EER too low (anonymization no-op), reproducibility drift (CUDA non-determinism), WER NaN (audio format mismatch), incoherent attacker output, submission-format errors. Falls back to gstack `/investigate` for non-domain causes.
- **`/vp-ship`** — voice-anonymization-aware ship workflow. gstack `/ship` shape (base-branch detection, version bump, atomic commit, push, optional PR) PLUS VP-specific gates: pytest -m "not gpu", `/vp-repro-check` PASS if recipe touched, submission format if eval pipeline touched, optional 10-min lazy_informed attacker smoke if anonymizer code changed. Blocks ship if any P0 gate fails.
- **`/vp-autoplan`** — full lifecycle sequencer: `/vp-talk` → `/vp-hypothesis` → `/vp-plan-design-review` → `/vp-plan-eng-review` → `/vp-implement` → `/vp-qa` → `/vp-ship`. Four scope modes (Greenfield / Mid-cycle / Implementation-done / Pre-submission). Check-in gates between phases — autoplan never silently skips a skill's prompts.

### Added (error codes for new skills)
- `LICENSE_VIOLATION`, `REPRO_CHECK_FAIL`, `TESTS_REGRESSED`, `CONTRACT_VIOLATION`, `PLACEHOLDER_HPARAMS`, `BASELINE_TESTS_RED`, `TARGET_OUT_OF_SCOPE`, `RUFF_DIRTY` — added to `ERROR_CODES` allowlist for `/vp-implement` BLOCKED states.

### Skill count
- **v0.1.0-dev (initial):** 7 skills + 7 MCP tools
- **v0.1.0-dev (post-2026-04-28):** **15 skills + 8 MCP tools** — full lifecycle coverage with voice-anon domain context at every phase.

### Fixed (correctness audit, 2026-04-28)
- **B1 frame length: 25 → 20 ms** to match the canonical Patino VP2020 reference (`anonymise_dir_mcadams.py`). Earlier value was wrong; B1 numbers from the prior version would not match published baselines.
- **B1 pole mask: exclude ±π real-axis poles.** Previously a pole at `angle = π` (negative real) would get transformed to `π^0.8 ≈ 2.499`, lifting it off the real axis with no conjugate partner — geometrically wrong. Canonical Patino uses `np.iscomplex(roots)`. Audit-flagged and corrected.
- **B1 Levinson-Durbin dead branch removed.** The `if i > 0 else [r[1]]` clause in `_lpc()` was confirmed dead by concrete trace; general expression handles `i==0` correctly.
- **`check_submission.py` REWRITTEN.** Prior version validated an invented format (JSON files, `linkability.json`, `{male, female, overall}` gender split). Actual VP2026 layout per Eval Plan v1 (HAL hal-05561895, Tables 8-9) is: CSV files under `exp/asr/`, `exp/ser/`, `exp/asv_ssl/`, `exp/asv_anon<suffix>/`, with submission archive at `exp/results_summary/track1/result_for_submission<suffix>.zip`. Track 2 (multilingual) layout also handled. Privacy is **EER-only** in VP2026 — no `linkability.json`. Gender split is **F-F, M-M, Mixed** (not male/female/overall). Earlier validator would have blessed invalid submissions and rejected valid ones.
- **HuBERT layer claim corrected.** Prior `get_component_info.py` cited a "Liu et al. 2024" paper that doesn't exist and stated "layer 6 = content / layer 12 = speaker" — partially wrong. Replaced with Pasad, Chou, Livescu (ASRU 2021, arXiv:2107.04734): HuBERT-base content peaks at layers 7-9, speaker info concentrates in early layers 1-4, layer 12 is content-leaning (close to masked-prediction target).

### Added (docs + agent context)
- **`CLAUDE.md` at repo root** — context for AI agents working IN this repo. Architecture overview, non-negotiable rules (no GPLv3 vendoring, no weights bundling, telemetry allowlist), where things live, common tasks (add a new MCP tool, add a new skill, implement a recipe), domain primer.
- **`docs/claude-md-template.md`** — context to drop into a researcher's voice-anonymization project's CLAUDE.md. VP2026 metric directions (privacy = HIGHER EER, utility = LOWER WER), canonical baselines, attacker conditions, dataset conventions, model licenses, "use vpstack skill X instead of writing one-off script Y" routing rules. Researcher copies via `cat ~/.claude/skills/vpstack/docs/claude-md-template.md >> CLAUDE.md`.
- **README expansion: per-skill examples + per-tool reference + session walkthrough.** Each of the 7 skills shows a researcher dialogue → vpstack response pattern. Each of the 8 MCP tools has a one-row table entry with cost + return shape.

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
