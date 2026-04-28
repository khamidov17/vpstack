---
name: vp-baseline-compare
version: 0.1.0-dev
description: |
  Run B1 (McAdams) + B2 (neural) baselines on the same eval set as the user's anonymization system,
  return a delta table (EER / WER / linkability). Use when the user asks "how does my system compare
  to baseline?" or "is this better than B1?" or wants a quick sanity check of their anonymizer against
  canonical references. (vpstack)
  Voice triggers: "baseline compare", "vs B1", "vs B2".
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /vp-baseline-compare

Run the canonical VP2026 baselines and the user's system on the same eval set; return a structured comparison. This is the most-used skill — researchers run it after every meaningful system change to know if they're improving against the canonical references.

## Preamble (run first)

```bash
eval "$(~/.claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || .claude/skills/vpstack/bin/vpstack-skill-init 2>/dev/null || echo 'ACTIVATION=NO_MATCH')"

# Activation gate
case "$ACTIVATION" in
  NO_MATCH|DISABLED_EXPLICIT)
    exit 0
    ;;
  DETECTED_FIRST_RUN)
    # Skill body handles the AskUserQuestion below
    ;;
  ENABLED_EXPLICIT|DETECTED_CONFIRMED)
    # Proceed normally
    ;;
esac

# Surface upgrade if available — do not block
if [ -n "$UPGRADE_AVAILABLE" ]; then
  echo "vpstack upgrade available: $UPGRADE_AVAILABLE  (run: vpstack-upgrade)"
fi
```

## First-run gate

If `ACTIVATION` is `DETECTED_FIRST_RUN`, ask once via AskUserQuestion:

> "This project looks like voice-anonymization work (matched: $ACTIVATION_REASON). Enable vpstack here?"
>
> A) Yes, enable for this project (writes `<repo>/.vpstack/enabled`)
> B) No, silence vpstack on this project (writes `<repo>/.vpstack/disabled`)
> C) Ask me again next time

On answer:
- A → `mkdir -p .vpstack && touch .vpstack/enabled` and proceed
- B → `mkdir -p .vpstack && touch .vpstack/disabled` and exit silently
- C → `mkdir -p .vpstack && touch .vpstack/ask-later` and exit silently. Marker is valid for 60 minutes — vpstack-detect treats it as `DETECTED_CONFIRMED` during that window, preventing re-prompt loops in a multi-skill session. After 60min, the prompt fires again.

After A, also append the project hash to `~/.vpstack/projects-decided` so future runs skip the prompt:
```bash
PROJECT_HASH=$(printf '%s' "$PWD" | sha256sum 2>/dev/null | cut -c1-16 || printf '%s' "$PWD" | shasum -a 256 | cut -c1-16)
echo "$PROJECT_HASH" >> ~/.vpstack/projects-decided
```

## Workflow

### Step 1: Resolve the slug and timestamps

```bash
SLUG=$(~/.claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || .claude/skills/vpstack/bin/vpstack-slug 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
TEL_START=$(date +%s)
EXP_ID="baseline-compare-$(date +%Y%m%dT%H%M%S)"
```

### Step 2: Locate the user's system

Ask via AskUserQuestion:

> "Which anonymization system should I compare against B1 and B2?"
>
> A) Path to a directory with my anonymized audio (already-run system)
> B) Just run B1 — no user system comparison, I want canonical numbers

If A: ask for the path. Validate it exists and contains `.wav` files with:
```bash
ls "$USER_PATH"/*.wav 2>/dev/null | head -5
```
If no `.wav` files are found, report the error and stop.

If B: skip Step 3.

### Step 3: Collect user system metrics (if applicable)

If the user provided a pre-anonymized audio directory, note it for the comparison table. vpstack does not run a separate eval pipeline for arbitrary user systems in this version — the user should provide EER/WER values directly, or run their own eval script first.

Ask via AskUserQuestion:

