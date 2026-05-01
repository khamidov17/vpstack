import os
import subprocess
import pytest
import shutil
from pathlib import Path

@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir()
    return repo_dir

def run_detect(cwd, extra_args=None):
    bin_path = Path(__file__).parent.parent / "bin" / "vpstack-detect"
    cmd = [str(bin_path.absolute()), "--no-cache"]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True
    )
    return result

def test_no_match_empty_dir(temp_repo):
    res = run_detect(temp_repo)
    assert res.stdout.strip().startswith("NO_MATCH")

def test_detect_via_marker(temp_repo):
    marker_dir = temp_repo / ".vpstack"
    marker_dir.mkdir()
    (marker_dir / "enabled").touch()

    res = run_detect(temp_repo)
    assert res.stdout.strip().startswith("ENABLED_EXPLICIT")

def test_detect_via_voice_pattern_in_path(tmp_path):
    voice_repo = tmp_path / "my-vp2026-project"
    voice_repo.mkdir()

    res = run_detect(voice_repo)
    assert res.stdout.strip().startswith("DETECTED_FIRST_RUN")
    assert "path matches voice pattern" in res.stdout

def test_detect_via_readme(temp_repo):
    readme = temp_repo / "README.md"
    readme.write_text("This is a VoicePrivacy project.")

    res = run_detect(temp_repo)
    assert res.stdout.strip().startswith("DETECTED_FIRST_RUN")
    assert "voice-related text in README.md" in res.stdout
