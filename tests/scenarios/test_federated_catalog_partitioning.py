"""Tests for federated catalog partitioning integrity.

Verifies each library owns a distinct partition of the 635-book corpus
with no overlapping book IDs.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MANIFEST_PATH = DATA_DIR / "network_seed_manifest.json"


def _hub_book_ids() -> set[str]:
    """Load book IDs from the hub (Hanno Memorial) sources."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for src in manifest["hub"]["sources"]:
        data = json.loads((DATA_DIR / src["file"]).read_text(encoding="utf-8"))
        ids.update(b["id"] for b in data.get(src["key"], []))
    return ids


class TestFederatedCatalogPartitioning:
    """Partition integrity: each book belongs to exactly one library."""

    def test_hanno_holds_main_and_batch_01(self, synthetic_catalog_books):
        """Hanno catalog contains books from main catalog + batch_01."""
        hub_ids = _hub_book_ids()
        # Main catalog: book-001 to book-100
        for i in range(1, 101):
            assert f"book-{i:03d}" in hub_ids, f"book-{i:03d} missing from hub"
        # batch_01: book-101 to book-150
        for i in range(101, 151):
            assert f"book-{i:03d}" in hub_ids, f"book-{i:03d} missing from hub"
        assert len(hub_ids) == 150

    def test_mastodon_holds_histories_and_technical(self, spoke_holdings):
        """Mastodon has batch_07 (book-501–575) + batch_03 (book-226–230)."""
        books = spoke_holdings["mastodon-institute"]
        ids = {b["id"] for b in books}
        assert len(books) == 80
        # batch_07
        for i in range(501, 576):
            assert f"book-{i:03d}" in ids
        # batch_03
        for i in range(226, 231):
            assert f"book-{i:03d}" in ids

    def test_mammoth_holds_tragedies_fiction_modern(self, spoke_holdings):
        """Mammoth Valley has batch_06 + batch_10 + batch_08 = 165 books."""
        books = spoke_holdings["mammoth-valley"]
        assert len(books) == 165
        ids = {b["id"] for b in books}
        # batch_06: book-426 to book-500
        for i in range(426, 501):
            assert f"book-{i:03d}" in ids
        # batch_10: book-726 to book-740
        for i in range(726, 741):
            assert f"book-{i:03d}" in ids
        # batch_08: book-576 to book-650
        for i in range(576, 651):
            assert f"book-{i:03d}" in ids

    def test_ivory_holds_philosophy_and_ext_technical(self, spoke_holdings):
        """Ivory University has batch_04 (book-276–350) + batch_09 (book-651–665)."""
        books = spoke_holdings["ivory-university"]
        assert len(books) == 90
        ids = {b["id"] for b in books}
        for i in range(276, 351):
            assert f"book-{i:03d}" in ids
        for i in range(651, 666):
            assert f"book-{i:03d}" in ids

    def test_tusk_holds_poetry_and_translated(self, spoke_holdings):
        """Tusk Conservatory has batch_02 (book-151–225) + batch_05 (book-351–425)."""
        books = spoke_holdings["tusk-conservatory"]
        assert len(books) == 150
        ids = {b["id"] for b in books}
        for i in range(151, 226):
            assert f"book-{i:03d}" in ids
        for i in range(351, 426):
            assert f"book-{i:03d}" in ids

    def test_no_book_in_two_libraries(self, spoke_holdings):
        """No book ID appears in both hub and any spoke, or in two spokes."""
        hub_ids = _hub_book_ids()
        all_spoke_ids: dict[str, str] = {}  # book_id -> library_code
        duplicates: list[str] = []

        # Check hub vs spokes
        for lib_code, books in spoke_holdings.items():
            for book in books:
                bid = book["id"]
                if bid in hub_ids:
                    duplicates.append(f"{bid} in hanno-memorial and {lib_code}")
                if bid in all_spoke_ids:
                    duplicates.append(f"{bid} in {all_spoke_ids[bid]} and {lib_code}")
                all_spoke_ids[bid] = lib_code

        assert not duplicates, f"Overlapping book IDs: {duplicates[:5]}"

    def test_total_partition_covers_635(self, spoke_holdings):
        """Hub + all spokes = 635 total books."""
        hub_count = len(_hub_book_ids())
        spoke_count = sum(len(books) for books in spoke_holdings.values())
        assert hub_count + spoke_count == 635, (
            f"Hub ({hub_count}) + spokes ({spoke_count}) = {hub_count + spoke_count}"
        )

    def test_spoke_book_ids_are_valid_format(self, spoke_holdings):
        """All spoke book IDs match book-NNN pattern."""
        pattern = re.compile(r"^book-\d{3}$")
        for lib_code, books in spoke_holdings.items():
            for book in books:
                assert pattern.match(book["id"]), (
                    f"{lib_code}: invalid ID format {book['id']}"
                )

    def test_each_spoke_has_isbn_for_holdings_lookup(self, spoke_holdings):
        """Every spoke partition contains at least one book with an ISBN."""
        for lib_code, books in spoke_holdings.items():
            isbns = [b.get("isbn") for b in books if b.get("isbn")]
            assert len(isbns) > 0, f"{lib_code} has no books with ISBNs"
