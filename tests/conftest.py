"""pytest fixtures shared across vpstack tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"

# Make vpstack_mcp importable in tests without requiring `pip install -e mcp-server/`.
sys.path.insert(0, str(REPO_ROOT / "mcp-server"))
sys.path.insert(0, str(REPO_ROOT))  # for speechbrain_voice_anon


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """Redirect HOME to a tmp dir so tests don't pollute the user's real ~/.vpstack."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    yield fake_home


@pytest.fixture
def vpstack_bin():
    """Path to bin/ scripts. Tests invoke them as subprocesses."""
    return BIN_DIR


def run_script(name, *args, cwd=None, env=None, check=False):
    """Run a bin/ script and return the CompletedProcess. Inherits env unless overridden."""
    script = BIN_DIR / name
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [str(script), *args],
        cwd=str(cwd) if cwd else None,
        env=full_env,
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )


@pytest.fixture
def make_voice_repo(tmp_path):
    """Factory: create a voice-anonymization repo with a chosen detection signal."""
    counter = [0]

    def _make(signal: str = "speechbrain_dep") -> Path:
        counter[0] += 1
        repo = tmp_path / f"voice-repo-{counter[0]}"
        repo.mkdir()
        if signal == "vp_config":
            (repo / "vp_config.yaml").write_text("baseline: B1\n")
        elif signal == "speechbrain_dep":
            (repo / "requirements.txt").write_text("speechbrain>=1.0\nnumpy\n")
        elif signal == "claude_md":
            (repo / "CLAUDE.md").write_text("# This project works on voice anonymization for VP2026.\n")
        elif signal == "path":
            # Move repo to a path matching the pattern
            new_path = tmp_path / f"VP2026-system-{counter[0]}"
            repo.rename(new_path)
            return new_path
        elif signal == "explicit_enabled":
            (repo / ".vpstack").mkdir()
            (repo / ".vpstack" / "enabled").touch()
        elif signal == "explicit_disabled":
            (repo / ".vpstack").mkdir()
            (repo / ".vpstack" / "disabled").touch()
        else:
            raise ValueError(f"unknown signal: {signal}")
        return repo

    return _make


@pytest.fixture
def make_non_voice_repo(tmp_path):
    """Factory: create repos that should NEVER trigger vpstack."""
    counter = [0]

    def _make(kind: str = "rails") -> Path:
        counter[0] += 1
        repo = tmp_path / f"non-voice-{kind}-{counter[0]}"
        repo.mkdir()
        if kind == "rails":
            (repo / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'rails', '~> 7.0'\n")
            (repo / "README.md").write_text("# My Rails app\n")
        elif kind == "go-cli":
            (repo / "go.mod").write_text("module example.com/cli\n\ngo 1.21\n")
            (repo / "README.md").write_text("# CLI tool\n")
        elif kind == "python-ml":
            # Has ML deps but no voice signal — pure NLP project, for example
            (repo / "requirements.txt").write_text("torch\ntransformers\nscikit-learn\n")
            (repo / "README.md").write_text("# Sentiment classification model\n")
        else:
            raise ValueError(f"unknown kind: {kind}")
        return repo

    return _make
