"""CG6: vpstack-detect activates on voice-anonymization repos."""

from tests.conftest import run_script


def test_explicit_enabled_marker(isolated_home, make_voice_repo):
    repo = make_voice_repo("explicit_enabled")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("ENABLED_EXPLICIT")


def test_vp_config_yaml_triggers(isolated_home, make_voice_repo):
    repo = make_voice_repo("vp_config")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DETECTED_FIRST_RUN")
    assert "vp_config.yaml" in result.stdout


def test_speechbrain_dep_triggers(isolated_home, make_voice_repo):
    """F9 fix: speechbrain dep alone (no AND with name) should trigger detection."""
    repo = make_voice_repo("speechbrain_dep")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DETECTED_FIRST_RUN")
    assert "speechbrain" in result.stdout.lower()


def test_claude_md_voice_text_triggers(isolated_home, make_voice_repo):
    repo = make_voice_repo("claude_md")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DETECTED_FIRST_RUN")


def test_path_pattern_triggers(isolated_home, make_voice_repo):
    repo = make_voice_repo("path")
    assert "VP2026" in str(repo)
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DETECTED_FIRST_RUN")
