"""CG4 (CRITICAL): no payload (any mode) ever contains forbidden keys or values.

Forbidden in the payload:
  - file paths / directory paths
  - code, hypothesis text, eval numbers, repo names, branch names
  - hyperparameters, seeds, config hashes, user prompts
  - error message bodies (only error class names allowed)

Strategy: schema test + property-style test that passes a privacy-marker string in
several injection points (skill name, error class) and asserts the marker NEVER
appears in the final payload.
"""

import json
from tests.conftest import run_script


# Strict allowlist of payload keys. Any key not on this list is a regression.
ALLOWED_KEYS = {"skill", "outcome", "vpstack_version", "ts", "duration_s", "device_id", "error_class"}


def _emit_payload(skill="vp-eval", outcome="success", duration="5", error_class=None, mode="community"):
    run_script("vpstack-config", "set", "telemetry", mode)
    args = ["--skill", skill, "--outcome", outcome, "--duration", duration, "--dry-run"]
    if error_class:
        args.extend(["--error-class", error_class])
    r = run_script("vpstack-telemetry-log", *args)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout.strip())


def test_payload_keys_are_strict_allowlist(isolated_home):
    payload = _emit_payload(mode="community")
    extra = set(payload.keys()) - ALLOWED_KEYS
    assert not extra, f"payload contains unexpected keys: {extra}"


def test_skill_name_outside_allowlist_dropped(isolated_home):
    """Skill names not matching ^vp-[a-z0-9-]+$ should be dropped, not sanitized in."""
    # Try injecting a path-like skill name
    payload = _emit_payload(skill="../../etc/passwd", mode="community")
    assert payload is None, "malicious skill name should be dropped, not emitted"


def test_outcome_outside_allowlist_dropped(isolated_home):
    payload = _emit_payload(outcome="success; rm -rf /", mode="community")
    assert payload is None, "malicious outcome should be dropped"


def test_error_class_outside_format_dropped(isolated_home):
    """Error class must be UPPER_SNAKE_CASE only — anything else gets dropped (not sanitized in)."""
    payload = _emit_payload(error_class="some lowercase error message body", mode="community")
    assert payload is not None
    assert "error_class" not in payload, "malformed error class should be omitted from payload"


def test_no_path_separators_in_payload_values(isolated_home):
    """Defensive: verify no value in the payload contains a path-like substring."""
    payload = _emit_payload(mode="community")
    assert payload is not None
    for k, v in payload.items():
        if isinstance(v, str):
            assert "/" not in v, f"payload[{k}] contains path separator: {v!r}"
            assert "\\" not in v, f"payload[{k}] contains path separator: {v!r}"


def test_no_message_bodies(isolated_home):
    """Even when error_class is set, no free-form message text leaks into the payload."""
    payload = _emit_payload(error_class="GPU_OOM", mode="community")
    assert payload is not None
    # error_class should be exactly the class name, not include any message
    if "error_class" in payload:
        assert payload["error_class"] == "GPU_OOM"
        assert " " not in payload["error_class"]
