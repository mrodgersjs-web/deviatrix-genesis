"""Persistent run history — SQLite-backed storage for pipeline runs.

Every run writes its full state (survivors, dropped, hybrids, quality
metrics, telemetry) so you can query trends across runs.

Usage::

    from deviatrix_genesis.v5.run_history import RunHistory

    history = RunHistory()
    run_id = history.record_run(result)
    recent = history.recent_runs(limit=10)
    trends = history.trend_analysis()
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["RunHistory", "RunRecord"]

_DEFAULT_DB = str(Path.home() / ".rig" / "deviatrix" / "run_history.db")


@dataclass
class RunRecord:
    run_id: str
    brief: str
    timestamp: float
    wall_clock_s: float
    n_rounds: int
    n_survivors: int
    n_dropped: int
    n_hybrids: int
    n_packets: int
    best_z: float
    median_z: float
    quality_json: str
    survivors_json: str
    full_result_json: str


class RunHistory:
    """SQLite-backed run history."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or _DEFAULT_DB
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    brief TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    wall_clock_s REAL NOT NULL,
                    n_rounds INTEGER NOT NULL,
                    n_survivors INTEGER NOT NULL,
                    n_dropped INTEGER NOT NULL,
                    n_hybrids INTEGER NOT NULL,
                    n_packets INTEGER NOT NULL,
                    best_z REAL NOT NULL,
                    median_z REAL NOT NULL,
                    quality_json TEXT NOT NULL,
                    survivors_json TEXT NOT NULL,
                    full_result_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)
            """)

    def record_run(self, result: dict[str, Any]) -> str:
        """Record a pipeline run result. Returns the run_id."""
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        survivors = result.get("survivors", [])
        z_values = [s.get("composite_z", 0.0) for s in survivors]

        record = RunRecord(
            run_id=run_id,
            brief=result.get("brief", ""),
            timestamp=time.time(),
            wall_clock_s=result.get("wall_clock_s", 0.0),
            n_rounds=result.get("n_rounds", 0),
            n_survivors=len(survivors),
            n_dropped=len(result.get("dropped", [])),
            n_hybrids=len(result.get("hybrids", [])),
            n_packets=result.get("n_packets", 0),
            best_z=max(z_values) if z_values else 0.0,
            median_z=sorted(z_values)[len(z_values) // 2] if z_values else 0.0,
            quality_json=json.dumps(result.get("quality", {}), default=str),
            survivors_json=json.dumps(survivors, default=str),
            full_result_json=json.dumps(result, default=str),
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.run_id, record.brief, record.timestamp,
                record.wall_clock_s, record.n_rounds, record.n_survivors,
                record.n_dropped, record.n_hybrids, record.n_packets,
                record.best_z, record.median_z, record.quality_json,
                record.survivors_json, record.full_result_json,
            ))

        return run_id

    def recent_runs(self, limit: int = 10) -> list[RunRecord]:
        """Get the most recent runs."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_run(self, run_id: str) -> RunRecord | None:
        """Get a specific run by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def trend_analysis(self, last_n: int = 20) -> dict[str, Any]:
        """Analyze trends across recent runs."""
        runs = self.recent_runs(limit=last_n)
        if not runs:
            return {"runs": 0}

        wall_times = [r.wall_clock_s for r in runs]
        best_zs = [r.best_z for r in runs]
        survivor_counts = [r.n_survivors for r in runs]
        round_counts = [r.n_rounds for r in runs]

        import statistics
        return {
            "runs": len(runs),
            "wall_clock": {
                "mean": round(statistics.mean(wall_times), 2),
                "median": round(statistics.median(wall_times), 2),
                "trend": "improving" if len(wall_times) > 1 and wall_times[-1] < wall_times[0] else "stable",
            },
            "best_z": {
                "mean": round(statistics.mean(best_zs), 2),
                "max": round(max(best_zs), 2),
                "trend": "improving" if len(best_zs) > 1 and best_zs[-1] > best_zs[0] else "stable",
            },
            "survivors": {
                "mean": round(statistics.mean(survivor_counts), 1),
                "trend": "improving" if len(survivor_counts) > 1 and survivor_counts[-1] > survivor_counts[0] else "stable",
            },
            "rounds": {
                "mean": round(statistics.mean(round_counts), 1),
            },
        }

    def _row_to_record(self, row: tuple) -> RunRecord:
        return RunRecord(
            run_id=row[0], brief=row[1], timestamp=row[2],
            wall_clock_s=row[3], n_rounds=row[4], n_survivors=row[5],
            n_dropped=row[6], n_hybrids=row[7], n_packets=row[8],
            best_z=row[9], median_z=row[10], quality_json=row[11],
            survivors_json=row[12], full_result_json=row[13],
        )