> "Do you have EER and WER values for your system already, or should I just show the baseline numbers?"
>
> A) I have values — I'll paste them  B) Just show the baseline numbers

If A: ask the user to provide EER (%) and WER (%) for their system. Record them as `user_eer` and `user_wer`.

### Step 3.5: Pre-flight audio check (do this BEFORE running B1)

B1 (McAdams) is calibrated for 16 kHz mono speech. Wrong format → wrong anonymization with no error. Claude must check first:

```bash
# Check sample rate of first WAV file found
FIRST_WAV=$(find "$DATA_PATH" -name "*.wav" -maxdepth 6 | head -1)
if [ -n "$FIRST_WAV" ]; then
  # Try soxi (sox), then ffprobe, then python fallback
  SR=$(soxi -r "$FIRST_WAV" 2>/dev/null \
    || ffprobe -v quiet -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 "$FIRST_WAV" 2>/dev/null \
    || python3 -c "import soundfile as sf; print(sf.info('$FIRST_WAV').samplerate)" 2>/dev/null \
    || echo "unknown")
  CHANNELS=$(soxi -c "$FIRST_WAV" 2>/dev/null \
    || python3 -c "import soundfile as sf; print(sf.info('$FIRST_WAV').channels)" 2>/dev/null \
    || echo "unknown")
  echo "Sample rate: $SR Hz | Channels: $CHANNELS"
fi
```

**Interpret the output:**
- Sample rate is NOT 16000 → **STOP and warn**: "B1 assumes 16 kHz. Your audio is ${SR} Hz. Processing it will produce badly conditioned LPC and incorrect anonymization. Resample first: `sox input.wav -r 16000 output.wav` or `ffmpeg -i input.wav -ar 16000 output.wav`. Proceed anyway only if you understand the implications."
- Channels > 1 → **Warn** (do not block): "Audio has ${CHANNELS} channels — all channels will be averaged to mono. If you need a specific channel, pre-process with `sox input.wav remix 1` first."
- Sample rate unknown → warn and proceed with caution

Also validate alpha if the user is not using the default:
- alpha > 0.95 → warn: "alpha={alpha} is near 1.0 — the pole shift is minimal, producing almost no anonymization. Canonical B1 uses alpha=0.8."
- alpha < 0.6 → warn: "alpha={alpha} is below 0.6 — expect audible artifacts and WER regression, especially on fast speech. Consider alpha in [0.7, 0.9]."

### Step 4: Run B1 baseline (McAdams)

**B1 is signal-processing only — no neural models, no GPU needed.**

Write `/tmp/vp_b1_run.py` using the Write tool with this content, then run it:

