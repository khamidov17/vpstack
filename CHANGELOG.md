# Changelog

All notable changes to vpstack are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) with semver versioning.

## [Unreleased]

### Added (dependency manager + skill prompts, 2026-04-29)
- **`bin/vpstack-deps`** — runtime dependency manager for the ML binaries. Subcommands: `check <feature>` (probe imports), `install <feature>` (run pip install, picks `--user` outside venv), `list` (status of every feature), `packages <feature>` (emit pip args). Features map to ML binary capabilities: `b1` → `numpy scipy soundfile`, `score` → `speechbrain torch torchaudio`, `wer` → `openai-whisper torch`, `utmos` → `speechmos torch torchaudio`, `b2-pool` → `speechbrain torch torchaudio`, `b2-sbvc` → `speechbrain>=0.5.16 torch torchaudio`.
- **Skills now prompt before pip install.** `/vp-spike`, `/vp-attack`, `/vp-baseline-compare`, `/vp-eval` each probe `vpstack-deps check <feature>` before invoking a binary. If a package is missing, the skill surfaces the exact pip command and asks via `AskUserQuestion` (Install / Manual / Skip) — never silently mutates the user's Python environment. Replaces the previous behavior where the binary returned an opaque `DEPS_MISSING` JSON and the user had to figure out what to run.
- **README install section rewritten.** The pre-flight `pip install` block is gone — users no longer need to install everything up front. Skills install only what's needed, on demand, after the user agrees. The "pre-install everything" alternative is documented via `vpstack-deps install` for users who prefer batch setup.
- **`/vp-spike` Step 5 — replaced dead `/tmp/vp_b1_run.py` reference with `vpstack-b1`.** The skill was still telling Claude to run an inlined script that hasn't existed since v0.2; now it shells to the real binary. Also dropped the `BASELINE_NOT_IMPLEMENTED` (exit 2) handling — `vpstack-b1` actually anonymizes, that exit code was a v0.1 stub.

### Added (full eval pipeline + B2 wrapper, 2026-04-29)
- **`vpstack-wer`** — ASR Word-Error-Rate scoring via OpenAI Whisper. Configurable model (`tiny.en` / `base.en` / `small.en` / `medium.en` / `large`), TSV reference manifest, edit-distance WER (own implementation, no `jiwer` dep), per-file + overall, JSON or human output. ~150 lines bash + python.
- **`vpstack-utmos`** — Naturalness PMOS scoring via UTMOS22 (Saeki et al. Interspeech 2022, arXiv:2204.02152) using the `speechmos` package. Per-file + mean/std/min/max, JSON or human. Direction reminder built in (higher = more natural).
- **`vpstack-eval`** — full VP2026 scorecard orchestrator. Drives `vpstack-score` (EER per F-F / M-M / Mixed split), `vpstack-wer` (utility), `vpstack-utmos` (naturalness), then writes the official submission CSV layout per Eval Plan v1 (HAL hal-05561895, Tables 8-9): `exp/asv_anon{suffix}/eer_*.csv`, `exp/asr/wer.csv`, `exp/ser/utmos.csv`, `exp/results_summary/track1/result_for_submission{suffix}.csv`. Optional `--make_zip` for the bundled submission archive. Partial evals supported — components without inputs are reported as skipped, the rest continue.
- **`vpstack-b2`** — neural B2 baseline wrapper, three backends:
  - `external` (default, recommended for VP2026 submission) — drives a user-installed B2 recipe matching the contract `<recipe> --data_path --output_dir --seed [--target_speaker_pool]`. Per LICENSING.md the official VP2026 B2 recipe is GPLv3 and stays out-of-tree; vpstack just drives it.
  - `pool-selection` — ECAPA-TDNN embeddings on source + target pool, farthest-neighbor selection per file (deterministic given `--seed`), writes `anon_targets.json` mapping. A research building block for OHNN / selection-style methods. Does not vocode by itself.
  - `speechbrain-vc` (experimental) — falls back to a pretrained SpeechBrain VC checkpoint if available. Clearly labelled as NOT VP2026-comparable; emits an upfront warning.
- **`/vp-eval` skill rewritten** — was advertising "WER and linkability scoring not yet implemented in vpstack." Now drives `vpstack-eval` directly, parses the JSON, presents the VP2026 scorecard, logs the run to vpbrain (`metrics.eer`/`wer`/`pmos`), and offers the submission ZIP. Also fixed: dead reference to `/tmp/vp_b1_run.py` (replaced by `vpstack-b1` since v0.2), invented `eer.json` schema (real VP2026 layout is CSVs per Eval Plan), and stale `vp_check_submission` MCP-tool reference (gone since v0.2 zero-code refactor).
- **`/vp-baseline-compare` Step 4.5: optional B2 column** — was hard-coded to skip B2 with a "not yet part of vpstack" note. Now offers `vpstack-b2 --backend external` (drive your installed VP2026 B2 recipe) or `--backend pool-selection` (target-speaker manifest only).

### Added (vpbrain end-to-end wiring, 2026-04-29)
- **`/vp-brain` skill** — slash command finally matches what the README has been advertising. Thin wrapper over `vpstack-brain`: lists, ranks, queries, diffs, surfaces learnings + timeline. Works on Claude Code / Codex / Cursor. Skill count: 17 → **18**.
- **`vpstack-brain --slug <name>` cross-project flag** — query any project's experiments without `cd`-ing into the repo. Reads as `vpstack-brain --slug other-project list`.
- **`vpstack-brain projects`** — new subcommand, lists every known project under `~/.vpstack/projects/` with experiment + learning counts and marks the active one.
- **Timeline now scoped to active slug** — `vpstack-brain timeline` filters to the current project (or `--slug` override) instead of dumping global activity.
- **`/vp-baseline-compare` checks vpbrain for duplicates** — Step 1.5 queries prior `B1-McAdams` runs before re-running B1; offers to reuse if a recent run exists. B1 is deterministic for a fixed alpha/seed/data, so this saves the user a 5-min round-trip.
- **`/vp-writeup` reads from vpbrain instead of a fictional MCP tool** — Step 1 now lists experiments via `vpstack-brain list`, resolves user picks against `~/.vpstack/projects/$SLUG/experiments/`, and pulls learnings via `vpstack-brain learnings`. The old `vp_search_experiments` reference (dead since v0.2 MCP rip-out) is gone.

### Fixed (vpbrain bugs, 2026-04-29)
- **`vpstack-brain stats` printed `Project: ?`** — `cmd_stats` referenced `os.environ.get('SLUG','?')` but `SLUG` was never exported. Fixed by exporting once at the top of the script.
- **`vpstack-brain learnings` ignored `--slug` override** — used to shell out to `vpstack-learnings-search` which derives slug from cwd. Inlined the read so the override propagates.
- **`vpstack-skill-init` learnings markers swallowed by `eval`** — skills consume the preamble via `eval "$(vpstack-skill-init …)"`, so any non-key=value line on stdout becomes a "command not found" error. The `RECENT_LEARNINGS_START` / `[key] insight` / `RECENT_LEARNINGS_END` lines now go to stderr, matching their display-only intent and making the cross-session learnings feature actually visible.

## [Unreleased — pre-2026-04-29]

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
