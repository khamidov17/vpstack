"""CG7 (CRITICAL): vp_log_experiment writes are atomic — no half-state on kill -9.

Strategy:
  1. Write a normal experiment, verify summary.json is complete.
  2. Verify the .tmp file does NOT exist after a successful write.
  3. Simulate a partial-write state (manually create a .tmp file) and verify a
     subsequent successful write replaces it cleanly.
"""

import json
import os
from pathlib import Path

import pytest


def test_log_experiment_writes_complete_json(isolated_home, monkeypatch):
    monkeypatch.chdir(isolated_home)
    # Make this dir look like a git repo so slug resolves
    import subprocess
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=isolated_home, check=True)

    from vpstack_mcp.tools.log_experiment import handle

    result = handle(
        exp_id="test-exp-001",
        metrics={"eer": 12.3, "wer": 8.1, "linkability": 0.42},
        config_hash="abc123def456",
    )

    assert result["ok"] is True
    summary_path = Path(result["result"]["path"])
    assert summary_path.exists()

    # Verify content
    with open(summary_path) as f:
        data = json.load(f)
    assert data["id"] == "test-exp-001"
    assert data["metrics"]["eer"] == 12.3
    assert data["config_hash"] == "abc123def456"

    # CG7: no .tmp file should remain after successful write
    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    assert not tmp_path.exists(), f"leftover .tmp file: {tmp_path}"


def test_invalid_exp_id_rejected(isolated_home, monkeypatch):
    monkeypatch.chdir(isolated_home)
    from vpstack_mcp.tools.log_experiment import handle

    # Path-traversal attempt
    result = handle(exp_id="../../etc/passwd", metrics={}, config_hash="x")
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_CONFIG"


def test_metrics_must_be_dict(isolated_home, monkeypatch):
    monkeypatch.chdir(isolated_home)
    from vpstack_mcp.tools.log_experiment import handle

    result = handle(exp_id="test-002", metrics="not a dict", config_hash="x")  # type: ignore
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_CONFIG"


def test_pre_existing_tmp_file_replaced_cleanly(isolated_home, monkeypatch):
    """If a previous run was killed mid-write leaving a .tmp behind, the next write succeeds and cleans up."""
    monkeypatch.chdir(isolated_home)
    import subprocess
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=isolated_home, check=True)

    from vpstack_mcp.tools.log_experiment import handle, _project_slug

    # F10 fix changed the slug to include a hash of the toplevel path. Resolve the
    # actual slug used by the production code rather than hardcoding it.
    slug = _project_slug()
    exp_dir = Path.home() / ".vpstack" / "projects" / slug / "experiments" / "test-003"
    exp_dir.mkdir(parents=True)
    stale_tmp = exp_dir / "summary.json.tmp"
    stale_tmp.write_text("CORRUPT_HALF_WRITE")

    # Now do a real write — should succeed and leave summary.json complete
    result = handle(exp_id="test-003", metrics={"eer": 10.0}, config_hash="x")
    assert result["ok"] is True

    summary = exp_dir / "summary.json"
    assert summary.exists()
    with open(summary) as f:
        data = json.load(f)  # must be valid JSON, not "CORRUPT_HALF_WRITE"
    assert data["id"] == "test-003"
