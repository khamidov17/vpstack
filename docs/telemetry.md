# Telemetry — what gets sent, what doesn't

vpstack telemetry exists to help the maintainer find broken skills and fix bugs faster. It is **opt-in**, has three modes, and is designed so the privacy contract is mechanically enforceable, not just promised.

## Three modes

| Mode | What gets sent | What it enables |
|---|---|---|
| `off` | **Nothing.** Zero network calls. The script short-circuits before payload assembly. | Maximum privacy. |
| `anonymous` | `{skill, outcome, vpstack_version, ts, duration_s}` only. No device ID, no session linkage. | Knowing if anyone is using vpstack at all. Counter only. |
| `community` | Anonymous fields + `device_id` (stable hash of `machine_uuid + username`) + `error_class` (UPPER_SNAKE_CASE only). | Trend tracking across versions, finding skills that break, fixing bugs faster. |

You're prompted to choose at install time. All three options are presented explicitly with `off` as a real first-class choice (no dark patterns).

Change anytime:

```bash
vpstack-config set telemetry off
vpstack-config set telemetry anonymous
vpstack-config set telemetry community
```

## What is NEVER sent (in any mode)

- **Code** — file contents, source, snippets, diffs.
- **File paths** — absolute or relative.
- **Hypothesis text, eval numbers, experiment IDs.** — your research data stays on your machine.
- **Repo names, branch names, project paths.**
- **Hyperparameters, seeds, config hashes.**
- **User-typed prompts.** — anything you typed to Claude is never seen by vpstack.
- **Error message bodies.** — only error class names (`GPU_OOM`, `DATA_MISSING`, etc.) — never the underlying message.

## Strict allowlist

The implementation in `bin/vpstack-telemetry-log` enforces a strict allowlist. The exact set of permitted payload keys:

```
{"skill", "outcome", "vpstack_version", "ts", "duration_s", "device_id", "error_class"}
```

Any key not in this set is dropped before serialization. This is enforced both at construction (in the Python helper) AND at the final filter step (defense in depth). Tested in `tests/telemetry/test_payload_sanitization.py::test_payload_keys_are_strict_allowlist`.

## Allowlist for values

Even within allowed keys, values are validated:

| Key | Allowed values |
|---|---|
| `skill` | Must match `^vp-[a-z0-9-]+$`. Anything else dropped (entire payload). |
| `outcome` | One of `success`, `error`, `abort`, `unknown`. Anything else dropped. |
| `error_class` | UPPER_SNAKE_CASE only, ≤32 chars. Anything else (including spaces, lowercase, message bodies) silently dropped from payload. |
| `duration_s` | Integer ≥0. Non-numeric strings cause the field to be omitted. |
| `device_id` | 16-char hex prefix of SHA-256(`machine_uuid::username`). Stable across vpstack versions on the same machine for same user. |

## Off mode contract

The contract for `off` mode is: **zero network calls, ever.** This is enforced by an early-exit at the top of `bin/vpstack-telemetry-log`:

```bash
if [ "$MODE" = "off" ]; then
  log "mode=off, no network call"
  exit 0
fi
```

The script returns before reading any input args (so even if you tried to inject something via `--skill`, it wouldn't matter — the script never gets that far). Tested in `tests/telemetry/test_off_mode_zero_network.py`.

## Network failure handling

Telemetry POSTs run in the background with a 2-second timeout and zero retries. If the endpoint is unreachable, slow, or returns 500, the user sees nothing — the skill workflow is never blocked. Errors are dropped silently because they don't affect researcher work.

## Self-hosted endpoint

The default endpoint is `https://telemetry.vpstack.dev/v1/event`. This is a vpstack-maintained Cloudflare Worker that:

- Accepts POST with the documented payload schema only.
- Logs to KV with a 90-day retention.
- Publishes the schema on the same domain so users can audit what is/isn't stored.
- Has no authentication (it's anonymous by design — auth would require user identity, which is the opposite of the privacy posture).

You can point at your own endpoint (e.g., for a research lab that wants to self-host its own aggregate stats):

```bash
vpstack-config set telemetry_endpoint https://your-server.example.com/event
```

## Auditing

Want to see what would be sent before it's sent? Use `--dry-run`:

```bash
vpstack-telemetry-log --skill vp-eval --duration 42 --outcome success --dry-run
```

Prints the payload to stdout, makes no network call. Same payload that would have been sent.

## Why this design

The privacy posture follows from one principle: **telemetry should only encode information the maintainer would publish in a public dashboard.** If the data feels uncomfortable on a public page, it shouldn't be sent at all. Skill names, outcomes, and durations are publishable. Code, paths, and research data are not.

The strict allowlist + early-exit + no retries + 2s timeout combine to make this principle structurally enforceable, not just a promise in the README.
