"""Tests for spoke catalog seeding from network seed manifest.

Validates that seed_spoke_catalog.py correctly creates per-library
catalog databases with the right books and instances.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, SQLModel, select

# Ensure scripts/ and catalog src are importable
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "catalog" / "src"))
sys.path.insert(0, str(ROOT / "shared" / "src"))

from seed_spoke_catalog import seed_library, load_manifest, find_library_entry
from catalog.models import BookModel, BookInstanceModel


MANIFEST_PATH = ROOT / "data" / "network_seed_manifest.json"

_db_counter = 0
_tmpdir = tempfile.mkdtemp(prefix="spoke_seed_test_")


@pytest.fixture
def manifest():
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _seed_to_tmpfile(library_code: str) -> tuple[Session, dict]:
    """Seed a library into a temp SQLite file, return session + result."""
    global _db_counter
    _db_counter += 1
    db_path = Path(_tmpdir) / f"{library_code}-{_db_counter}.db"
    db_url = f"sqlite:///{db_path}"
    result = seed_library(library_code, db_url)
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    session = Session(engine)
    return session, result


class TestSpokeSeeding:
    """Verify spoke catalogs are seeded correctly."""

    def test_mastodon_book_count(self, manifest):
        """Mastodon Institute should have 80 books (batch_07 + batch_03)."""
        session, result = _seed_to_tmpfile("mastodon-institute")
        try:
            expected = manifest["spokes"][0]["total_books"]  # 80
            assert result["books_seeded"] == expected
            db_count = session.exec(select(BookModel)).all()
            assert len(db_count) == expected
        finally:
            session.close()

    def test_tusk_book_count(self, manifest):
        """Tusk Conservatory should have 150 books (batch_02 + batch_05)."""
        session, result = _seed_to_tmpfile("tusk-conservatory")
        try:
            expected = manifest["spokes"][3]["total_books"]  # 150
            assert result["books_seeded"] == expected
            db_count = session.exec(select(BookModel)).all()
            assert len(db_count) == expected
        finally:
            session.close()

    def test_instances_generated_for_all_books(self):
        """Every seeded book should have at least one instance."""
        session, result = _seed_to_tmpfile("ivory-university")
        try:
            assert result["instances_generated"] > 0
            books = session.exec(select(BookModel)).all()
            for book in books:
                instances = session.exec(
                    select(BookInstanceModel).where(BookInstanceModel.book_id == book.id)
                ).all()
                assert len(instances) >= 1, f"Book {book.id} has no instances"
        finally:
            session.close()

    def test_spoke_dbs_have_no_overlap(self):
        """Spoke databases must not contain books from other libraries."""
        sessions = {}
        book_ids_by_lib = {}
        try:
            for code in ["mastodon-institute", "mammoth-valley", "ivory-university", "tusk-conservatory"]:
                session, _ = _seed_to_tmpfile(code)
                sessions[code] = session
                ids = {b.id for b in session.exec(select(BookModel)).all()}
                book_ids_by_lib[code] = ids

            codes = list(book_ids_by_lib.keys())
            for i, code_a in enumerate(codes):
                for code_b in codes[i + 1:]:
                    overlap = book_ids_by_lib[code_a] & book_ids_by_lib[code_b]
                    assert not overlap, (
                        f"Overlap between {code_a} and {code_b}: {overlap}"
                    )
        finally:
            for s in sessions.values():
                s.close()

    def test_hub_seeding(self, manifest):
        """Hub (hanno-memorial) should seed from its own sources."""
        session, result = _seed_to_tmpfile("hanno-memorial")
        try:
            expected = manifest["hub"]["total_books"]  # 150
            assert result["books_seeded"] == expected
        finally:
            session.close()

    def test_spoke_not_contain_hanno_books(self):
        """Spoke DBs must not contain Hanno Memorial books."""
        hanno_session, _ = _seed_to_tmpfile("hanno-memorial")
        mastodon_session, _ = _seed_to_tmpfile("mastodon-institute")
        try:
            hanno_ids = {b.id for b in hanno_session.exec(select(BookModel)).all()}
            mastodon_ids = {b.id for b in mastodon_session.exec(select(BookModel)).all()}
            overlap = hanno_ids & mastodon_ids
            assert not overlap, f"Mastodon contains Hanno books: {overlap}"
        finally:
            hanno_session.close()
            mastodon_session.close()

    def test_instance_barcodes_use_library_prefix(self):
        """Instance barcodes should use library-specific prefixes."""
        session, _ = _seed_to_tmpfile("mastodon-institute")
        try:
            instances = session.exec(select(BookInstanceModel)).all()
            assert len(instances) > 0
            for inst in instances[:10]:  # spot-check first 10
                assert inst.barcode.startswith("MAS-"), (
                    f"Expected MAS- prefix, got {inst.barcode}"
                )
        finally:
            session.close()

    def test_unknown_library_raises(self):
        """Seeding an unknown library should raise ValueError."""
        with pytest.raises(ValueError, match="not found in manifest"):
            seed_library("nonexistent-library")


class TestManifestLookup:
    """Verify manifest lookup helpers."""

    def test_find_hub(self, manifest):
        entry = find_library_entry(manifest, "hanno-memorial")
        assert entry is not None
        assert entry["name"] == "Hanno Memorial Library"

    def test_find_spoke(self, manifest):
        entry = find_library_entry(manifest, "ivory-university")
        assert entry is not None
        assert entry["name"] == "Ivory University Research Library"

    def test_find_missing(self, manifest):
        entry = find_library_entry(manifest, "does-not-exist")
        assert entry is None
