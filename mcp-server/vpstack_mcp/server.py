"""vpstack-mcp stdio server.

Exposes 16 VP2026 voice-privacy tools to any MCP-aware AI agent (Claude Code,
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
    get_context,
    get_leaderboard,
    log_learning,
    check_audio_health,
    estimate_compute,
    anonymize_custom_data,
    generate_trial_file,
    export_results,
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
            "(NOT YET IMPLEMENTED — v0.2) Run the full VP2026 evaluation pipeline on the user's "
            "anonymization system. Will compute EER (overall + per-gender), WER, linkability, "
            "and side-channel metrics. Currently returns BASELINE_NOT_IMPLEMENTED. "
            "Use vp_run_attacker for privacy eval and vp_run_baseline for baseline comparisons."
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
            "/vp-baseline-compare, /vp-eval) to record results. "
            "Populate hypothesis/method/system_name/tags so vp_search_experiments can find results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "exp_id": {"type": "string"},
                "metrics": {"type": "object"},
                "config_hash": {"type": "string"},
                "hypothesis": {
                    "type": "string",
                    "description": "One-line hypothesis being tested. Indexed by vp_search_experiments.",
                },
                "method": {
                    "type": "string",
                    "description": "Short method name (e.g. 'hubert-layer6-farthest'). Indexed by search.",
                },
                "system_name": {
                    "type": "string",
                    "description": "Human name for this anonymization system variant. Indexed by search.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Free-form tags (e.g. ['semi-informed', 'b2-ablation']). Indexed.",
                },
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
    "vp_get_context": {
        "handler": get_context.handle,
        "description": (
            "One-call session restore for a voice-privacy research project. "
            "Returns: best EER experiment so far, last 5 experiments with metrics, "
            "active hypothesis, last spike verdict, EER trend (improving/declining), "
            "B1/B2 reference baselines, days to submission deadline (if set), and "
            "recent research learnings. Replaces 3-5 individual tool calls at session start. "
            "Call this first at the start of any research session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_learnings": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include recent learnings from learnings.jsonl.",
                },
            },
        },
    },
    "vp_get_leaderboard": {
        "handler": get_leaderboard.handle,
        "description": (
            "Rank all logged experiments by a metric (EER, WER, or linkability). "
            "Returns a sorted comparison table with B1/B2 reference rows and beats_B1/beats_B2 flags. "
            "Replaces N individual experiment reads with one call. "
            "Use when the researcher asks 'which was my best run?' or 'am I beating B2?'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["eer", "wer", "linkability"],
                    "default": "eer",
                    "description": "EER: higher=better (more private). WER: lower=better (more useful).",
                },
                "sort_order": {"type": "string", "enum": ["asc", "desc"]},
                "limit": {"type": "integer", "default": 50},
                "include_references": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include B1/B2 reference rows at the top.",
                },
            },
        },
    },
    "vp_log_learning": {
        "handler": log_learning.handle_log,
        "description": (
            "Persist a research insight to ~/.vpstack/projects/{slug}/learnings.jsonl. "
            "Use after a /vp-spike verdict, after debugging a known failure, or when the "
            "researcher explicitly notes a pattern. Learnings surface in future sessions "
            "via vp_get_context and /vp-implement pre-flight. "
            "Example: key='hubert-l6-short-utterances', "
            "insight='HuBERT layer 6 causes speaker leakage on utterances < 1s on LibriSpeech dev'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Short kebab-case identifier, e.g. 'hubert-layer6-short-utterances'.",
                },
                "insight": {
                    "type": "string",
                    "description": "1-3 sentences. Be specific: include components, values, and conditions.",
                },
                "type": {
                    "type": "string",
                    "enum": ["pitfall", "pattern", "preference", "architecture", "component", "data"],
                    "default": "pitfall",
                },
                "confidence": {"type": "integer", "default": 8, "description": "1-10. Observed in data=8-9, inferred=4-5."},
                "source": {
                    "type": "string",
                    "enum": ["observed", "user-stated", "inferred", "cross-model"],
                    "default": "observed",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related file paths for staleness detection.",
                },
                "component": {
                    "type": "string",
                    "description": "Component this relates to, e.g. 'hubert', 'ecapa-tdnn'.",
                },
            },
            "required": ["key", "insight"],
        },
    },
    "vp_get_learnings": {
        "handler": log_learning.handle_get,
        "description": (
            "Return logged research learnings, optionally filtered by query, type, or component. "
            "Use before /vp-spike or /vp-implement to surface known pitfalls and patterns. "
            "Returns newest first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring match against key and insight."},
                "type": {"type": "string", "enum": ["pitfall", "pattern", "preference", "architecture", "component", "data"]},
                "component": {"type": "string", "description": "Filter to a specific component."},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    "vp_check_audio_health": {
        "handler": check_audio_health.handle,
        "description": (
            "Pre-flight quality check on a directory of WAV files before running expensive GPU pipelines. "
            "Detects: sample rate mismatches (silent wrong results), clipping, mostly-silence utterances, "
            "stereo files (need downmixing), too-short or too-long files. "
            "Returns PASS / WARN / FAIL verdict with per-file issue list and aggregate stats. "
            "Run this before vp_run_baseline, vp_run_attacker, or vp_anonymize_custom_data."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_path": {"type": "string", "description": "Directory of WAV files to check."},
                "expected_sr": {"type": "integer", "default": 16000, "description": "Expected sample rate. VP2026 uses 16000 Hz."},
                "max_files_to_scan": {"type": "integer", "default": 100, "description": "Cap on files to inspect (for large directories)."},
            },
            "required": ["audio_path"],
        },
    },
    "vp_estimate_compute": {
        "handler": estimate_compute.handle,
        "description": (
            "Given a dataset size and anonymization method, estimate GPU hours, VRAM, disk space, "
            "wall-clock time, and rough cloud cost. Use before starting a large experiment to plan "
            "infrastructure (cloud GPU rental, storage allocation). "
            "All estimates are rough — benchmark on a small sample first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "total_hours_audio": {"type": "number", "description": "Total audio hours to process."},
                "num_speakers": {"type": "integer", "description": "Number of unique speakers."},
                "method": {"type": "string", "enum": ["B1", "B2", "custom_neural"], "default": "B2"},
                "task": {
                    "type": "string",
                    "enum": ["anonymize", "attacker_ignorant", "attacker_lazy_informed", "attacker_semi_informed", "full_eval"],
                    "default": "anonymize",
                },
                "gpu_type": {
                    "type": "string",
                    "enum": ["V100", "A100", "A10G", "RTX3090", "RTX4090", "CPU"],
                    "default": "A100",
                },
            },
            "required": ["total_hours_audio", "num_speakers"],
        },
    },
    "vp_anonymize_custom_data": {
        "handler": anonymize_custom_data.handle,
        "description": (
            "Anonymize any directory of WAV files using B1 (McAdams) — not just VP2026-format Kaldi data. "
            "Accepts any layout (nested subdirectories, arbitrary filenames). "
            "Preserves directory structure in output. Handles stereo by downmixing. "
            "Processes files individually so one corrupt file doesn't abort the batch. "
            "For medical speech, call-center audio, podcasts, or any non-benchmark use case. "
            "B2 neural method returns BASELINE_NOT_IMPLEMENTED (tracked for v0.2)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_path": {"type": "string", "description": "Input directory containing WAV files."},
                "output_path": {"type": "string", "description": "Output directory. Must not be inside input_path."},
                "method": {"type": "string", "enum": ["B1", "B2"], "default": "B1"},
                "alpha": {"type": "number", "default": 0.8, "description": "McAdams coefficient (B1 only). VP2026 canonical: 0.8."},
                "seed": {"type": "integer", "default": 42},
                "preserve_structure": {"type": "boolean", "default": True, "description": "Preserve input directory tree in output."},
                "overwrite": {"type": "boolean", "default": False, "description": "Overwrite existing output files."},
            },
            "required": ["input_path", "output_path"],
        },
    },
    "vp_generate_trial_file": {
        "handler": generate_trial_file.handle,
        "description": (
            "Generate a Kaldi-style speaker verification trial file from a directory of WAV files. "
            "Required for running vp_run_attacker on non-VP2026 custom datasets. "
            "Infers speaker IDs from subdirectory names or filename prefixes. "
            "Splits utterances into enrollment and trial sets, generates target (same-speaker) "
            "and nontarget (cross-speaker) pairs. Fully reproducible given the same seed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_dir": {"type": "string", "description": "Directory with WAV files, organized by speaker."},
                "output_path": {"type": "string", "description": "Where to write the trial file."},
                "speaker_id_source": {"type": "string", "enum": ["subdirectory", "filename_prefix"], "default": "subdirectory"},
                "n_target_pairs_per_speaker": {"type": "integer", "default": 5},
                "n_nontarget_pairs_per_speaker": {"type": "integer", "default": 5},
                "seed": {"type": "integer", "default": 42},
                "enrollment_fraction": {"type": "number", "default": 0.3},
                "min_utterances_per_speaker": {"type": "integer", "default": 2},
            },
            "required": ["audio_dir", "output_path"],
        },
    },
    "vp_export_results": {
        "handler": export_results.handle,
        "description": (
            "Export logged experiments as a publication-ready LaTeX table or CSV. "
            "LaTeX output uses booktabs style (\\toprule/\\midrule/\\bottomrule), "
            "bolds best value per metric column, and is formatted for ACL/Interspeech/ICASSP. "
            "Replaces Claude reading N individual summary.json files and hand-formatting a table. "
            "Include exp_ids to export specific experiments, or omit for all (newest first)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["latex", "csv"], "default": "latex"},
                "exp_ids": {"type": "array", "items": {"type": "string"}, "description": "Specific experiment IDs. Default: all."},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to include. Available: id, date, method, hypothesis, config_hash, tags, eer, wer, linkability.",
                },
                "sort_by": {"type": "string", "enum": ["eer", "wer", "linkability", "date", "id"], "default": "eer"},
                "limit": {"type": "integer", "default": 30},
                "caption": {"type": "string", "default": "Voice anonymization results on VP2026 dev set (semi-informed attacker)."},
                "label": {"type": "string", "default": "results"},
            },
        },
    },
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Advertise all vpstack tools to the MCP client."""
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
