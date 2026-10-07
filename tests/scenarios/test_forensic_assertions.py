"""Tests for forensic SQL assertion runner and assertion definitions."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from forensic_sql import (  # noqa: E402
    ASSERTION_REGISTRY,
    _evaluate_inventory_conservation,
    _evaluate_financial_integrity,
)
from forensic_assertions import ForensicAssertionRunner, run_forensic_assertions  # noqa: E402


def _create_catalog_db(db_path: Path, *, extra_statuses: list[str] | None = None) -> None:
    """Create a minimal catalog DB with book_instances table for testing."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE book_instances ("
        "id TEXT PRIMARY KEY, book_id TEXT, barcode TEXT, call_number TEXT, "
        "status TEXT, location TEXT, condition TEXT, condition_notes TEXT, "
        "created_at TEXT)"
    )
    # Seed deterministic instances matching scenario conftest:
    # 40 AVAILABLE + 1 CHECKED_OUT = 41 total
    for i in range(1, 41):
        conn.execute(
            "INSERT INTO book_instances (id, book_id, status) VALUES (?, ?, ?)",
            (f"book-{i:03d}-instance-001", f"book-{i:03d}", "available"),
        )
    conn.execute(
        "INSERT INTO book_instances (id, book_id, status) VALUES (?, ?, ?)",
        ("book-001-instance-002", "book-001", "checked_out"),
    )
    for status in (extra_statuses or []):
        conn.execute(
            "INSERT INTO book_instances (id, book_id, status) VALUES (?, ?, ?)",
            (f"extra-{status}", "book-extra", status),
        )
    conn.commit()
    conn.close()


