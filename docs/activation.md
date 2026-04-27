# How auto-activation works

vpstack is installed globally (one copy in `~/.claude/skills/vpstack/`), but **only activates inside voice-anonymization projects**. On any other project — your Rails app, your Go CLI, your unrelated NLP repo — the skills exit silently and produce zero output.

This is the headline UX promise. It's enforced by `bin/vpstack-detect`, which every skill calls in its preamble.

## The detection state machine

Every skill invocation, `vpstack-detect` returns one of five states:

| State | Meaning | Skill behavior |
|---|---|---|
| `ENABLED_EXPLICIT` | `<repo>/.vpstack/enabled` marker present | Proceed normally |
| `DISABLED_EXPLICIT` | `<repo>/.vpstack/disabled` marker present | Exit silently |
| `DETECTED_CONFIRMED` | Heuristic match + user confirmed previously | Proceed normally |
| `DETECTED_FIRST_RUN` | Heuristic match, no prior decision | Show the AskUserQuestion prompt |
| `NO_MATCH` | No signal at all | Exit silently |

## Detection signals

`vpstack-detect` walks up from the current working directory (bounded by the git toplevel, your `$HOME`, or 16 levels max — whichever comes first) looking for any of these signals:

1. **Explicit marker:** `.vpstack/enabled` or `.vpstack/disabled` in any ancestor.
2. **`vp_config.yaml`** at the project root.
3. **`speechbrain` listed in deps** (`requirements.txt`, `pyproject.toml`, `environment.yml`, or `setup.py`). One signal alone is enough — no AND with name match. The first-run prompt covers false positives.
4. **`CLAUDE.md` or `README.md`** mentions `VP2026`, `voice anonymization`, `voice anonymisation`, or `voice privacy` (case-insensitive).
5. **Path matches:** anywhere in the path matches `*VP2026*`, `*voice-anon*`, or `*voice-privacy*` (with a few case variants).

Any one signal triggers `DETECTED_*`. The disabled marker always wins over the enabled marker (safer default).

## First-run prompt

The first time a vpstack skill runs inside a detected voice project, you see:

```
This project looks like voice-anonymization work
(matched: speechbrain dependency in requirements.txt).

Enable vpstack here?

  A) Yes, enable for this project
  B) No, silence vpstack on this project
  C) Ask me again next time
```

- **A** writes `<repo>/.vpstack/enabled` and adds the project hash to `~/.vpstack/projects-decided`. Future skill calls in this project skip the prompt.
- **B** writes `<repo>/.vpstack/disabled`. The project is silenced forever (until you delete the marker).
- **C** does nothing. Next call shows the prompt again.

You can pre-set either marker manually:

```bash
mkdir -p .vpstack
touch .vpstack/enabled    # always run vpstack here
# or
touch .vpstack/disabled   # never run vpstack here
```

The `.vpstack/` directory is tiny — just marker files. You can gitignore it (private project preferences) or commit it (team-wide opt-in/opt-out).

## Headless / CI mode

In non-interactive environments (no TTY, CI runners, pipes), the first-run prompt would block forever waiting for input. To prevent this, `vpstack-skill-init` automatically detects no-TTY contexts and treats `DETECTED_FIRST_RUN` as `DISABLED_EXPLICIT` — silent exit instead of a hung prompt.

You can also force this with the `--headless` flag if you want explicit behavior in scripts.

## Cache

`vpstack-detect` results are cached for 5 minutes per CWD at `~/.vpstack/cache/detect-{cwd_hash}`. This avoids re-walking the file tree on every skill invocation in a session. Bypass with `--no-cache`.

## Edge cases handled

- **Symlink loops** in parent walk — bounded by the 16-level cap.
- **Both markers present** — `disabled` always wins, with a warning to stderr.
- **Marker outside git toplevel but inside `$HOME`** — found (walk continues past git boundary up to HOME).
- **Deeply nested CWD** (>8 levels under marker) — found (regression test in `tests/activation/test_non_voice_silent.py::test_disabled_marker_found_from_deeply_nested_subdir`).
- **CI / no-TTY** — auto-headless, no hangs.
