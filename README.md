# vpstack

> Voice-privacy research infrastructure for AI coding agents.

**v0.3.0-dev** — Markdown skills + bash binaries. Works in Claude Code, Codex, and Cursor.

vpstack gives AI agents the domain knowledge and workflow automation they need for VoicePrivacy 2026. They stop hallucinating baseline numbers. They know what EER means and which direction is better. They run the right attacker condition. They check reproducibility before you submit.

**Auto-activates on voice-anonymization projects. Silent everywhere else.**

---

## How it works

A complete experiment cycle, hypothesis to ship, with the actual commands:

```
You:    My content encoder is HuBERT layer 12. I want to test layer 6.

You:    /vp-hypothesis

Claude: [7 questions: what changes, baseline, acceptance criteria, magnitude]
        "Domain note: Layer 6 is pre-content peak — phonetic + residual speaker.
         Layer 7-9 is the phonetic content peak per Pasad et al. (ASRU 2021)."
        → Writes ~/.vpstack/projects/my-system/hypotheses/20260429-hubert-l6.md
```

```
You:    /vp-spike

Claude: [reads hypothesis, asks for 3 variant data paths]
        Running variants via vpstack-b1...

        $ vpstack-b1 --data_path /data/l6/ --seed 42
        $ vpstack-b1 --data_path /data/l9/ --seed 42
        $ vpstack-b1 --data_path /data/l12/ --seed 42

        | Variant   | Files | Output           | Config hash       |
        | layer-6   | 847   | /data/l6/anon_b1 | d4f662e1b76de2f5  |
        | layer-9   | 847   | /data/l9/anon_b1 | a72e8c33f9a14b6e  |
        | layer-12  | 847   | /data/l12/anon_b1| b8f1d24e6c8a7f1d  |

        → Run /vp-attack on each output to get EER for the verdict
```

```
You:    /vp-attack on /data/l6/anon_b1

Claude: Which condition? semi-informed is the official VP2026 ranking metric.
You:    lazy-informed first.

        $ vpstack-score \
            --anonymized_path /data/l6/anon_b1 \
            --enrollment_path /data/enroll \
            --trial_list /data/trials.txt \
            --condition lazy_informed \
            --backend speechbrain --seed 42

        VP2026 Attacker Results — lazy_informed
        EER overall:  38.2%   (↑ = more private, 50% = random)
        N trials:     200     (100 target / 100 nontarget)
        seed:         42

        → Run semi-informed before citing this in a paper
```

```
You:    /vp-repro-check

Claude: $ vpstack-lock verify checkpoints.lock
        OK:      hubert-base
        OK:      ecapa-voxceleb
        OK:      hifigan-libritts
        vpstack-lock verify: 3/3 OK

        Reproducibility: PASS_STRONG
        ✓ seed pinned: 42
        ✓ splits: explicit (VP2026 dev-clean v2026.03.17)
        ✓ checkpoints: 3/3 hash-verified
        ✓ hparams: no placeholders
        ✓ determinism: torch_deterministic: true
```

```
You:    /vp-brain top --metric eer

Claude: $ vpstack-brain top --metric eer --limit 5

        Top 5 by eer (↑ = better):
        RANK    VALUE  EXP_ID                                METHOD
        1       38.20  layer-6-spike-20260429T143012        B1-McAdams
        2       35.10  layer-9-spike-20260429T143245        B1-McAdams
        3       28.40  layer-12-spike-20260429T143518       B1-McAdams
        4       14.20  b1-reference-20260428                B1-McAdams
        5        4.10  original-no-anon-20260427            none
```

```
You:    /vp-ship

Claude: Tests passed. Repro PASS_STRONG. Deferred gates: 0.
        VERSION: 0.3.0-dev → 0.3.1-dev
        Commit: abc1234 — "feat: HuBERT layer ablation"
        PR: github.com/you/vp2026-system/pull/7
```

That's one experiment cycle. Hypothesis → spike (real B1 runs) → attack (real ECAPA scoring) → repro-check (real hash verification) → leaderboard → ship. No skill pretends to do something it can't.

---

## Install

