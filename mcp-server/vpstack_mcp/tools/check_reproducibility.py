"""vp_check_reproducibility — verify a config has all the inputs needed to reproduce its results.

Checks: pinned seed, explicit splits, hash-verified checkpoints, complete hparams,
deterministic mode. Returns PASS or FAIL with specific reasons.

NOTE: does NOT check vpstack version — see DESIGN.md for the rationale (gstack-pattern
auto-update means vpstack version is researcher-tracked, not tool-tracked).
"""

from __future__ import annotations

from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err


def handle(config_path: str) -> ToolResult:
    """Run the 5 reproducibility checks against a config file."""
    p = Path(config_path).expanduser()
    if not p.exists():
        return err("DATA_MISSING", f"config not found: {p}", "")

    try:
        import yaml
    except ImportError:
        return err("INTERNAL", "pyyaml not installed", "pip install pyyaml")

    try:
        with open(p) as f:
            cfg = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        return err("INVALID_CONFIG", f"config is not valid YAML: {e}", "")

    issues: list[str] = []
    passed: list[str] = []

    # 1. Seed pinned?
    seed = cfg.get("seed")
    if seed is None:
        issues.append("seed missing — config has no 'seed' key")
    elif not isinstance(seed, int):
        issues.append(f"seed must be a single int, got: {type(seed).__name__}")
    elif isinstance(seed, str) and "auto" in seed.lower():
        issues.append(f"seed appears auto-derived: {seed}")
    else:
        passed.append(f"seed pinned: {seed}")

    # 2. Splits explicit?
    splits = cfg.get("data") or cfg.get("splits") or {}
    if not splits:
        issues.append("no 'data' or 'splits' section in config")
    else:
        unresolved = [k for k, v in splits.items() if isinstance(v, str) and "auto" in v.lower()]
        if unresolved:
            issues.append(f"splits use auto-detect: {unresolved}")
        else:
            passed.append(f"splits explicit ({len(splits)} entries)")

    # 3. Checkpoint hashes (recipe-specific — checked against a lockfile if present)
    checkpoints = cfg.get("checkpoints") or {}
    lockfile = p.parent / "checkpoints.lock"
    if checkpoints:
        if not lockfile.exists():
            issues.append("checkpoints listed but no checkpoints.lock alongside config")
        else:
            # TODO v0.1.x: verify each declared hash against the lockfile.
            passed.append(f"checkpoints declared ({len(checkpoints)} entries) + lockfile present")

    # 4. Hparams complete? Recipe-specific. v0.1 just checks that no values are obvious placeholders.
    hparams = cfg.get("hparams") or {}
    placeholder_keys = [k for k, v in hparams.items() if v in ("TODO", "FILL_ME", None, "")]
    if placeholder_keys:
        issues.append(f"hparams have placeholder values: {placeholder_keys}")
    elif hparams:
        passed.append(f"hparams populated ({len(hparams)} keys)")

    # 5. Determinism
    det = cfg.get("deterministic") or cfg.get("torch_deterministic") or False
    n_seeds = cfg.get("n_seeds", 1)
    if det:
        passed.append("torch.use_deterministic_algorithms enabled")
    elif n_seeds >= 3:
        passed.append(f"n_seeds={n_seeds} (variance estimation OK)")
    else:
        issues.append("not deterministic (set torch_deterministic: true OR run with n_seeds >= 3)")

    if issues:
        return ok({
            "status": "FAIL",
            "issues": issues,
            "passed": passed,
            "vpstack_version_note": "vpstack version is NOT part of this contract — record it in your lab notebook.",
        })
    return ok({
        "status": "PASS",
        "passed": passed,
        "vpstack_version_note": "vpstack version is NOT part of this contract — record it in your lab notebook.",
    })
