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

**B1 McAdams:** Run via `vpstack-b1` binary:
```bash
# Run B1 on your data
vpstack-b1 --data_path /path/to/your/audio --seed 42
# Requires: pip install soundfile scipy numpy
```

---

## Running VP2026 skills as Codex

Skills are in `skills/vp-*/SKILL.md`. Each is a step-by-step workflow.
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

## Workflow for a typical experiment

### Step 0: Set up your domain (run once per project)

Follow `skills/vp-talk/SKILL.md` → Engineering mode. It asks 6 questions and writes:
`~/.vpstack/projects/{slug}/domain_config.yaml`

This config is automatically read by every subsequent skill.

```bash
# Check if you have a domain config:
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || python3 -c "import hashlib,os,subprocess; t=subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip(); print(f'{os.path.basename(t)}-{hashlib.sha256(t.encode()).hexdigest()[:8]}')")
cat ~/.vpstack/projects/$SLUG/domain_config.yaml 2>/dev/null || echo "No config — run /vp-talk first"
```

### Step 1: Formalize hypothesis

Follow `skills/vp-hypothesis/SKILL.md`. Writes to:
`~/.vpstack/projects/{slug}/hypotheses/{id}.md`

### Step 2: Run B1 anonymization (baseline anchor)

```bash
# Run B1 binary
vpstack-b1 --data_path /path/to/data --seed 42
# Requires: pip install soundfile scipy numpy
# ⚠ If your audio is not 16kHz: sox input.wav -r 16000 output.wav
```

### Step 3: Run your anonymization method (bring your own)

```bash
# OHNN/Selection/B2: use SpeechBrain or your own implementation
pip install speechbrain
# Follow your method's recipe
```

### Step 4: Evaluate (bring your own tools)

```bash
# EER (speaker verification):
pip install speechbrain  # use spkrec-ecapa-voxceleb

# WER (transcription quality):
pip install openai-whisper
whisper /path/to/anon_audio --model medium --language en

# PMOS/naturalness:
pip install utmos
python3 -c "from utmos import UTMOSScore; print(UTMOSScore().score('file.wav'))"
```

### Step 5: Reproducibility check

Follow `skills/vp-repro-check/SKILL.md` — 5 bash checks, PASS_STRONG or PASS_WEAK.

### Step 6: Log and ship

```bash
# Log result
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
# Write summary.json via Write tool (see skills/vp-baseline-compare/SKILL.md Step 6)

# Ship
# Follow skills/vp-ship/SKILL.md
```

---

## Project structure

```
skills/vp-*/SKILL.md   15 skill workflows — follow step by step
bin/                   Bash scripts (vpstack-slug, detect, skill-init, telemetry)
docs/domain.md         Full VP2026 domain reference (metrics, components, known issues)
docs/claude-md-template.md  Copy into user's project CLAUDE.md for Claude context
```

**Runtime state (written during research):**
```
~/.vpstack/projects/{slug}/
  domain_config.yaml      ← written by /vp-talk engineering mode
  hypotheses/*.md         ← written by /vp-hypothesis
  experiments/{id}/       ← written by each skill after running
  research-plans/*.md     ← written by /vp-talk research mode
  deferred-gates.jsonl    ← written by /vp-plan-eng-review
```

---

## Rules

1. **Never import VP2024 GitHub code** — it's GPLv3. Implement from the Eval Plan PDF.
2. **Never bundle pretrained weights** — fetch from HuggingFace at runtime.
3. **VP2026 metrics only** — do not use VP2020/VP2022 numbers as references.
4. **No Python code in this repo** — skills are markdown, bin/ is bash.
