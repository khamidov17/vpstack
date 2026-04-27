"""Tests for vp_check_submission against the actual VP2026 Eval Plan v1 layout.

Audit 2026-04-28 found the prior validator was checking an invented format
(JSON files, linkability.json, wrong gender split). This test exercises the
corrected validator against synthetic submission directories that match the
real VP2026 layout (Tables 8-9 of the plan).
"""

from pathlib import Path


def _make_track1_submission(root: Path, complete: bool = True) -> Path:
    """Build a minimal valid Track 1 submission tree under root/."""
    exp = root / "exp"
    (exp / "asr").mkdir(parents=True)
    (exp / "ser").mkdir(parents=True)
    (exp / "asv_ssl").mkdir(parents=True)
    (exp / "asv_anon_my_system").mkdir(parents=True)
    (exp / "results_summary" / "track1").mkdir(parents=True)

    header = "dataset,split,gender,enrollment,trial,EER\n"
    sample = "libri_dev,dev,Mixed,libri,libri,11.1\n"

    (exp / "asr" / "results_my_system.csv").write_text(header + sample.replace("EER", "WER"))
    (exp / "ser" / "results_my_system.csv").write_text(header + sample.replace("EER", "UAR"))
    (exp / "asv_ssl" / "results_my_system.csv").write_text(header + sample)
    (exp / "asv_anon_my_system" / "results_my_system.csv").write_text(header + sample)

    if complete:
        (exp / "results_summary" / "track1" / "result_for_rank_my_system").write_text("...")
        (exp / "results_summary" / "track1" / "result_for_submission_my_system.zip").write_text("zip-bytes")

    return root


def test_valid_track1_submission_passes(tmp_path):
    from vpstack_mcp.tools.check_submission import handle
    root = _make_track1_submission(tmp_path / "submission")
    r = handle(str(root))
    assert r["ok"] is True
    assert r["result"]["track"] == "track1"
    assert r["result"]["valid"] is True


def test_track1_missing_asv_semi_informed_fails(tmp_path):
    """The official ranking attacker output is not optional."""
    from vpstack_mcp.tools.check_submission import handle
    root = _make_track1_submission(tmp_path / "submission")
    # Remove the asv_anon directory entirely
    import shutil
    shutil.rmtree(root / "exp" / "asv_anon_my_system")

    r = handle(str(root))
    assert r["ok"] is False
    assert r["error"]["code"] == "MALFORMED_SUBMISSION"
    assert "asv_anon" in r["error"]["hint"].lower() or "asv_anon" in r["error"]["message"].lower()


def test_track1_missing_submission_archive_fails(tmp_path):
    from vpstack_mcp.tools.check_submission import handle
    root = _make_track1_submission(tmp_path / "submission")
    # Delete the .zip
    (root / "exp" / "results_summary" / "track1" / "result_for_submission_my_system.zip").unlink()

    r = handle(str(root))
    assert r["ok"] is False
    assert r["error"]["code"] == "MALFORMED_SUBMISSION"
    assert "result_for_submission" in r["error"]["hint"]


def test_unknown_layout_rejected(tmp_path):
    """Empty directory or random structure: track detection should fail clearly."""
    from vpstack_mcp.tools.check_submission import handle
    root = tmp_path / "empty"
    root.mkdir()
    r = handle(str(root))
    assert r["ok"] is False
    assert r["error"]["code"] == "MALFORMED_SUBMISSION"
    assert "Track 1 or Track 2" in r["error"]["message"]


def test_csv_with_wrong_columns_flagged(tmp_path):
    from vpstack_mcp.tools.check_submission import handle
    root = _make_track1_submission(tmp_path / "submission")
    # Corrupt the asv_ssl CSV to have wrong columns
    csv = root / "exp" / "asv_ssl" / "results_my_system.csv"
    csv.write_text("foo,bar,baz\n1,2,3\n")
    r = handle(str(root))
    assert r["ok"] is False
    assert "missing columns" in r["error"]["hint"]


def test_path_must_be_directory(tmp_path):
    from vpstack_mcp.tools.check_submission import handle
    f = tmp_path / "not_a_dir.txt"
    f.write_text("nope")
    r = handle(str(f))
    assert r["ok"] is False
    assert r["error"]["code"] == "INVALID_CONFIG"


def test_nonexistent_path_returns_data_missing(tmp_path):
    from vpstack_mcp.tools.check_submission import handle
    r = handle(str(tmp_path / "does-not-exist"))
    assert r["ok"] is False
    assert r["error"]["code"] == "DATA_MISSING"
