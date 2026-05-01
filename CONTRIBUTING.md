# Contributing to vpstack

Thank you for your interest in contributing to vpstack! This project provides research infrastructure for voice-privacy AI agents.

## Architectural Principles

Before you contribute, please read [DESIGN.md](DESIGN.md) and [CLAUDE.md](CLAUDE.md). The most important principles are:

1.  **No Standalone Python in the Main Source**: This project uses a "Markdown Skills + Bash Binaries" model for maximum portability across AI coding agents.
2.  **Embedded Python for Computation**: For complex algorithms (like McAdams B1), we embed Python snippets inside bash scripts in `bin/` using heredocs.
3.  **Portability**: Skills (in `skills/`) should be pure Markdown that tells the agent what bash commands to run.
4.  **No GPLv3 Code**: Never import or vendor code from the official VP2024 baseline. Re-implement from the published Eval Plan PDF.

## How to Contribute

### Adding or Updating a Binary
- Binaries go in `bin/`.
- They should be bash scripts that orchestrate logic or run embedded Python.
- Always include a `--help` flag.
- Add a corresponding smoke test in `tests/test_binaries.py`.

### Adding or Updating a Skill
- Skills go in `skills/vp-{name}/SKILL.md`.
- Copy the preamble from an existing skill to ensure proper activation and telemetry.
- Skills must be self-contained.

### Running Tests
We use `pytest` for automated testing.
```bash
pip install -r requirements-test.txt  # (or install numpy, scipy, soundfile, pytest)
pytest -v tests/
```

## Release Process
1. Bump the version in `VERSION`.
2. Sync the version in `package.json`.
3. Push a tag `v*.*.*`. The GitHub Action will handle the npm publication.
