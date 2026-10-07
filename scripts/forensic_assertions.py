"""Forensic assertion runner for post-benchmark integrity verification.

Executes SQL assertions against file-backed SQLite databases persisted
during benchmark scenario runs, producing a structured report.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.eval.trace_schemas import (
    ForensicAssertionReport,
    ForensicAssertionResult,
    ForensicSeverity,
    TraceEventType,
)

from forensic_sql import ASSERTION_REGISTRY, SQLAssertion

if TYPE_CHECKING:
    from shared.eval.trace_writer import TraceWriter


class ForensicAssertionRunner:
    """Executes forensic SQL assertions against benchmark databases.

    Args:
        db_paths: Mapping of service name to SQLite database path.
        trace_writer: Optional trace writer for emitting assertion events.
    """

    def __init__(
        self,
        db_paths: dict[str, Path],
        trace_writer: TraceWriter | None = None,
    ) -> None:
        self._db_paths = db_paths
        self._trace_writer = trace_writer

    def _execute_sql(self, db_path: Path, sql: str) -> list[dict[str, Any]]:
        """Execute SQL against a SQLite database and return rows as dicts."""
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def run_assertion(self, assertion: SQLAssertion) -> ForensicAssertionResult:
        """Execute a single assertion and return its result."""
        db_path = self._db_paths.get(assertion.target_db)
        if db_path is None or not db_path.exists():
            return ForensicAssertionResult(
                assertion_id=assertion.assertion_id,
                status="fail",
                severity=ForensicSeverity(assertion.severity),
                sql=assertion.sql,
                result={},
                evidence=f"Database not found for target '{assertion.target_db}' at {db_path}.",
            )

        try:
            rows = self._execute_sql(db_path, assertion.sql)
            status, evidence = assertion.evaluate(rows)
            return ForensicAssertionResult(
                assertion_id=assertion.assertion_id,
                status=status,
                severity=ForensicSeverity(assertion.severity),
                sql=assertion.sql,
                result={"rows": rows},
                evidence=evidence,
            )
        except Exception as exc:
            return ForensicAssertionResult(
                assertion_id=assertion.assertion_id,
                status="fail",
                severity=ForensicSeverity(assertion.severity),
                sql=assertion.sql,
                result={"error": str(exc)},
                evidence=f"Assertion execution error: {exc}",
            )

    def run_all(self, run_id: str = "unknown") -> ForensicAssertionReport:
        """Execute all registered assertions and produce a report."""
        if self._trace_writer:
            self._trace_writer.emit(
                TraceEventType.ASSERTION_START,
                "forensic_assertions",
                payload={"assertion_count": len(ASSERTION_REGISTRY)},
            )

        results: list[ForensicAssertionResult] = []
        for assertion in ASSERTION_REGISTRY:
            result = self.run_assertion(assertion)
            results.append(result)

            if self._trace_writer:
                self._trace_writer.emit(
                    TraceEventType.ASSERTION_RESULT,
                    "forensic_assertions",
                    payload={
                        "assertion_id": result.assertion_id,
                        "status": result.status,
                        "severity": result.severity,
                    },
                )

        pass_count = sum(1 for r in results if r.status == "pass")
        fail_count = sum(1 for r in results if r.status == "fail")

        return ForensicAssertionReport(
            run_id=run_id,
            assertions=results,
            summary={"pass": pass_count, "fail": fail_count, "total": len(results)},
        )


def run_forensic_assertions(
    db_dir: Path,
    run_id: str = "unknown",
    trace_writer: TraceWriter | None = None,
) -> ForensicAssertionReport:
    """Convenience function to run all forensic assertions against a DB directory.

    Args:
        db_dir: Directory containing service SQLite databases.
        run_id: Benchmark run identifier.
        trace_writer: Optional trace writer.

    Returns:
        ForensicAssertionReport with all assertion results.
    """
    db_paths: dict[str, Path] = {}
    for service in ["catalog", "circulation", "ill", "registry"]:
        db_path = db_dir / f"{service}.db"
        if db_path.exists():
            db_paths[service] = db_path

    runner = ForensicAssertionRunner(db_paths=db_paths, trace_writer=trace_writer)
    return runner.run_all(run_id=run_id)