### Claude Code

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
pip install soundfile scipy numpy           # for vpstack-b1
pip install speechbrain torch torchaudio    # for vpstack-score (optional, only if you need EER)
```

Restart Claude Code. Open a voice-anonymization project. Type `/vp-hypothesis`.

vpstack auto-activates on voice-anonymization projects (detects `VP2026`, `voice-anonymization`, `speechbrain`, British spelling `anonymisation`, more). Silent everywhere else.

### Codex

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
cp ~/.claude/skills/vpstack/AGENTS.md /path/to/your/vp2026-project/AGENTS.md
```

Codex reads `AGENTS.md` for domain context. Open `skills/vp-*/SKILL.md` and tell Codex to follow it. The bash binaries (`vpstack-b1`, `vpstack-score`, etc.) work the same way for Codex as for Claude — same commands, same outputs.

### Cursor

```bash
git clone https://github.com/khamidov17/vpstack.git ~/.claude/skills/vpstack
chmod +x ~/.claude/skills/vpstack/bin/*
mkdir -p /path/to/your/vp2026-project/.cursor
cp ~/.claude/skills/vpstack/.cursor/rules /path/to/your/vp2026-project/.cursor/rules
```

In Cursor Composer, open `skills/vp-*/SKILL.md` in the sidebar and reference it. Same bash binaries.

### All clients — add domain context to your project

```bash
cat ~/.claude/skills/vpstack/docs/claude-md-template.md >> CLAUDE.md
```

This gives the agent the VP2026 domain facts upfront — metric directions, baseline notes, component tradeoffs, common mistakes — so it doesn't ask you what EER means or get the direction backwards.

---

## Skills

| Skill | What it does |
|---|---|
| `/vp-talk` | Two modes: **Research** (8 forcing questions → research plan) or **Engineering** (6 domain questions → domain_config.yaml + engineering plan) |
| `/vp-hypothesis` | Formalize an experiment in 7 questions, write structured doc |
| `/vp-spike` | Run 1–3 B1 ablation variants via `vpstack-b1`, log verdicts as learnings |
| `/vp-baseline-compare` | B1 baseline (real, via `vpstack-b1`) + delta table |
| `/vp-attack` | ASV attacker (real, via `vpstack-score`): ignorant / lazy-informed / semi-informed |
| `/vp-eval` | Full VP2026 scorecard — currently uses `vpstack-score` + Whisper + UTMOS |
| `/vp-repro-check` | PASS_STRONG / PASS_WEAK — seeds, splits, checkpoint hashes (real, via `vpstack-lock`) |
| `/vp-implement` | 14-step dev workflow with license + repro gates |
| `/vp-investigate` | Domain-aware debugging — "my EER looks wrong" |
| `/vp-writeup` | Engineering report from experiment logs (no LLM-generated citations) |
| `/vp-qa` | QA pass: repro + attacker smoke + submission format |
| `/vp-ship` | Version bump + repro gate + deferred gate check + PR |
| `/vp-plan-eng-review` | 18 VP-specific engineering gates against research/engineering plan |
| `/vp-plan-design-review` | Architecture review before implementation |
| `/vp-autoplan` | Chains all skills end-to-end |
| `/vp-context-save` | Save session state — active hypothesis, last experiment, next step |
| `/vp-context-restore` | Resume from saved state — 2-sentence briefing, pick up where you left off |
| `/vp-brain` | Browse experiment store: `list`, `top`, `stats`, `query`, `diff`, `learnings`, `timeline`, `projects` |

---

## Bash binaries

The skills call these directly. You can also use them standalone:

| Binary | Purpose |
|---|---|
| `vpstack-b1` | McAdams B1 anonymization on any WAV directory. CPU only, ~5min for dev set |
| `vpstack-score` | ASV attacker — wraps SpeechBrain ECAPA or your own external attacker |
| `vpstack-lock` | Generate/verify `checkpoints.lock` for hash-pinned reproducibility |
| `vpstack-brain` | Experiment store CLI: `list`, `top`, `show`, `diff`, `query`, `stats`, `learnings`, `timeline`, `projects`. `--slug <name>` for cross-project queries |
| `vpstack-slug` | Project slug (basename + USER-scoped hash) — matches storage paths |
| `vpstack-skill-init` | Skill preamble logic — activation gate, learnings load, routing injection |
| `vpstack-detect` | Detects voice-anonymization projects |
| `vpstack-config` | User config (`~/.vpstack/config.json`) — telemetry mode, etc. |
| `vpstack-telemetry-log` | Opt-in telemetry (off / anonymous / community) |
| `vpstack-learnings-log` | Append a research learning to `~/.vpstack/projects/{slug}/learnings.jsonl` |
| `vpstack-learnings-search` | Query learnings by text, type, source |
| `vpstack-timeline-log` | Append a skill-run event to `~/.vpstack/analytics/timeline.jsonl` |

