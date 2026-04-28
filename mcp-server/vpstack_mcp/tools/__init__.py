"""vpstack MCP tool implementations.

Each tool module exposes a `handle(**kwargs)` callable returning a ToolResult dict
(see vpstack_mcp.errors). Tools are sync unless they need async I/O.
"""
from vpstack_mcp.tools import (
    run_baseline,
    run_eval,
    run_attacker,
    check_submission,
    check_reproducibility,
    check_audio_health,
    estimate_compute,
    get_component_info,
    search_experiments,
    log_experiment,
    get_context,
    get_leaderboard,
    log_learning,
    anonymize_custom_data,
    generate_trial_file,
    export_results,
)

__all__ = [
    "run_baseline",
    "run_eval",
    "run_attacker",
    "check_submission",
    "check_reproducibility",
    "check_audio_health",
    "estimate_compute",
    "get_component_info",
    "search_experiments",
    "log_experiment",
    "get_context",
    "get_leaderboard",
    "log_learning",
    "anonymize_custom_data",
    "generate_trial_file",
    "export_results",
]