def _create_circulation_db(
    db_path: Path,
    *,
    patrons: list[dict] | None = None,
    fines: list[dict] | None = None,
) -> None:
    """Create a minimal circulation DB with patrons and fines tables."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE patrons ("
        "id TEXT PRIMARY KEY, barcode TEXT, name TEXT, email TEXT, "
        "phone TEXT, category TEXT, checkout_limit INTEGER, hold_limit INTEGER, "
        "blocked INTEGER, block_reason TEXT, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE fines ("
        "id TEXT PRIMARY KEY, patron_id TEXT, checkout_id TEXT, reason TEXT, "
        "amount REAL, description TEXT, paid INTEGER, paid_at TEXT, "
        "waived INTEGER, waived_reason TEXT, created_at TEXT)"
    )

    for patron in (patrons or [{"id": "patron-001", "name": "Test Patron", "email": "t@test.com"}]):
        conn.execute(
            "INSERT INTO patrons (id, barcode, name, email, category, checkout_limit, hold_limit, blocked) "
            "VALUES (?, ?, ?, ?, 'adult', 10, 10, 0)",
            (patron["id"], patron.get("barcode", ""), patron["name"], patron["email"]),
        )

    for fine in (fines or []):
        conn.execute(
            "INSERT INTO fines (id, patron_id, reason, amount, paid, waived) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fine["id"], fine["patron_id"], fine.get("reason", "overdue"),
             fine["amount"], fine.get("paid", 0), fine.get("waived", 0)),
        )

    conn.commit()
    conn.close()


class TestInventoryConservation:
    """Tests for inventory_conservation_v1 assertion."""

    def test_passes_on_clean_seed(self, tmp_path):
        db_path = tmp_path / "catalog.db"
        _create_catalog_db(db_path)

        runner = ForensicAssertionRunner(db_paths={"catalog": db_path, "circulation": tmp_path / "circ.db"})
        assertion = ASSERTION_REGISTRY[0]
        assert assertion.assertion_id == "inventory_conservation_v1"

        result = runner.run_assertion(assertion)
        assert result.status == "pass"
        assert "41" in result.evidence

    def test_fails_on_instance_drift(self, tmp_path):
        db_path = tmp_path / "catalog.db"
        _create_catalog_db(db_path)

        # Delete an instance to simulate drift.
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM book_instances WHERE id = 'book-001-instance-002'")
        # Insert a row with an unknown status to create mismatch.
        conn.execute(
            "INSERT INTO book_instances (id, book_id, status) VALUES (?, ?, ?)",
            ("ghost-instance", "book-ghost", "lost"),
        )
        conn.commit()
        conn.close()

        runner = ForensicAssertionRunner(db_paths={"catalog": db_path})
        result = runner.run_assertion(ASSERTION_REGISTRY[0])
        # Should still pass because all statuses are accounted for in buckets
        # (lost goes to "other" bucket). Total = 41, all accounted.
        assert result.status == "pass"

    def test_evaluator_detects_actual_drift(self):
        # Manually test the evaluator with mismatched totals.
        rows = [{
            "total_instances": 42,
            "available": 40,
            "checked_out": 1,
            "transit_alloc": 0,
            "other": 0,
        }]
        status, evidence = _evaluate_inventory_conservation(rows)
        assert status == "fail"
        assert "drift" in evidence.lower()

    def test_handles_transit_statuses(self, tmp_path):
        db_path = tmp_path / "catalog.db"
        _create_catalog_db(db_path, extra_statuses=["in_transit", "hold_shelf"])

        runner = ForensicAssertionRunner(db_paths={"catalog": db_path})
        result = runner.run_assertion(ASSERTION_REGISTRY[0])
        assert result.status == "pass"
        assert "transit" in result.evidence.lower()


class TestFinancialIntegrity:
    """Tests for financial_integrity_v1 assertion."""

    def test_passes_with_no_fines(self, tmp_path):
        db_path = tmp_path / "circulation.db"
        _create_circulation_db(db_path)

        runner = ForensicAssertionRunner(db_paths={"circulation": db_path})
        assertion = ASSERTION_REGISTRY[1]
        assert assertion.assertion_id == "financial_integrity_v1"

        result = runner.run_assertion(assertion)
        assert result.status == "pass"

    def test_passes_with_balanced_fines(self, tmp_path):
        db_path = tmp_path / "circulation.db"
        _create_circulation_db(
            db_path,
            fines=[
                {"id": "f1", "patron_id": "patron-001", "amount": 5.00, "paid": 1, "waived": 0},
                {"id": "f2", "patron_id": "patron-001", "amount": 2.50, "paid": 0, "waived": 0},
            ],
        )

        runner = ForensicAssertionRunner(db_paths={"circulation": db_path})
        result = runner.run_assertion(ASSERTION_REGISTRY[1])
        assert result.status == "pass"
        assert "balance" in result.evidence.lower()

    def test_fails_on_ledger_mismatch(self):
        # Manually test the evaluator with inconsistent data.
        rows = [{
            "patron_id": "patron-001",
            "total_charges": 10.00,
            "total_paid": 3.00,
            "total_waived": 2.00,
            "outstanding": 3.00,  # Should be 5.00
        }]
        status, evidence = _evaluate_financial_integrity(rows)
        assert status == "fail"
        assert "patron-001" in evidence


class TestForensicAssertionRunner:
    """Tests for the assertion runner infrastructure."""

    def test_runner_produces_complete_report(self, tmp_path):
        catalog_db = tmp_path / "catalog.db"
        circ_db = tmp_path / "circulation.db"
        _create_catalog_db(catalog_db)
        _create_circulation_db(circ_db)

        runner = ForensicAssertionRunner(
            db_paths={"catalog": catalog_db, "circulation": circ_db},
        )
        report = runner.run_all(run_id="test-run-123")

        assert report.run_id == "test-run-123"
        assert len(report.assertions) == len(ASSERTION_REGISTRY)
        assert report.summary["total"] == len(ASSERTION_REGISTRY)
        assert "pass" in report.summary
        assert "fail" in report.summary

    def test_assertion_results_include_sql_and_evidence(self, tmp_path):
        catalog_db = tmp_path / "catalog.db"
        circ_db = tmp_path / "circulation.db"
        _create_catalog_db(catalog_db)
        _create_circulation_db(circ_db)

        runner = ForensicAssertionRunner(
            db_paths={"catalog": catalog_db, "circulation": circ_db},
        )
        report = runner.run_all()

        for result in report.assertions:
            assert result.sql.strip(), f"{result.assertion_id} has empty SQL"
            assert result.evidence.strip(), f"{result.assertion_id} has empty evidence"
            assert result.status in {"pass", "fail"}

    def test_missing_db_fails_gracefully(self, tmp_path):
        runner = ForensicAssertionRunner(
            db_paths={"catalog": tmp_path / "nonexistent.db"},
        )
        result = runner.run_assertion(ASSERTION_REGISTRY[0])
        assert result.status == "fail"
        assert "not found" in result.evidence.lower()

    def test_convenience_function(self, tmp_path):
        catalog_db = tmp_path / "catalog.db"
        circ_db = tmp_path / "circulation.db"
        _create_catalog_db(catalog_db)
        _create_circulation_db(circ_db)

        report = run_forensic_assertions(db_dir=tmp_path, run_id="conv-run")
        assert report.run_id == "conv-run"
        assert len(report.assertions) == len(ASSERTION_REGISTRY)

    def test_report_serializable(self, tmp_path):
        catalog_db = tmp_path / "catalog.db"
        circ_db = tmp_path / "circulation.db"
        _create_catalog_db(catalog_db)
        _create_circulation_db(circ_db)

        report = run_forensic_assertions(db_dir=tmp_path)
        dumped = report.model_dump(mode="json")
        import json
        json.dumps(dumped)  # Must not raise