```python
#!/usr/bin/env python3
"""McAdams B1 voice anonymization — Patino et al. VP2020.
Alpha=0.8, frame_length=20ms, hop=10ms, lpc_order=20 (canonical VP2026 settings).
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

import numpy as np
import scipy.signal
import soundfile as sf

def anonymize(waveform, sr, alpha=0.8, lpc_order=20, frame_ms=20, hop_ms=10, eps=1e-8):
    frame_len = int(sr * frame_ms / 1000)
    hop_len   = int(sr * hop_ms  / 1000)
    win = np.hanning(frame_len).astype(np.float32)
    n_frames = max(1, 1 + (len(waveform) - frame_len) // hop_len)
    padded = np.zeros((n_frames - 1) * hop_len + frame_len, np.float32)
    padded[:len(waveform)] = waveform
    out = np.zeros_like(padded); norm = np.zeros_like(padded)
    for i in range(n_frames):
        s, e = i * hop_len, i * hop_len + frame_len
        frame = padded[s:e] * win
        try:
            r = np.correlate(frame, frame, "full")[frame_len-1:frame_len+lpc_order]
            if r[0] < 1e-10: raise ValueError
            a = np.zeros(lpc_order+1); a[0] = 1.0; energy = r[0]
            for k in range(lpc_order):
                mu = -np.dot(a[:k+1], r[k+1:0:-1]) / energy
                a[1:k+2] += mu * a[k::-1][:k+1]; energy *= 1 - mu*mu
                if energy < 1e-12: break
            lpc = a.astype(np.float32)
            roots = np.roots(lpc)
            roots = roots[np.abs(roots) < 1-eps]
            mags = np.abs(roots); angs = np.angle(roots)
            mask = (np.abs(angs) > eps) & (np.abs(np.abs(angs) - np.pi) > eps)
            new_angs = angs.copy(); new_angs[mask] = np.sign(angs[mask]) * np.abs(angs[mask])**alpha
            new_lpc = np.real(np.poly(mags * np.exp(1j*new_angs))).astype(np.float32)
            if len(new_lpc) > len(lpc): new_lpc = new_lpc[:len(lpc)]
            elif len(new_lpc) < len(lpc): new_lpc = np.pad(new_lpc, (0, len(lpc)-len(new_lpc)))
            res = scipy.signal.lfilter(lpc, [1.0], frame)
            syn = scipy.signal.lfilter([1.0], new_lpc, res)
        except Exception:
            syn = frame
        out[s:e] += syn.astype(np.float32) * win; norm[s:e] += win
    out[norm > eps] /= norm[norm > eps]
    return out[:len(waveform)]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data_path", required=True)
    p.add_argument("--output_dir", default=None)
    p.add_argument("--alpha", type=float, default=0.8)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    np.random.seed(args.seed)
    data = Path(args.data_path).expanduser()
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else data / "anon_b1"
    wavs = sorted(data.rglob("*.wav"))
    if not wavs: print(f"No .wav files in {data}", file=sys.stderr); sys.exit(1)
    # Pre-flight sample rate check
    _, sr0 = sf.read(str(wavs[0]), frames=1, dtype="float32")
    if sr0 != 16000:
        print(f"WARNING: audio is {sr0} Hz, not 16000 Hz. B1 is calibrated for 16 kHz. "
              f"Resample with: sox input.wav -r 16000 output.wav", file=sys.stderr)
    n = 0; t0 = time.time(); last = t0
    for wav in wavs:
        audio, sr = sf.read(str(wav), dtype="float32")
        if audio.ndim > 1: audio = audio.mean(axis=1)
        anon = anonymize(audio, sr, args.alpha)
        dst = out_dir / wav.relative_to(data)
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), anon, sr); n += 1
        now = time.time()
        if now - last > 30 or n == len(wavs):
            eta = (len(wavs)-n) / (n/(now-t0)) if n/(now-t0) > 0 else 0
            print(f"B1: {n}/{len(wavs)} done, ETA {eta:.0f}s", file=sys.stderr, flush=True)
            last = now
    cfg = hashlib.sha256(f"B1:alpha={args.alpha}:seed={args.seed}".encode()).hexdigest()[:16]
    print(json.dumps({"ok": True, "n_files": n, "output_dir": str(out_dir), "config_hash": cfg}))
    return 0

if __name__ == "__main__": sys.exit(main())
```

Run it:
```bash
python3 /tmp/vp_b1_run.py --data_path "$DATA_PATH" --seed 42
```

**Dependencies (if missing):** `pip install soundfile scipy numpy`

**Reading the output:**
- JSON on stdout with `ok: true` → success, parse `output_dir` and `config_hash`
- Exit 1 with stderr message → error (wrong path, missing deps)
- Sample rate warning → inform the user and recommend resampling before proceeding

**B2 note:** B2 (HuBERT + ECAPA-TDNN + HiFi-GAN) is not yet part of vpstack. Tell the user: "B2 requires downloading pretrained models and a GPU. The VP2026 challenge provides the official B2 recipe at voiceprivacychallenge.org." B2 column shows "—" in the table.

### Step 5: Build the delta table

Construct the comparison table from available data. Use `"—"` for any metric that could not be obtained.

