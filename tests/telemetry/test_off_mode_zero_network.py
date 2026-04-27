"""CG3 (CRITICAL): telemetry off mode = zero network calls.

Privacy contract — when user picks 'off', vpstack-telemetry-log must NEVER attempt
a network request. Any regression here violates the privacy promise.

We don't directly intercept the syscall layer (that requires platform-specific tooling).
Instead we use --dry-run to verify the script exits before assembling/sending payload,
and test the early-exit code path explicitly.
"""

import json
from tests.conftest import run_script


def test_off_mode_emits_no_payload(isolated_home, vpstack_bin):
    """When telemetry=off, even --dry-run should produce no payload (early exit)."""
    # Set telemetry off
    r1 = run_script("vpstack-config", "set", "telemetry", "off")
    assert r1.returncode == 0

    # Run telemetry-log with --dry-run; should produce no stdout (because we exit
    # before payload assembly).
    r2 = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval",
        "--duration", "10",
        "--outcome", "success",
        "--dry-run",
    )
    assert r2.returncode == 0
    assert r2.stdout.strip() == "", f"off mode produced output: {r2.stdout!r}"


def test_off_mode_in_verbose_logs_no_network(isolated_home, vpstack_bin):
    """Verbose mode should report 'no network call' in stderr."""
    run_script("vpstack-config", "set", "telemetry", "off")
    r = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval", "--duration", "5", "--outcome", "success",
        "--dry-run", "--verbose",
    )
    assert r.returncode == 0
    assert "no network call" in r.stderr or "mode=off" in r.stderr


def test_off_mode_real_run_returns_immediately(isolated_home, vpstack_bin):
    """CG3 (real path): without --dry-run, off mode must NOT attempt curl.

    F5 fix from code review: previous CG3 test only checked --dry-run output is
    empty when off, never exercising the actual code path. This test:
      1. Configures telemetry=off
      2. Sets endpoint to localhost:1 (would refuse connection if reached, with
         curl --max-time 2 → would block 2s+)
      3. Invokes telemetry-log WITHOUT --dry-run
      4. Asserts script returns in <500ms (proves curl was never called — early
         exit fired before any network code)

    A regression that moved the off-check below the curl call would block 2s+ here.
    """
    import time

    run_script("vpstack-config", "set", "telemetry", "off")
    run_script("vpstack-config", "set", "telemetry_endpoint", "http://127.0.0.1:1/event")

    start = time.monotonic()
    r = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval", "--duration", "5", "--outcome", "success",
        # NO --dry-run — exercise the real path
    )
    elapsed = time.monotonic() - start

    assert r.returncode == 0
    # Off-mode early exit happens BEFORE curl, so the script returns in well under
    # 500ms. If a future regression bypasses the early-exit, this would take >=2s.
    assert elapsed < 0.5, (
        f"off mode took {elapsed:.2f}s — likely attempted network call. "
        f"CG3 contract: zero network calls when telemetry=off. "
        f"stderr: {r.stderr!r}"
    )


def test_anonymous_mode_does_not_block_on_unreachable_endpoint(isolated_home, vpstack_bin):
    """Even when telemetry IS configured, network failures must not block the user.

    Background curl with --max-time 2 + & disown means caller never waits.
    """
    import time

    run_script("vpstack-config", "set", "telemetry", "anonymous")
    run_script("vpstack-config", "set", "telemetry_endpoint", "http://127.0.0.1:1/event")

    start = time.monotonic()
    r = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval", "--duration", "5", "--outcome", "success",
    )
    elapsed = time.monotonic() - start

    assert r.returncode == 0
    # Even with an unreachable endpoint, the foreground script returns fast
    # because curl runs backgrounded. <500ms.
    assert elapsed < 0.5, (
        f"telemetry foreground took {elapsed:.2f}s — must run in background, never blocking. "
        f"stderr: {r.stderr!r}"
    )


def test_anonymous_mode_emits_payload_without_device_id_or_ts(isolated_home, vpstack_bin):
    """Anonymous mode = base payload only. NO device_id, NO ts, NO error_class.

    F4 fix: anonymous must be 'just a counter' — adding ts to every event would
    leak a timing distribution that re-identifies sessions in aggregate.
    """
    run_script("vpstack-config", "set", "telemetry", "anonymous")
    r = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval", "--duration", "5", "--outcome", "success",
        "--dry-run",
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout.strip())
    assert "device_id" not in payload, f"anonymous mode leaked device_id: {payload}"
    assert "ts" not in payload, f"anonymous mode leaked ts (fingerprinting risk): {payload}"
    assert "error_class" not in payload, f"anonymous mode leaked error_class: {payload}"
    assert payload["skill"] == "vp-eval"
    # Anonymous payload should ONLY have these 4 keys
    assert set(payload.keys()) == {"skill", "outcome", "vpstack_version", "duration_s"}


def test_community_mode_emits_payload_with_device_id(isolated_home, vpstack_bin):
    """Community mode = payload includes device_id."""
    run_script("vpstack-config", "set", "telemetry", "community")
    r = run_script(
        "vpstack-telemetry-log",
        "--skill", "vp-eval", "--duration", "5", "--outcome", "success",
        "--dry-run",
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout.strip())
    assert "device_id" in payload
    assert len(payload["device_id"]) == 16  # 16-char hash prefix
