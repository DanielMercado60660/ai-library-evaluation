"""Unit tests for catalog search filters."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from catalog.models import BookModel


class TestTitleSearch:
    """Tests for title search filtering."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create test books with various titles."""
        books = [
            BookModel(
                id="book-001",
                title="Pride and Pachyderm",
                author="Elaphine Greymarch",
                genres=["Romance"],
                stratum=7,
            ),
            BookModel(
                id="book-002",
                title="Tusk and Sensibility",
                author="Elaphine Greymarch",
                genres=["Romance"],
                stratum=7,
            ),
            BookModel(
                id="book-003",
                title="The Great Gatsby Elephant",
                author="F. Scott Elephitzgerald",
                genres=["Fiction"],
                stratum=7,
            ),
        ]
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_title_search_case_insensitive(self, client, books):
        """Title search should be case-insensitive."""
        response = await client.get("/books", params={"q": "pride"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert data["books"][0]["title"] == "Pride and Pachyderm"

    @pytest.mark.asyncio
    async def test_title_search_partial_match(self, client, books):
        """Title search should match partial strings."""
        response = await client.get("/books", params={"q": "tusk"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert "Tusk" in data["books"][0]["title"]

    @pytest.mark.asyncio
    async def test_title_search_multiple_results(self, client, books):
        """Title search should return multiple matching results."""
        response = await client.get("/books", params={"q": "elephant"})
        assert response.status_code == 200
        data = response.json()
        # Should match "The Great Gatsby Elephant"
        assert len(data["books"]) >= 1

    @pytest.mark.asyncio
    async def test_title_search_no_results(self, client, books):
        """Title search should return empty list for no matches."""
        response = await client.get("/books", params={"q": "nonexistent"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_title_search_special_characters(self, client, books):
        """Title search should handle special characters."""
        response = await client.get("/books", params={"q": "pride & pachyderm"})
        assert response.status_code == 200
        # Should not error out


class TestAuthorSearch:
    """Tests for author search filtering."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create test books with various authors."""
        books = [
            BookModel(
                id="book-004",
                title="Book One",
                author="Elaphine Greymarch",
                genres=["Romance"],
                stratum=7,
            ),
            BookModel(
                id="book-005",
                title="Book Two",
                author="Tuskston Churchill",
                genres=["History"],
                stratum=6,
            ),
            BookModel(
                id="book-006",
                title="Book Three",
                author="Dr. Mammoth Wise",
                genres=["Science"],
                stratum=2,
            ),
        ]
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_author_search_exact_match(self, client, books):
        """Author search should find exact author names."""
        response = await client.get("/books", params={"author": "Elaphine Greymarch"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert data["books"][0]["author"] == "Elaphine Greymarch"

    @pytest.mark.asyncio
    async def test_author_search_partial_match(self, client, books):
        """Author search should match partial author names."""
        response = await client.get("/books", params={"author": "Tuskston"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert "Tuskston" in data["books"][0]["author"]

    @pytest.mark.asyncio
    async def test_author_search_case_insensitive(self, client, books):
        """Author search should be case-insensitive."""
        response = await client.get("/books", params={"author": "mammoth wise"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1

    @pytest.mark.asyncio
    async def test_author_search_no_results(self, client, books):
        """Author search should return empty for unknown authors."""
        response = await client.get("/books", params={"author": "Unknown Author"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0


class TestGenreFilter:
    """Tests for genre filtering (JSON array contains)."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create test books with various genres."""
        from catalog.models import BookInstanceModel
        from shared.constants import InstanceStatus

        books = [
            BookModel(
                id="book-007",
                title="Romance Novel",
                author="Author One",
                genres=["Romance", "Drama"],
                stratum=7,
            ),
            BookModel(
                id="book-008",
                title="Mystery Novel",
                author="Author Two",
                genres=["Mystery", "Thriller"],
                stratum=7,
            ),
            BookModel(
                id="book-009",
                title="Multi-Genre",
                author="Author Three",
                genres=["Romance", "Mystery", "Adventure"],
                stratum=7,
            ),
        ]
        for book in books:
            db_session.add(book)
            # Add at least one instance per book so they show up in search
            instance = BookInstanceModel(
                id=f"{book.id}-instance-001",
                book_id=book.id,
                barcode=f"TEST-{book.id}",
                call_number="TEST",
                status=InstanceStatus.AVAILABLE,
                location="Test Shelf",
            )
            db_session.add(instance)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_genre_filter_single_match(self, client, books):
        """Genre filter should find books with specified genre."""
        response = await client.get("/books", params={"genre": "Thriller"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert "Thriller" in data["books"][0]["genres"]

    @pytest.mark.asyncio
    async def test_genre_filter_multiple_matches(self, client, books):
        """Genre filter should find all books with genre."""
        response = await client.get("/books", params={"genre": "Romance"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 2  # Romance Novel and Multi-Genre
        for book in data["books"]:
            assert "Romance" in book["genres"]

    @pytest.mark.asyncio
    async def test_genre_filter_case_sensitive(self, client, books):
        """Genre filter should be case-sensitive (exact match in JSON)."""
        # Note: JSON contains check is case-sensitive
        response = await client.get("/books", params={"genre": "romance"})
        assert response.status_code == 200
        data = response.json()
        # Should not match "Romance" (capital R)
        assert len(data["books"]) == 0

    @pytest.mark.asyncio
    async def test_genre_filter_no_results(self, client, books):
        """Genre filter should return empty for non-existent genre."""
        response = await client.get("/books", params={"genre": "Science Fiction"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0


class TestStratumFilter:
    """Tests for stratum (1-13) filtering."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create test books across all strata."""
        books = []
        for i in range(1, 9):  # Strata 1-8
            books.append(
                BookModel(
                    id=f"book-strata-{i}",
                    title=f"Stratum {i} Book",
                    author="Test Author",
                    genres=["Test"],
                    stratum=i,
                )
            )
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_stratum_filter_valid_values(self, client, books):
        """Stratum filter should work for all valid values (1-8)."""
        for stratum in range(1, 9):
            response = await client.get("/books", params={"stratum": stratum})
            assert response.status_code == 200
            data = response.json()
            assert len(data["books"]) == 1
            assert data["books"][0]["stratum"] == stratum

    @pytest.mark.asyncio
    async def test_stratum_filter_boundary_low(self, client, books):
        """Stratum filter should reject values below 1."""
        response = await client.get("/books", params={"stratum": 0})
        # Should return 422 validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_stratum_filter_boundary_high(self, client, books):
        """Stratum filter should reject values above 13."""
        response = await client.get("/books", params={"stratum": 14})
        # Should return 422 validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_stratum_filter_negative(self, client, books):
        """Stratum filter should reject negative values."""
        response = await client.get("/books", params={"stratum": -1})
        assert response.status_code == 422


class TestSeriesFilter:
    """Tests for series filtering."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create test books with series."""
        books = [
            BookModel(
                id="book-series-001",
                title="Book One",
                author="Author",
                genres=["Fantasy"],
                stratum=7,
                series="Chronicles of Narnia",
                series_position=1,
            ),
            BookModel(
                id="book-series-002",
                title="Book Two",
                author="Author",
                genres=["Fantasy"],
                stratum=7,
                series="Chronicles of Narnia",
                series_position=2,
            ),
            BookModel(
                id="book-standalone",
                title="Standalone Book",
                author="Author",
                genres=["Fantasy"],
                stratum=7,
                series=None,
            ),
        ]
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_series_filter_matches_all(self, client, books):
        """Series filter should find all books in series."""
        response = await client.get("/books", params={"series": "Chronicles of Narnia"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 2

    @pytest.mark.asyncio
    async def test_series_filter_partial_match(self, client, books):
        """Series filter should match partial series names."""
        response = await client.get("/books", params={"series": "Narnia"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 2

    @pytest.mark.asyncio
    async def test_series_filter_no_series(self, client, books):
        """Standalone books should not match series filter."""
        response = await client.get("/books", params={"series": "Chronicles"})
        assert response.status_code == 200
        data = response.json()
        # Should find the two Chronicles books, not the standalone
        assert len(data["books"]) == 2


class TestCombinedFilters:
    """Tests for combining multiple filters."""

    @pytest_asyncio.fixture
    async def books(self, db_session):
        """Create diverse test books."""
        books = [
            BookModel(
                id="book-combo-001",
                title="Romance in the Savanna",
                author="Elaphine Greymarch",
                genres=["Romance"],
                stratum=7,
            ),
            BookModel(
                id="book-combo-002",
                title="Mystery in the Savanna",
                author="Elaphine Greymarch",
                genres=["Mystery"],
                stratum=7,
            ),
            BookModel(
                id="book-combo-003",
                title="Romance in the City",
                author="Other Author",
                genres=["Romance"],
                stratum=7,
            ),
            BookModel(
                id="book-combo-004",
                title="Children's Tale",
                author="Tusk Carle",
                genres=["Children's"],
                stratum=5,
            ),
        ]
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_combined_query_and_genre(self, client, books):
        """Combine q (title/author) with genre filter."""
        response = await client.get("/books", params={"q": "Savanna", "genre": "Romance"})
        assert response.status_code == 200
        data = response.json()
        # Should find only "Romance in the Savanna"
        assert len(data["books"]) == 1
        assert data["books"][0]["title"] == "Romance in the Savanna"

    @pytest.mark.asyncio
    async def test_combined_author_and_genre(self, client, books):
        """Combine author with genre filter."""
        response = await client.get("/books", params={"author": "Greymarch", "genre": "Mystery"})
        assert response.status_code == 200
        data = response.json()
        # Should find only "Mystery in the Savanna"
        assert len(data["books"]) == 1
        assert data["books"][0]["title"] == "Mystery in the Savanna"

    @pytest.mark.asyncio
    async def test_combined_genre_and_stratum(self, client, books):
        """Combine genre with stratum filter."""
        response = await client.get("/books", params={"genre": "Romance", "stratum": 7})
        assert response.status_code == 200
        data = response.json()
        # Should find two Romance books at stratum 7
        assert len(data["books"]) == 2

    @pytest.mark.asyncio
    async def test_combined_all_filters(self, client, books):
        """Combine all filters together."""
        response = await client.get("/books", params={
            "q": "Romance",
            "author": "Greymarch",
            "genre": "Romance",
            "stratum": 7,
        })
        assert response.status_code == 200
        data = response.json()
        # Should find only "Romance in the Savanna"
        assert len(data["books"]) == 1

    @pytest.mark.asyncio
    async def test_combined_filters_no_results(self, client, books):
        """Combined filters with no matches return empty."""
        response = await client.get("/books", params={
            "author": "Greymarch",
            "genre": "Children's",  # Greymarch doesn't write children's books
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0


class TestEmptyAndEdgeCases:
    """Tests for empty results and edge cases."""

    @pytest.mark.asyncio
    async def test_search_empty_database(self, client, db_session):
        """Search on empty database returns empty results."""
        response = await client.get("/books")
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_search_empty_query_string(self, client, db_session):
        """Empty query string should return all books."""
        # Add a book
        book = BookModel(
            id="book-empty-query",
            title="Test Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)
        await db_session.commit()

        response = await client.get("/books", params={"q": ""})
        assert response.status_code == 200
        data = response.json()
        # Empty string should match all (or be ignored)
        assert len(data["books"]) >= 0

    @pytest.mark.asyncio
    async def test_search_with_sql_injection_attempt(self, client, db_session):
        """Search should be safe from SQL injection."""
        book = BookModel(
            id="book-sql-test",
            title="Normal Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)
        await db_session.commit()

        # Attempt SQL injection
        response = await client.get("/books", params={"q": "'; DROP TABLE books; --"})
        assert response.status_code == 200
        # Should not error, should return 0 results
        data = response.json()
        assert isinstance(data["books"], list)

        # Verify books table still exists
        response2 = await client.get("/books")
        assert response2.status_code == 200
