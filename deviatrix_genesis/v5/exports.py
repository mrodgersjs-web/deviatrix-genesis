"""Export suite — generate reports in Markdown, JSON, and structured formats.

Usage::

    from deviatrix_genesis.v5.exports import ReportExporter

    exporter = ReportExporter(result)
    exporter.to_markdown("report.md")
    exporter.to_json("data.json")
    exporter.to_summary()  # one-liner
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["ReportExporter"]


class ReportExporter:
    """Export pipeline results in multiple formats."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def to_markdown(self, path: str | Path | None = None) -> str:
        """Generate a full Markdown report."""
        r = self.result
        lines = [
            "# Deviatrix Genesis — Run Report\n",
            f"**Brief:** {r.get('brief', 'N/A')}",
            f"**Seeds:** {r.get('seeds', [])}",
            f"**Rounds:** {r.get('n_rounds', 0)}",
            f"**Wall-clock:** {r.get('wall_clock_s', 0):.1f}s",
            f"**Packets:** {r.get('n_packets', 0)}",
            "",
        ]

        # Quality
        q = r.get("quality", {})
        if q:
            lines.extend([
                "## Quality Metrics\n",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Expeditions | {q.get('total_expeditions', 0)} |",
                f"| Pass rate | {q.get('pass_rate_pct', 0)}% |",
                f"| Wall breaches | {q.get('wall_breaches', 0)} |",
                f"| Z mean | {q.get('z_mean', 0):.2f} |",
                f"| Z median | {q.get('z_median', 0):.2f} |",
                f"| Z stdev | {q.get('z_stdev', 0):.2f} |",
                f"| Z range | [{q.get('z_min', 0):.2f}, {q.get('z_max', 0):.2f}] |",
                "",
            ])

        # Survivors
        survivors = r.get("survivors", [])
        if survivors:
            lines.extend([
                f"## Survivors ({len(survivors)})\n",
                "| Name | Z-Score | Band | Family |",
                "|------|---------|------|--------|",
            ])
            for s in survivors:
                lines.append(
                    f"| {s.get('name', '')} | {s.get('composite_z', 0):.2f} "
                    f"| {s.get('band', '')} | {s.get('mechanism_family', '')} |"
                )
            lines.append("")

        # Hybrids
        hybrids = r.get("hybrids", [])
        if hybrids:
            lines.extend([f"## Hybrids ({len(hybrids)})\n"])
            for h in hybrids:
                lines.append(f"* **{h.get('name', '')}** — parents: {h.get('parent_names', [])}")
            lines.append("")

        # Memory OS
        mem_ids = r.get("memory_ids_written", [])
        if mem_ids:
            lines.extend([f"## Memory OS Writes ({len(mem_ids)})\n"])
            for mid in mem_ids:
                lines.append(f"* `{mid}`")
            lines.append("")

        # Run ID
        if r.get("run_id"):
            lines.append(f"---\n*Run ID: {r['run_id']}*")

        md = "\n".join(lines)
        if path:
            Path(path).write_text(md)
        return md

    def to_json(self, path: str | Path | None = None) -> str:
        """Export as JSON."""
        # Strip non-serializable items
        clean = {k: v for k, v in self.result.items() if k != "quality"}
        if "quality" in self.result:
            clean["quality"] = self.result["quality"]
        text = json.dumps(clean, indent=2, default=str)
        if path:
            Path(path).write_text(text)
        return text

    def to_summary(self) -> str:
        """One-line summary."""
        r = self.result
        survivors = len(r.get("survivors", []))
        best_z = max(
            (s.get("composite_z", 0) for s in r.get("survivors", [])),
            default=0, key=abs,
        )
        return (
            f"Deviatrix: {survivors} survivors, best_z={best_z:.2f}, "
            f"{r.get('n_rounds', 0)} rounds, {r.get('wall_clock_s', 0):.1f}s"
        )

    def to_csv(self, path: str | Path | None = None) -> str:
        """Export survivors as CSV."""
        survivors = self.result.get("survivors", [])
        if not survivors:
            return ""

        headers = ["name", "composite_z", "band", "mechanism_family", "formula"]
        rows = [",".join(headers)]
        for s in survivors:
            row = [
                s.get("name", ""),
                str(s.get("composite_z", 0)),
                s.get("band", ""),
                s.get("mechanism_family", ""),
                f'"{s.get("formula", "")}"',
            ]
            rows.append(",".join(row))

        csv = "\n".join(rows)
        if path:
            Path(path).write_text(csv)
        return csv
