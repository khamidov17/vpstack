"""vp_export_results — export logged experiments as a LaTeX table or CSV.

Every researcher eventually writes a paper. This tool reads logged experiments
from ~/.vpstack/projects/{slug}/experiments/ and produces:
  - LaTeX: ready-paste \begin{tabular} suitable for ACL/Interspeech/ICASSP papers
  - CSV: for spreadsheets, further analysis, or import into pandas

Token efficiency: replaces Claude reading N individual summary.json files and
then hand-formatting a table — one tool call, structured output.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any

from vpstack_mcp.errors import ToolResult, ok, err


def _project_slug() -> str:
    import hashlib
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        toplevel = out.decode().strip()
    except Exception:
        toplevel = os.getcwd()
    name = Path(toplevel).name or "unknown"
    h = hashlib.sha256(toplevel.encode()).hexdigest()[:8]
    return f"{name}-{h}"


def _is_valid(v: Any) -> bool:
    return isinstance(v, (int, float)) and not math.isnan(float(v))


def _fmt(v: Any, decimals: int = 1) -> str:
    if not _is_valid(v):
        return "---"
    return f"{float(v):.{decimals}f}"


def _load_experiments(exp_root: Path, exp_ids: list[str] | None, limit: int) -> list[dict]:
    if not exp_root.exists():
        return []
    rows = []
    dirs = sorted(exp_root.iterdir(), reverse=True)
    for d in dirs:
        if not d.is_dir():
            continue
        if exp_ids and d.name not in exp_ids:
            continue
        f = d / "summary.json"
        if not f.exists():
            continue
        try:
            with open(f) as fp:
                rows.append(json.load(fp))
        except (json.JSONDecodeError, OSError):
            continue
        if len(rows) >= limit:
            break
    return rows


def _to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for r in rows:
        m = r.get("metrics") or {}
        row = []
        for col in columns:
            if col == "id":
                row.append(r.get("id", ""))
            elif col == "date":
                row.append((r.get("date") or "")[:10])
            elif col == "method":
                row.append(r.get("method") or r.get("system_name") or "")
            elif col == "hypothesis":
                row.append((r.get("hypothesis") or "")[:60])
            elif col == "config_hash":
                row.append(r.get("config_hash", ""))
            elif col == "tags":
                row.append(", ".join(r.get("tags") or []))
            else:
                row.append(_fmt(m.get(col)) if _is_valid(m.get(col)) else m.get(col, ""))
        writer.writerow(row)
    return buf.getvalue()


def _to_latex(rows: list[dict], columns: list[str], caption: str, label: str, sort_by: str) -> str:
    """Generate a publication-ready LaTeX table (ACL/Interspeech style)."""
    metric_cols = [c for c in columns if c in ("eer", "wer", "linkability")]
    other_cols = [c for c in columns if c not in metric_cols]
    all_cols = other_cols + metric_cols

    # Column format: l for text, r for numbers
    col_fmt = ""
    for c in all_cols:
        col_fmt += "r" if c in metric_cols else "l"

    # Header row
    header_map = {
        "id": "System", "method": "Method", "date": "Date",
        "hypothesis": "Hypothesis", "config_hash": "Config",
        "eer": r"EER (\%) $\uparrow$", "wer": r"WER (\%) $\downarrow$",
        "linkability": r"Linkability $\downarrow$", "tags": "Tags",
    }

    lines = [
        r"\begin{table}[h]",
        r"  \centering",
        r"  \small",
        f"  \\begin{{tabular}}{{{col_fmt}}}",
        r"    \toprule",
        "    " + " & ".join(header_map.get(c, c.title()) for c in all_cols) + r" \\",
        r"    \midrule",
    ]

    # Find best value per metric column for bold highlighting
    best: dict[str, float] = {}
    for col in metric_cols:
        vals = [float(r.get("metrics", {}).get(col, float("nan")))
                for r in rows if _is_valid(r.get("metrics", {}).get(col))]
        if vals:
            # EER: higher is better; WER and linkability: lower is better
            best[col] = max(vals) if col == "eer" else min(vals)

    for r in rows:
        m = r.get("metrics") or {}
        cells = []
        for col in all_cols:
            if col == "id":
                val = (r.get("system_name") or r.get("id") or "").replace("_", r"\_")[:30]
            elif col == "method":
                val = (r.get("method") or "").replace("_", r"\_")[:20]
            elif col == "date":
                val = (r.get("date") or "")[:10]
            elif col == "hypothesis":
                val = (r.get("hypothesis") or "")[:40].replace("_", r"\_")
            elif col == "config_hash":
                val = r.get("config_hash", "")[:8]
            elif col == "tags":
                val = ", ".join(r.get("tags") or [])[:30]
            elif col in metric_cols:
                raw = m.get(col)
                if _is_valid(raw):
                    fval = float(raw)
                    formatted = _fmt(raw)
                    # Bold if this is the best value
                    if col in best and abs(fval - best[col]) < 1e-6:
                        val = r"\textbf{" + formatted + "}"
                    else:
                        val = formatted
                else:
                    val = "---"
            else:
                val = str(m.get(col, ""))
            cells.append(val)
        lines.append("    " + " & ".join(cells) + r" \\")

    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        f"  \\caption{{{caption}}}",
        f"  \\label{{tab:{label}}}",
        r"\end{table}",
        "",
        r"% Required packages: \usepackage{booktabs}",
        r"% EER: higher = more private (↑). WER: lower = better (↓).",
        r"% Best value per column shown in \textbf{bold}.",
        r"% Generated by vpstack vp_export_results.",
    ]
    return "\n".join(lines)


def handle(
    format: str = "latex",
    exp_ids: list[str] | None = None,
    columns: list[str] | None = None,
    sort_by: str = "eer",
    limit: int = 30,
    caption: str = "Voice anonymization results on VP2026 dev set (semi-informed attacker).",
    label: str = "results",
) -> ToolResult:
    """Export logged experiments as a LaTeX table or CSV.

    Args:
        format: "latex" or "csv". Default "latex".
        exp_ids: Optional list of specific experiment IDs to include. Default: all (newest first).
        columns: Columns to include. Default: ["id", "method", "eer", "wer", "linkability"].
                 Available: id, date, method, hypothesis, config_hash, tags, eer, wer, linkability.
        sort_by: Sort experiments by this metric before rendering. "eer" (desc), "wer" (asc).
        limit: Max experiments to include. Default 30.
        caption: LaTeX caption string. Default is a standard VP2026 caption.
        label: LaTeX label suffix (used as tab:{label}). Default "results".

    Returns:
        {"table": str, "format": str, "n_rows": int, "note": str}
    """
    if format not in ("latex", "csv"):
        return err("INVALID_CONFIG", f"format must be 'latex' or 'csv', got: {format!r}", "")
    if sort_by not in ("eer", "wer", "linkability", "date", "id"):
        return err("INVALID_CONFIG", f"sort_by must be one of: eer, wer, linkability, date, id", "")

    default_columns = ["id", "method", "eer", "wer", "linkability"]
    cols = columns if columns else default_columns
    valid_cols = {"id", "date", "method", "hypothesis", "config_hash", "tags", "eer", "wer", "linkability"}
    invalid = [c for c in cols if c not in valid_cols]
    if invalid:
        return err("INVALID_CONFIG", f"unknown columns: {invalid}", f"Valid: {sorted(valid_cols)}")

    slug = _project_slug()
    exp_root = Path.home() / ".vpstack" / "projects" / slug / "experiments"
    rows = _load_experiments(exp_root, exp_ids, limit)

    if not rows:
        return ok({
            "table": "",
            "format": format,
            "n_rows": 0,
            "note": (
                f"No experiments found at {exp_root}. "
                "Log experiments with vp_log_experiment first, then call vp_export_results."
            ),
        })

    # Sort
    desc = sort_by == "eer"

    def _sort_key(r: dict) -> tuple:
        v = r.get("metrics", {}).get(sort_by) if sort_by in ("eer", "wer", "linkability") else r.get(sort_by, "")
        has_v = _is_valid(v) if sort_by in ("eer", "wer", "linkability") else bool(v)
        num = float(v) if has_v and isinstance(v, (int, float)) else (float("-inf") if desc else float("inf"))
        return (0 if has_v else 1, -num if desc else num)

    rows.sort(key=_sort_key)

    if format == "csv":
        table = _to_csv(rows, cols)
    else:
        table = _to_latex(rows, cols, caption, label, sort_by)

    return ok({
        "table": table,
        "format": format,
        "n_rows": len(rows),
        "project_slug": slug,
        "note": (
            "Paste into your paper. Check all numbers against your logged experiments before submission. "
            "EER ↑ = more private. WER ↓ = better utility. Best value per column is bolded (LaTeX)."
        ),
    })
