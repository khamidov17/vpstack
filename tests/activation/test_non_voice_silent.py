"""CG5 (CRITICAL): vpstack-detect returns NO_MATCH on non-voice repos.

This is the headline UX promise — vpstack must NEVER make noise on unrelated projects.
A regression here would mean a researcher with both VP2026 and a Rails app sees vpstack
chatter on their Rails work. Unacceptable.
"""

from tests.conftest import run_script


def test_rails_app_is_silent(isolated_home, make_non_voice_repo):
    repo = make_non_voice_repo("rails")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("NO_MATCH")


def test_go_cli_is_silent(isolated_home, make_non_voice_repo):
    repo = make_non_voice_repo("go-cli")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("NO_MATCH")


def test_python_ml_unrelated_is_silent(isolated_home, make_non_voice_repo):
    """Has torch + transformers but no voice signals — must NOT trigger."""
    repo = make_non_voice_repo("python-ml")
    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("NO_MATCH")


def test_disabled_marker_silences_even_with_voice_signals(isolated_home, make_voice_repo):
    """Marker precedence ([B2] in design): .disabled wins even if heuristics would otherwise fire."""
    repo = make_voice_repo("speechbrain_dep")
    (repo / ".vpstack").mkdir(exist_ok=True)
    (repo / ".vpstack" / "disabled").touch()

    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DISABLED_EXPLICIT")


def test_disabled_wins_over_enabled(isolated_home, make_voice_repo):
    """Both markers present = treat as disabled (safer default)."""
    repo = make_voice_repo("speechbrain_dep")
    (repo / ".vpstack").mkdir(exist_ok=True)
    (repo / ".vpstack" / "enabled").touch()
    (repo / ".vpstack" / "disabled").touch()

    result = run_script("vpstack-detect", "--no-cache", cwd=repo)
    assert result.returncode == 0
    assert result.stdout.startswith("DISABLED_EXPLICIT")


def test_disabled_marker_found_from_deeply_nested_subdir(isolated_home, make_voice_repo, tmp_path):
    """Regression: deeply-nested CWD (>8 levels) must still find .vpstack/disabled at project root.

    Bug history: original code capped parent walk at 8 levels. A researcher with .vpstack/disabled
    at project root and PWD inside a deep subdir (e.g. experiments/2026/04/27/run-12/logs/) would
    miss the marker and silently activate vpstack on what they explicitly disabled.
    """
    project = make_voice_repo("speechbrain_dep")
    (project / ".vpstack").mkdir(exist_ok=True)
    (project / ".vpstack" / "disabled").touch()

    # Create a 10-level-deep path inside the project
    deep = project
    for level in "abcdefghij":
        deep = deep / level
        deep.mkdir()

    result = run_script("vpstack-detect", "--no-cache", cwd=deep)
    assert result.returncode == 0
    assert result.stdout.startswith("DISABLED_EXPLICIT"), (
        f"Deep-walk regression: got {result.stdout!r} from PWD 10 levels under marker. "
        "The walk must reach project root."
    )