```
                        B1            B2            Yours
EER % (↑ = private)    [b1_eer]      not impl.     [user_eer or —]
WER % (↓ = useful)     [b1_wer]      not impl.     [user_wer or —]
Linkability (↓)         [b1_link]     not impl.     [user_link or —]

Δ vs B1:  EER [delta_eer]  WER [delta_wer]
```

Metric direction reminders (always show to user):
- EER: **higher = more private**. Random-chance ceiling is 50%. A perfect anonymizer would approach 50%.
- WER: **lower = more useful**. 0% = perfect transcription.
- Linkability: **lower = harder to link back to original speaker**.

Color guidance (if terminal supports ANSI):
- Green: user's system improves over B1 on the primary metric (EER)
- Yellow: mixed result (EER up but WER also up significantly)
- Red: regression vs B1

### Step 6: Log experiment

Use the Write tool to create the experiment summary. First ensure the directory exists:

```bash
mkdir -p ~/.vpstack/projects/$SLUG/experiments/$EXP_ID
```

Then use the Write tool to create `~/.vpstack/projects/$SLUG/experiments/$EXP_ID/summary.json` with contents:

```json
{
  "exp_id": "<EXP_ID>",
  "skill": "vp-baseline-compare",
  "timestamp": "<ISO 8601 timestamp>",
  "slug": "<SLUG>",
  "seed": 42,
  "b1": {
    "config_hash": "<from B1 stdout or null>",
    "n_files_anonymized": "<from B1 stdout or null>",
    "output_dir": "<from B1 stdout or null>",
    "eer": "<b1_eer or null>",
    "wer": "<b1_wer or null>"
  },
  "b2": null,
  "user_system": {
    "eer": "<user_eer or null>",
    "wer": "<user_wer or null>"
  },
  "notes": "<any BASELINE_NOT_IMPLEMENTED notices>"
}
```

### Step 7: Suggest next steps

Based on results:

- If the user's system EER is higher than B1 EER: "Your system shows stronger privacy than B1. Consider running `/vp-eval` when the full eval pipeline is implemented to validate on the held-out test set."
- If the user's system EER is lower than B1 EER: "Your system shows weaker privacy than B1. Try `/vp-spike` to ablate components and find what's hurting privacy."
- If B1 exited with `BASELINE_NOT_IMPLEMENTED` (exit 2): "B1 anonymization ran successfully but the EER/WER scoring pipeline is not yet implemented. Check `output_dir` for anonymized audio. Run your own ASV eval against it."
- If no user system was provided: "No user system compared. Try `/vp-hypothesis` to formalize your first ablation idea."

## Telemetry (run last)

```bash
TEL_END=$(date +%s)
TEL_DUR=$(( TEL_END - TEL_START ))
~/.claude/skills/vpstack/bin/vpstack-telemetry-log \
  --skill vp-baseline-compare \
  --duration "$TEL_DUR" \
  --outcome "$OUTCOME"
```

Where `OUTCOME` is one of: `success`, `error`, `abort`. On `error`, include `--error-class` (allowlist: `GPU_OOM`, `DATA_MISSING`, `INVALID_CONFIG`, `TIMEOUT`).

## Completion status

- DONE — table produced, experiment logged
- DONE_WITH_CONCERNS — B1 exited 2 (BASELINE_NOT_IMPLEMENTED); anonymization ran but no EER/WER scored
- BLOCKED — VP2026 data path missing or B1 recipe exited 1 (real error)

## Notes for skill authors

This is the canonical vpstack skill — every other skill follows the same shape:
1. Preamble with `vpstack-skill-init` (handles activation, version check, telemetry start)
2. Activation gate (exit silently on NO_MATCH / DISABLED)
3. First-run gate (AskUserQuestion if DETECTED_FIRST_RUN)
4. Workflow body (runs bash commands directly, uses Write tool for state)
5. Telemetry end (`vpstack-telemetry-log`)

Skills MUST NOT bypass the preamble — that's the privacy and silent-on-non-voice contract.
