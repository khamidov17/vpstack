# AGENTS.md — Context for Codex and other AI agents

vpstack is a voice-privacy research toolkit for the VoicePrivacy 2026 challenge.
Read this before writing any code or running any commands in this project.

---

## What this repo is

vpstack gives AI coding agents domain knowledge for VP2026 voice anonymization research.
No MCP server. No Python code in the repo. Skills are markdown files that tell Claude
(or you) what bash commands to run. You are the execution engine.

**If you're helping in a *user's* voice-anonymization project** (not this repo),
copy `docs/domain.md` and `docs/claude-md-template.md` into that project for context.

---

## Critical domain facts — read before doing anything

**Metrics (never get these backwards):**
- EER (Equal Error Rate): **HIGHER = more private**. 50% = random = perfect anonymization.
- WER (Word Error Rate): **LOWER = more useful**. 0% = perfect transcription.
- Linkability (ZEBRA Cllr): **LOWER = harder to link speakers**.
- Always report **semi-informed** attacker condition — that's the VP2026 ranking metric.

**Baselines — run on YOUR VP2026 data, never use hardcoded numbers from older years:**
- B1 (McAdams): signal-processing, CPU, fast. Weak anonymization. The floor to beat.
- B2 (HuBERT + ECAPA-TDNN + HiFi-GAN): neural, GPU. Strong. The real target. NOT yet implemented in vpstack.

**B1 McAdams script:** The skill `vp-baseline-compare` contains a self-contained Python
script that Claude writes to `/tmp/vp_b1_run.py`. You can extract and run it directly:
```bash
# Extract and run B1 on your data
python3 /tmp/vp_b1_run.py --data_path /path/to/your/audio --seed 42
# Requires: pip install soundfile scipy numpy
```

---

## Running VP2026 skills as Codex

Skills are in `skills/*/SKILL.md`. Each is a step-by-step workflow.
To execute a skill as Codex:

1. Read the SKILL.md file
2. Follow the steps — run bash commands, write files, ask the user questions
3. Write experiment state to `~/.vpstack/projects/{slug}/`

Get your project slug:
```bash
~/.claude/skills/vpstack/bin/vpstack-slug
# or: python3 -c "import hashlib,os,subprocess; t=subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip(); print(f'{os.path.basename(t)}-{hashlib.sha256(t.encode()).hexdigest()[:8]}')"
```

Log an experiment (Write tool or direct file write):
```bash
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
cat > ~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json << 'EOF'
{
  "id": "your-exp-id",
  "date": "2026-04-29T00:00:00Z",
  "config_hash": "abc123",
  "metrics": {"eer": 38.2, "wer": 8.1},
  "method": "B1-alpha0.8",
  "hypothesis": "your hypothesis text"
}
EOF
```

---

## Workflow for a typical VP2026 experiment

```bash
# 1. Formalize hypothesis (read skills/vp-hypothesis/SKILL.md, follow steps)
# 2. Run B1 anonymization
python3 /tmp/vp_b1_run.py --data_path /path/to/data --seed 42

# 3. Run attacker (requires VP2026 challenge attacker script)
python3 run_attacker.py \
  --anonymized_path /path/to/anon \
  --enrollment_path /path/to/enrollment \
  --trial_list /path/to/trials.txt \
  --attacker_condition semi_informed \
  --output_format json --seed 42

# 4. Reproducibility check (read skills/vp-repro-check/SKILL.md)
grep -E "^seed: [0-9]+" your_config.yaml || echo "FAIL: seed missing"
grep -E "^(data|splits):" your_config.yaml || echo "FAIL: no splits"
grep -E "TODO|FILL_ME" your_config.yaml && echo "FAIL: placeholder hparams"

# 5. Log result (write summary.json as above)
```

---

## Project structure

```
skills/           15 SKILL.md workflows — follow these step by step
bin/              Bash scripts (slug, detect, skill-init, telemetry)
docs/domain.md    Full VP2026 domain reference (metrics, components, known issues)
docs/claude-md-template.md  Copy into user's project CLAUDE.md
tests/            Activation + telemetry tests (bash-based)
```

---

## Rules

1. **Never import VP2024 GitHub code** — it's GPLv3. Implement from the Eval Plan PDF.
2. **Never bundle pretrained weights** — fetch from HuggingFace at runtime.
3. **VP2026 metrics only** — do not use VP2020/VP2022 numbers as references.
4. **No Python code in this repo** — skills are markdown, bin/ is bash.
