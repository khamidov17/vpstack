"""Tests for vp_check_reproducibility.

Covers the 5 reproducibility checks: seed, splits, checkpoints, hparams, determinism.
Includes regression tests for the false-PASS bug on checkpoint hashes (v0.1 audit).
"""

import os
from pathlib import Path

import pytest


def _write_config(tmp_path, content: str) -> str:
    cfg = tmp_path / "hparams.yaml"
    cfg.write_text(content)
    return str(cfg)


def _write_lockfile(tmp_path, content: str = "hubert: sha256:abc123\n") -> None:
    (tmp_path / "checkpoints.lock").write_text(content)


class TestSeedCheck:
    def test_missing_seed_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "data:\n  train: /data/train\ndeterministic: true\n")
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("seed missing" in i for i in r["result"]["issues"])

    def test_integer_seed_passes(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: 42\ndata:\n  train: /d\ndeterministic: true\n")
        r = handle(cfg)
        assert any("seed pinned: 42" in p for p in r["result"]["passed"])

    def test_string_seed_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: 'forty-two'\ndata:\n  train: /d\ndeterministic: true\n")
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("seed" in i and "integer" in i for i in r["result"]["issues"])

    def test_auto_derived_seed_fails(self, tmp_path):
        """Regression: auto-derived string seeds must be caught."""
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: auto_42\ndata:\n  train: /d\ndeterministic: true\n")
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("auto-derived" in i for i in r["result"]["issues"])


class TestCheckpointHashes:
    def test_matching_hashes_pass(self, tmp_path):
        """Hashes that match between config and lockfile should PASS."""
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\n"
            "checkpoints:\n  hubert: sha256:abc123\n",
        )
        _write_lockfile(tmp_path, "hubert: sha256:abc123\n")  # matching hash
        r = handle(cfg)
        passed_msgs = " ".join(r["result"]["passed"])
        assert "hash-verified" in passed_msgs or "hubert" in passed_msgs

    def test_mismatched_hash_fails(self, tmp_path):
        """Regression: hash mismatch between config and lockfile must produce FAIL.

        The audit found v0.1 reported PASS without comparing hashes.
        v0.1.1 implements actual comparison — mismatched hashes must fail.
        """
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\n"
            "checkpoints:\n  hubert: sha256:correct_hash\n",
        )
        _write_lockfile(tmp_path, "hubert: sha256:stale_wrong_hash\n")  # mismatch
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("mismatch" in i for i in r["result"]["issues"])

    def test_checkpoint_missing_from_lockfile_fails(self, tmp_path):
        """Checkpoint declared in config but absent from lockfile must fail."""
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\n"
            "checkpoints:\n  hubert: sha256:abc\n  hifigan: sha256:def\n",
        )
        _write_lockfile(tmp_path, "hubert: sha256:abc\n")  # hifigan missing
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("missing from lockfile" in i or "hifigan" in i for i in r["result"]["issues"])

    def test_missing_lockfile_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\ncheckpoints:\n  hubert: sha256:abc\n",
        )
        # No lockfile written
        r = handle(cfg)
        assert any("no checkpoints.lock" in i for i in r["result"]["issues"])


class TestHparamsPlaceholders:
    def test_todo_value_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\nhparams:\n  batch_size: TODO\n",
        )
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"
        assert any("placeholder" in i for i in r["result"]["issues"])

    def test_fill_me_value_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\nhparams:\n  lr: FILL_ME\n",
        )
        r = handle(cfg)
        assert r["result"]["status"] == "FAIL"

    def test_populated_hparams_pass(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\nhparams:\n  lr: 0.001\n  batch_size: 32\n",
        )
        r = handle(cfg)
        assert any("hparams populated" in p for p in r["result"]["passed"])


class TestDeterminism:
    def test_not_deterministic_without_seeds_fails(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: 42\ndata:\n  train: /d\n")
        r = handle(cfg)
        assert any("not deterministic" in i for i in r["result"]["issues"])

    def test_n_seeds_3_passes(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: 42\ndata:\n  train: /d\nn_seeds: 3\n")
        r = handle(cfg)
        assert any("n_seeds=3" in p for p in r["result"]["passed"])

    def test_torch_deterministic_passes(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(tmp_path, "seed: 42\ndata:\n  train: /d\ndeterministic: true\n")
        r = handle(cfg)
        assert any("deterministic" in p.lower() for p in r["result"]["passed"])


class TestFullPassAndFail:
    def test_nonexistent_config_returns_error(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        r = handle("/nonexistent/path/config.yaml")
        assert r["ok"] is False
        assert r["error"]["code"] == "DATA_MISSING"

    def test_full_clean_config_passes(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /data/train\n  dev: /data/dev\ndeterministic: true\nhparams:\n  lr: 0.001\n",
        )
        r = handle(cfg)
        assert r["result"]["status"] == "PASS"

    def test_vpstack_version_note_always_present(self, tmp_path):
        from vpstack_mcp.tools.check_reproducibility import handle
        cfg = _write_config(
            tmp_path,
            "seed: 42\ndata:\n  train: /d\ndeterministic: true\n",
        )
        r = handle(cfg)
        assert "vpstack_version_note" in r["result"]
        assert "lab notebook" in r["result"]["vpstack_version_note"]
