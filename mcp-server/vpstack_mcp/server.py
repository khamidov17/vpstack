"""vpstack-mcp stdio server.

Exposes 7 VP2026 voice-privacy tools to any MCP-aware AI agent (Claude Code,
Claude Desktop, Codex, Cursor, Cline). Uses stdio transport — local subprocess,
no port management, no FastAPI process.

Run via:
    python -m vpstack_mcp.server     # or  vpstack-mcp  (entry point)
"""

import asyncio
import logging
import sys
from typing import Any

# MCP SDK — anthropic's reference Python implementation.
try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:
    print(
        "vpstack-mcp requires the 'mcp' package. Install with: pip install vpstack-mcp",
        file=sys.stderr,
    )
    raise

from vpstack_mcp import __version__
from vpstack_mcp.tools import (
    run_baseline,
    run_eval,
    run_attacker,
    check_submission,
    check_reproducibility,
    get_component_info,
    search_experiments,
    log_experiment,
)


logger = logging.getLogger("vpstack_mcp")
server = Server("vpstack-mcp")


# Tool registry — name → (handler, schema, description).
# Schemas use JSON Schema dialect that MCP clients understand.
_TOOLS: dict[str, dict[str, Any]] = {
    "vp_run_baseline": {
        "handler": run_baseline.handle,
        "description": (
            "Run a canonical VP2026 baseline (B1 McAdams or B2 neural) on the given data path. "
            "Returns EER / WER / linkability and a config hash for reproducibility tracking. "
            "Long-running: B1 ~5min, B2 ~45min on a single GPU. Streams progress to stderr."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "baseline": {"type": "string", "enum": ["B1", "B2"]},
                "data_path": {"type": "string"},
                "seed": {"type": "integer", "default": 42},
            },
            "required": ["baseline", "data_path"],
        },
    },
    "vp_run_eval": {
        "handler": run_eval.handle,
        "description": (
            "Run the full VP2026 evaluation pipeline on the user's anonymization system. "
            "Computes EER (overall + per-gender), WER, linkability, and side-channel metrics. "
            "Held-out 'test' split blocked unless explicit opt-in to prevent overfitting."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_path": {"type": "string"},
                "eval_set": {"type": "string", "enum": ["dev", "test"]},
                "seed": {"type": "integer", "default": 42},
                "official_test": {"type": "boolean", "default": False},
            },
            "required": ["system_path", "eval_set"],
        },
    },
    "vp_check_submission": {
        "handler": check_submission.handle,
        "description": (
            "Validate a submission directory against the VP2026 expected format. "
            "Returns a list of structural errors and warnings before the user attempts an upload."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"submission_path": {"type": "string"}},
            "required": ["submission_path"],
        },
    },
    "vp_check_reproducibility": {
        "handler": check_reproducibility.handle,
        "description": (
            "Verify a config has all the inputs needed to reproduce its results: "
            "pinned seed, explicit splits, hash-verified checkpoints, complete hparams, "
            "deterministic mode. Returns PASS or FAIL with specific reasons."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"config_path": {"type": "string"}},
            "required": ["config_path"],
        },
    },
    "vp_get_component_info": {
        "handler": get_component_info.handle,
        "description": (
            "Look up the tradeoff matrix for a known voice-privacy component "
            "(encoder, vocoder, anonymization method). Returns description, tradeoffs, "
            "and reference papers. Sources from a hand-curated YAML in the recipe package."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"component_name": {"type": "string"}},
            "required": ["component_name"],
        },
    },
    "vp_search_experiments": {
        "handler": search_experiments.handle,
        "description": (
            "Search the user's logged experiments at ~/.vpstack/projects/{slug}/experiments/. "
            "Backed by jsonl scan in v0.1 (fast for ~1000 experiments). Returns matching "
            "experiment IDs with summary metrics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    "vp_log_experiment": {
        "handler": log_experiment.handle,
        "description": (
            "Atomically log an experiment to ~/.vpstack/projects/{slug}/experiments/{exp_id}/. "
            "Atomic write contract: no half-state on kill -9. Used by skills (/vp-spike, "
            "/vp-baseline-compare, /vp-eval) to record results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "exp_id": {"type": "string"},
                "metrics": {"type": "object"},
                "config_hash": {"type": "string"},
            },
            "required": ["exp_id", "metrics", "config_hash"],
        },
    },
    "vp_run_attacker": {
        "handler": run_attacker.handle,
        "description": (
            "Run an ASV attacker against an anonymized output to measure how well anonymization "
            "hides the speaker. Three official VP2024/2026 conditions: ignorant (pretrained ECAPA, "
            "fast diagnostic), lazy_informed (pretrained ECAPA + anonymized enrollment, ~10min), "
            "semi_informed (ECAPA retrained on anonymized train-clean-360, the ranking attacker, "
            "~4-12h on a single GPU). Returns per-gender EER (the official privacy metric) plus "
            "linkability (ZEBRA Cllr). Use semi_informed as default unless the user explicitly "
            "asks for a fast diagnostic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "anonymized_path": {"type": "string"},
                "enrollment_path": {"type": "string"},
                "trial_list": {"type": "string"},
                "attacker_condition": {
                    "type": "string",
                    "enum": ["ignorant", "lazy_informed", "semi_informed"],
                },
                "attacker_arch": {"type": "string", "enum": ["ecapa_tdnn"], "default": "ecapa_tdnn"},
                "anonymizer_config": {"type": "string"},
                "seed": {"type": "integer", "default": 42},
            },
            "required": ["anonymized_path", "enrollment_path", "trial_list", "attacker_condition"],
        },
    },
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Advertise the 7 vpstack tools to the MCP client."""
    return [
        types.Tool(
            name=name,
            description=spec["description"],
            inputSchema=spec["inputSchema"],
        )
        for name, spec in _TOOLS.items()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]):
    """Dispatch a tool call. All tools return the structured ToolResult contract from errors.py.

    F3 fix from code review: when a tool returns ok=False, we signal protocol-level
    failure so MCP clients (Claude Desktop, Cursor) can branch on isError without
    parsing the JSON body. The structured error payload is still in the response
    so callers that DO parse get the typed error code + hint.

    Per the MCP SDK convention, returning a list of content items with isError=True
    on the response is the protocol-level error indicator. Different SDK versions
    have used either a tuple `(content, isError)` or a CallToolResult object; we
    return a CallToolResult shape if available, falling back to a list (which
    older SDKs treat as success-only). If your client doesn't see isError on
    failures, upgrade the `mcp` package or check SDK version.
    """
    import json

    if name not in _TOOLS:
        result = {
            "ok": False, "result": None,
            "error": {"code": "INTERNAL", "message": f"unknown tool: {name}",
                      "hint": "Check the tool name against vpstack-mcp's registered tools."},
        }
    else:
        handler = _TOOLS[name]["handler"]
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**arguments)
            else:
                result = handler(**arguments)
        except Exception as e:  # last-resort guard — never leak a stack trace
            logger.exception("tool %s raised", name)
            result = {
                "ok": False, "result": None,
                "error": {
                    "code": "INTERNAL",
                    "message": str(e)[:200],
                    "hint": "This is a vpstack bug — please file an issue with reproduction steps.",
                },
            }

    content = [types.TextContent(type="text", text=json.dumps(result))]

    # Try to return a structured CallToolResult with isError set. Different MCP
    # SDK versions expose this differently; we prefer the typed object when
    # available, fall back to a plain list otherwise.
    is_error = not result.get("ok", False)
    if hasattr(types, "CallToolResult"):
        return types.CallToolResult(content=content, isError=is_error)
    return content


async def run() -> None:
    """Run the stdio MCP server until the client disconnects."""
    logger.info("vpstack-mcp v%s starting (stdio)", __version__)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vpstack-mcp",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Entry point for the `vpstack-mcp` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
