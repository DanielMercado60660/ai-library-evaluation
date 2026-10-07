"""SQL assertion definitions for forensic benchmark verification.

Each assertion is a deterministic SQL check that validates system invariants
after a benchmark run. Assertions execute against file-backed SQLite databases
persisted by the scenario fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class SQLAssertion:
    """Definition of a single forensic SQL assertion."""

    assertion_id: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    target_db: str  # "catalog" | "circulation"
    sql: str
    evaluate: Callable[[list[dict[str, Any]]], tuple[str, str]]
    """Callable that receives query rows and returns (status, evidence)."""


def _evaluate_inventory_conservation(rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Check that total instances == sum of all status buckets."""
    if not rows:
        return "fail", "No book_instances rows found in database."

    row = rows[0]
    total = row["total_instances"]
    available = row["available"]
    checked_out = row["checked_out"]
    transit_alloc = row["transit_alloc"]
    other = row["other"]
    accounted = available + checked_out + transit_alloc + other

    if total == accounted:
        return (
            "pass",
            f"Conservation holds: {total} total == "
            f"{available} available + {checked_out} checked_out + "
            f"{transit_alloc} transit + {other} other.",
        )
    return (
        "fail",
        f"Conservation violated: {total} total != "
        f"{available} available + {checked_out} checked_out + "
        f"{transit_alloc} transit + {other} other "
        f"(accounted={accounted}, drift={total - accounted}).",
    )


INVENTORY_CONSERVATION_SQL = """\
SELECT
    COUNT(*) AS total_instances,
    SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available,
    SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) AS checked_out,
    SUM(CASE WHEN status IN ('in_transit', 'hold_shelf', 'dropbox') THEN 1 ELSE 0 END) AS transit_alloc,
    SUM(CASE WHEN status NOT IN ('available', 'checked_out', 'in_transit', 'hold_shelf', 'dropbox') THEN 1 ELSE 0 END) AS other
FROM book_instances
"""


def _evaluate_financial_integrity(rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Check that per-patron fine accounting is balanced."""
    mismatches: list[str] = []
    for row in rows:
        total = row["total_charges"]
        paid = row["total_paid"]
        waived = row["total_waived"]
        outstanding = row["outstanding"]
        if abs(total - (paid + waived + outstanding)) > 0.01:
            mismatches.append(
                f"patron {row['patron_id']}: charges={total}, "
                f"paid={paid}, waived={waived}, outstanding={outstanding}"
            )

    if not mismatches:
        patron_count = len(rows)
        return (
            "pass",
            f"Financial integrity holds for {patron_count} patron(s). "
            "All fine ledgers balance.",
        )
    return (
        "fail",
        f"Financial integrity violated for {len(mismatches)} patron(s): "
        + "; ".join(mismatches),
    )


FINANCIAL_INTEGRITY_SQL = """\
SELECT
    p.id AS patron_id,
    COALESCE(SUM(f.amount), 0) AS total_charges,
    COALESCE(SUM(CASE WHEN f.paid = 1 THEN f.amount ELSE 0 END), 0) AS total_paid,
    COALESCE(SUM(CASE WHEN f.waived = 1 THEN f.amount ELSE 0 END), 0) AS total_waived,
    COALESCE(SUM(CASE WHEN f.paid = 0 AND f.waived = 0 THEN f.amount ELSE 0 END), 0) AS outstanding
FROM patrons p
LEFT JOIN fines f ON f.patron_id = p.id
GROUP BY p.id
"""


ASSERTION_REGISTRY: list[SQLAssertion] = [
    SQLAssertion(
        assertion_id="inventory_conservation_v1",
        severity="critical",
        description="Total book instances equal sum of status-bucketed counts.",
        target_db="catalog",
        sql=INVENTORY_CONSERVATION_SQL,
        evaluate=_evaluate_inventory_conservation,
    ),
    SQLAssertion(
        assertion_id="financial_integrity_v1",
        severity="critical",
        description="Patron fine ledgers balance (charges == paid + waived + outstanding).",
        target_db="circulation",
        sql=FINANCIAL_INTEGRITY_SQL,
        evaluate=_evaluate_financial_integrity,
    ),
]
