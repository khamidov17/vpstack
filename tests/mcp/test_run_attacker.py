"""Unit tests for vp_run_attacker MCP tool — input validation only (full attacker run = GPU)."""

from pathlib import Path


def test_invalid_condition_rejected():
    from vpstack_mcp.tools.run_attacker import handle
    r = handle(
        anonymized_path="/tmp/x",
        enrollment_path="/tmp/y",
        trial_list="/tmp/z",
        attacker_condition="bogus",
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "INVALID_CONFIG"
    assert "ignorant" in r["error"]["message"]


def test_fully_informed_rejected_with_helpful_hint():
    """User's mental model often confuses semi_informed with 'fully informed'.
    The error must educate, not just reject."""
    from vpstack_mcp.tools.run_attacker import handle
    r = handle(
        anonymized_path="/tmp/x",
        enrollment_path="/tmp/y",
        trial_list="/tmp/z",
        attacker_condition="fully_informed",
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "INVALID_CONFIG"
    assert "fully_informed is not a VPC official condition" in r["error"]["message"]
    assert "semi_informed" in r["error"]["hint"]


def test_invalid_arch_rejected():
    from vpstack_mcp.tools.run_attacker import handle
    r = handle(
        anonymized_path="/tmp/x",
        enrollment_path="/tmp/y",
        trial_list="/tmp/z",
        attacker_condition="ignorant",
        attacker_arch="resnet34_lora",  # reserved for v0.2
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "INVALID_CONFIG"


def test_semi_informed_requires_anonymizer_config():
    """Without the config, the attacker can't anonymize train-clean-360 — fail early with hint."""
    from vpstack_mcp.tools.run_attacker import handle
    r = handle(
        anonymized_path="/tmp/x",
        enrollment_path="/tmp/y",
        trial_list="/tmp/z",
        attacker_condition="semi_informed",
        # anonymizer_config intentionally omitted
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "INVALID_CONFIG"
    assert "anonymizer_config" in r["error"]["message"]


def test_missing_path_returns_data_missing(tmp_path):
    """When anonymized_path doesn't exist, surface DATA_MISSING with the standard hint."""
    from vpstack_mcp.tools.run_attacker import handle
    r = handle(
        anonymized_path=str(tmp_path / "does-not-exist"),
        enrollment_path=str(tmp_path / "does-not-exist-2"),
        trial_list=str(tmp_path / "trials.tsv"),
        attacker_condition="ignorant",
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "DATA_MISSING"


def test_path_with_no_wav_files_rejected(tmp_path):
    """Empty directory should fail before the recipe is invoked."""
    from vpstack_mcp.tools.run_attacker import handle

    anon_dir = tmp_path / "anon"
    enroll_dir = tmp_path / "enroll"
    anon_dir.mkdir()
    enroll_dir.mkdir()
    trial_list = tmp_path / "trials.tsv"
    trial_list.write_text("speaker1\tutt1\t1\n")

    r = handle(
        anonymized_path=str(anon_dir),
        enrollment_path=str(enroll_dir),
        trial_list=str(trial_list),
        attacker_condition="ignorant",
    )
    assert r["ok"] is False
    assert r["error"]["code"] == "DATA_MISSING"
    assert "no .wav files" in r["error"]["message"]