Run any of them with `--help` for usage.

---

## What's implemented

| Component | Status |
|---|---|
| B1 McAdams anonymization (`vpstack-b1`) | ✅ Working end-to-end on any 16kHz WAV directory |
| ASV attacker scoring (`vpstack-score`) | ✅ SpeechBrain ECAPA backend + external backend for official VP2026 |
| Checkpoint hash verification (`vpstack-lock`) | ✅ Generate + verify, real SHA256, macOS/Linux compat |
| Experiment store CLI (`vpstack-brain`) | ✅ Full operations over JSONL state |
| All 17 skills | ✅ Markdown workflows that call the binaries directly |
| Cross-session learnings + timeline | ✅ Persistent state, surfaced in skill preambles |
| Reproducibility check (PASS_STRONG / PASS_WEAK) | ✅ Real verification, not placeholder |
| Engineering plan output (vp-talk Mode E) | ✅ `domain_config.yaml` + `engineering-plan.md` |
| Context save/restore | ✅ Resume mid-experiment from any session |
| Activation auto-detect | ✅ VP2026 projects fire, others stay silent |
| Claude Code / Codex / Cursor | ✅ All three clients, same skills, same binaries |
| B2 neural baseline (HuBERT + ECAPA + HiFi-GAN) | ⏳ v0.4 — use the official VP2026 challenge B2 recipe today |
| Full bundled eval pipeline | ⏳ v0.4 — today: `vpstack-score` for EER, Whisper for WER, UTMOS for PMOS |

---

## Storage layout

State lives at `~/.vpstack/`:

```
~/.vpstack/
├── config.json                              user config (telemetry mode, etc.)
├── analytics/
│   └── timeline.jsonl                       every skill run, ever (audit trail)
└── projects/
    └── {repo}-{user-hash}/
        ├── domain_config.yaml               from /vp-talk Mode E
        ├── learnings.jsonl                  research insights, persistent across sessions
        ├── session-state.md                 from /vp-context-save (resume target)
        ├── deferred-gates.jsonl             from /vp-plan-eng-review (re-checked at /vp-ship)
        ├── hypotheses/{id}.md               from /vp-hypothesis
        ├── research-plans/{id}.md           from /vp-talk Mode R
        ├── engineering-plans/{id}.md        from /vp-talk Mode E
        ├── spikes/{id}.md                   from /vp-spike
        └── experiments/{exp_id}/summary.json    canonical experiment log
```

Browse it with `vpstack-brain` or directly via `cat`. No database. No proprietary format.

---

## Domain knowledge

Everything the agent needs to know about VP2026 is in [`docs/domain.md`](docs/domain.md):

- Metric directions (EER ↑ = private, 50% = goal; WER ↓ = useful)
- Three attacker conditions and which one to report (semi-informed)
- Component tradeoffs (HuBERT layers, ContentVec, WavLM, ECAPA-TDNN, HiFi-GAN, McAdams, PLDA)
- Known component failure modes (the things researchers re-discover every time)
- `checkpoints.lock` format for hash-pinned reproducibility
- VP2026 submission format requirements
- Common mistakes that waste GPU time

---

## Architecture

```
skills/vp-*/SKILL.md     pure markdown — workflow instructions for the agent
bin/vpstack-*            bash binaries — actual computation, called by skills
docs/                    domain knowledge agents read in every session
```

Zero Python files in the skill layer. The bash binaries embed Python heredocs where needed (numpy/scipy for B1, torch/speechbrain for the attacker), but the skills themselves are markdown only — same pattern as gstack.

No MCP server. No daemon. No build step beyond `chmod +x`.

---

## License

Apache 2.0. Do NOT import VP2024 baseline GitHub code — it's GPLv3 and would force the whole project to GPL. Implement from the [VP2024 Eval Plan PDF](https://inria.hal.science/hal-04531444v1/) or subprocess the GPLv3 scripts as external tools (vpstack does this via `vpstack-score --backend external`).
