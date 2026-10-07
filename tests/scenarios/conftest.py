"""Deterministic in-process fixtures for scenario benchmark tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, UTC

import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from catalog.db import get_session as get_catalog_session
from catalog.main import app as catalog_app
from catalog.models import BookModel, BookInstanceModel
from circulation.db import get_session as get_circulation_session
from circulation.main import app as circulation_app
from circulation.models import PatronModel, BookInstanceModel as CirculationBookInstanceModel
from ill.db import get_session as get_ill_session
from ill.main import app as ill_app
from registry.db import get_session as get_registry_session
from registry.main import app as registry_app
from registry.models import LibraryMetricsModel, PartnerLibraryModel
from registry.a2a_relay import relay_store
from shared.constants import InstanceStatus, ItemCondition


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CATALOG_SEED = DATA_DIR / "hanno_memorial_library_catalog.json"
PATRON_SEED = DATA_DIR / "hanno_patrons.json"
MANIFEST_PATH = DATA_DIR / "network_seed_manifest.json"


def _make_engine(service_name: str):
    """Create an async engine, using file-backed DB when BENCHMARK_DB_DIR is set."""
    db_dir = os.environ.get("BENCHMARK_DB_DIR")
    if db_dir:
        db_path = Path(db_dir) / f"{service_name}.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Remove stale DB from prior run so tables are recreated cleanly.
        if db_path.exists():
            db_path.unlink()
        url = f"sqlite+aiosqlite:///{db_path}"
    else:
        url = "sqlite+aiosqlite:///:memory:"
    return create_async_engine(url, echo=False, connect_args={"check_same_thread": False})


@pytest.fixture(scope="session")
def synthetic_catalog_books() -> list[dict]:
    """Load deterministic synthetic catalog records."""
    payload = json.loads(CATALOG_SEED.read_text(encoding="utf-8"))
    return payload["books"]


@pytest.fixture(scope="session")
def synthetic_patrons() -> list[dict]:
    """Load deterministic synthetic patron records."""
    return json.loads(PATRON_SEED.read_text(encoding="utf-8"))


@pytest_asyncio.fixture
async def catalog_client(synthetic_catalog_books):
    """In-process catalog service client seeded from synthetic catalog data."""
    engine = _make_engine("catalog")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    catalog_app.dependency_overrides[get_catalog_session] = override_session

    async with session_factory() as session:
        selected = synthetic_catalog_books[:40]
        for idx, book in enumerate(selected, start=1):
            model = BookModel(
                id=book["id"],
                title=book["title"],
                author=book["author"],
                isbn=book.get("isbn"),
                genres=book.get("genres", []),
                summary=book.get("summary"),
                publication_year=book.get("publication_year"),
                author_dates=book.get("author_dates"),
                stratum=book.get("stratum"),
                publisher=book.get("publisher"),
                page_count=book.get("page_count"),
                setting_era=book.get("setting_era"),
                series=book.get("series"),
                series_position=book.get("series_position"),
                shelf_location=book.get("shelf_location"),
                related_works=book.get("related_works", []),
                notes=book.get("notes"),
                in_library=book.get("in_library", True),
                illustrations=book.get("illustrations", False),
                illustrator=book.get("illustrator"),
                age_range=book.get("age_range"),
                reading_level=book.get("reading_level"),
            )
            session.add(model)

            # Deterministic copy counts for availability assertions.
            session.add(
                BookInstanceModel(
                    id=f"{book['id']}-instance-001",
                    book_id=book["id"],
                    barcode=f"HAN-ITEM-{idx:06d}",
                    call_number=f"CAT-{idx:04d}",
                    status=InstanceStatus.AVAILABLE,
                    location=book.get("shelf_location") or "General Stacks",
                    condition=ItemCondition.GOOD,
                )
            )
            if book["id"] == "book-001":
                session.add(
                    BookInstanceModel(
                        id=f"{book['id']}-instance-002",
                        book_id=book["id"],
                        barcode=f"HAN-ITEM-{(idx + 400):06d}",
                        call_number=f"CAT-{idx:04d}",
                        status=InstanceStatus.CHECKED_OUT,
                        location=None,
                        condition=ItemCondition.GOOD,
                    )
                )

        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=catalog_app),
        base_url="http://catalog-test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as client:
        yield client

    catalog_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def circulation_client(synthetic_patrons):
    """In-process circulation service client with deterministic patron/item state."""
    engine = _make_engine("circulation")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    circulation_app.dependency_overrides[get_circulation_session] = override_session

    async with session_factory() as session:
        for patron in synthetic_patrons[:5]:
            session.add(
                PatronModel(
                    id=patron["id"],
                    barcode=patron["barcode"],
                    name=patron["name"],
                    email=patron["email"],
                    phone=patron.get("phone"),
                    category=patron["category"],
                    checkout_limit=patron["checkout_limit"],
                    hold_limit=patron["hold_limit"],
                    blocked=False,
                    block_reason=None,
                )
            )

        session.add(
            CirculationBookInstanceModel(
                id="book-001-instance-001",
                book_id="book-001",
                barcode="HAN-CIRC-000001",
                call_number="SCN-0001",
                status=InstanceStatus.AVAILABLE.value,
                location="Scenario Shelf",
                condition="good",
            )
        )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=circulation_app),
        base_url="http://circulation-test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as client:
        yield client

    circulation_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def ill_client():
    """In-process ILL service client with isolated state."""
    engine = _make_engine("ill")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    ill_app.dependency_overrides[get_ill_session] = override_session

    async with AsyncClient(
        transport=ASGITransport(app=ill_app),
        base_url="http://ill-test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as client:
        yield client

    ill_app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def registry_client():
    """In-process registry service client with partner library seed."""
    relay_store.clear()
    engine = _make_engine("registry")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    registry_app.dependency_overrides[get_registry_session] = override_session

    async with session_factory() as session:
        for code, name, loan_days in [
            ("mastodon-institute", "Mastodon Institute Library", 28),
            ("mammoth-valley", "Mammoth Valley Library", 28),
            ("ivory-university", "Ivory University Library", 28),
            ("tusk-conservatory", "Tusk Conservatory Archives", 21),
        ]:
            partner = PartnerLibraryModel(
                code=code,
                name=name,
                display_name=name,
                status="active",
                lending_enabled=True,
                borrowing_enabled=True,
                loan_period_days=loan_days,
                member_since=datetime.now(UTC),
            )
            session.add(partner)
            session.add(
                LibraryMetricsModel(
                    library_code=code,
                    last_updated=datetime.now(UTC),
                )
            )
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=registry_app),
        base_url="http://registry-test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as client:
        yield client

    registry_app.dependency_overrides.clear()
    relay_store.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Chaos injection fixtures (v1.3)
# ---------------------------------------------------------------------------

# Add scripts/ to path so chaos modules are importable in test context.
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


@pytest.fixture
def chaos_controller(request):
    """Load a ChaosController from the ``@pytest.mark.chaos_profile`` marker.

    Usage::

        @pytest.mark.chaos_profile("a2a_timeout_on_send", seed=42)
        def test_something(chaos_controller, chaotic_ill_client):
            ...

    Returns ``None`` when the marker is absent so existing tests are unaffected.
    """
    marker = request.node.get_closest_marker("chaos_profile")
    if marker is None:
        return None

    from chaos_profiles import load_profile
    from chaos_controller import ChaosController as _ChaosController

    profile_id = marker.args[0] if marker.args else marker.kwargs.get("profile_id")
    seed = marker.kwargs.get("seed", 42)
    profile = load_profile(profile_id, seed=seed)
    return _ChaosController(profile)


@pytest_asyncio.fixture
async def chaotic_ill_client(ill_client, chaos_controller, monkeypatch):
    """ILL client with optional chaos fault injection.

    When ``chaos_controller`` is ``None`` (no marker), falls through to
    the regular ``ill_client`` without modification.
    """
    if chaos_controller is None:
        yield ill_client
        return

    from ill.a2a_client import call_service as _original_call_service

    async def _chaos_call_service(service_name, endpoint, **kwargs):
        event = chaos_controller.intercept(service_name, endpoint)
        if event is not None:
            chaos_controller.apply_fault(event)
        chaos_controller.record_retry()
        return await _original_call_service(service_name, endpoint, **kwargs)

    monkeypatch.setattr("ill.a2a_client.call_service", _chaos_call_service)
    yield ill_client


@pytest_asyncio.fixture
async def chaotic_catalog_client(catalog_client, chaos_controller, monkeypatch):
    """Catalog client with optional chaos fault injection."""
    if chaos_controller is None:
        yield catalog_client
        return

    original_get = catalog_client.get

    async def _chaos_get(url, **kwargs):
        event = chaos_controller.intercept("catalog", url)
        if event is not None:
            chaos_controller.apply_fault(event)
        chaos_controller.record_retry()
        return await original_get(url, **kwargs)

    monkeypatch.setattr(catalog_client, "get", _chaos_get)
    yield catalog_client


# ---------------------------------------------------------------------------
# Federated topology fixtures (v1.4)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def spoke_holdings() -> dict[str, list[dict]]:
    """Load spoke library holdings from the network seed manifest.

    Returns a dict mapping library code -> list of book dicts, loaded from
    the batch files assigned to each spoke in the manifest.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    holdings: dict[str, list[dict]] = {}
    for spoke in manifest["spokes"]:
        books: list[dict] = []
        for source in spoke["sources"]:
            data = json.loads((DATA_DIR / source["file"]).read_text(encoding="utf-8"))
            books.extend(data.get(source["key"], []))
        holdings[spoke["code"]] = books
    return holdings


@pytest_asyncio.fixture
async def federated_ill_client(ill_client, spoke_holdings, registry_client, monkeypatch):
    """ILL client with monkeypatched service deps for federated scenarios.

    Patches call_circulation, call_catalog, call_registry, and call_service
    so ILL routes can resolve spoke holdings without live services.
    """
    from shared.http_client import ServiceNotFoundError

    # Build ISBN -> holdings lookup from spoke data.
    isbn_to_holdings: dict[str, dict] = {}
    for library_code, books in spoke_holdings.items():
        for book in books:
            isbn = book.get("isbn")
            if isbn:
                isbn_to_holdings[isbn] = {
                    "library_code": library_code,
                    "book_id": book["id"],
                    "title": book["title"],
                    "total_copies": 2,
                    "available_copies": 1,
                }

    async def fake_call_circulation(endpoint: str, *args, **kwargs):
        if endpoint.startswith("/patrons/"):
            patron_id = endpoint.split("/")[-1]
            return {"id": patron_id, "barcode": "HAN-P-FED", "blocked": False}
        return {}

    # Build book_id -> holdings lookup for instance resolution.
    book_id_to_holdings: dict[str, dict] = {}
    for library_code, books in spoke_holdings.items():
        for book in books:
            book_id_to_holdings[book["id"]] = {
                "library_code": library_code,
                "book_id": book["id"],
                "title": book["title"],
                "total_copies": 2,
                "available_copies": 1,
            }

    async def fake_call_catalog(endpoint: str, *args, **kwargs):
        # Handle /books/{id}/instances — return fake instances for spoke books.
        if "/instances" in endpoint:
            book_id = endpoint.split("/books/")[1].split("/instances")[0]
            if book_id in book_id_to_holdings:
                return [
                    {"id": f"inst-{book_id}-a", "status": "available"},
                    {"id": f"inst-{book_id}-b", "status": "checked_out"},
                ]
            raise ServiceNotFoundError("not found", "catalog", endpoint, 404, None)
        # Check if this is a search that matches a spoke book by ISBN.
        params = kwargs.get("params", {})
        isbn = params.get("isbn")
        if isbn and isbn in isbn_to_holdings:
            h = isbn_to_holdings[isbn]
            return {
                "books": [{"id": h["book_id"], "title": h["title"], "isbn": isbn}],
                "total": 1,
                "limit": 20,
                "offset": 0,
            }
        # Default: book not found locally (triggers ILL flow).
        raise ServiceNotFoundError("not found", "catalog", endpoint, 404, None)

    async def fake_call_registry(endpoint: str, *args, **kwargs):
        if endpoint.startswith("/libraries/"):
            code = endpoint.split("/")[-1]
            return {
                "code": code,
                "status": "active",
                "lending_enabled": True,
            }
        return {}

    async def fake_call_service(
        service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0
    ):
        assert service == "registry"
        if method == "POST" and endpoint == "/a2a/message/send":
            return (
                await registry_client.post(
                    endpoint,
                    headers={"x-library-code": data["message"]["from_library"]},
                    json=data,
                )
            ).json()
        raise AssertionError(f"Unsupported call_service: {service} {method} {endpoint}")

    monkeypatch.setattr("ill.routes._is_known_local_book", lambda book_id: False)
    monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
    monkeypatch.setattr("ill.routes.call_catalog", fake_call_catalog)
    monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)
    monkeypatch.setattr("ill.a2a_client.call_service", fake_call_service)
    yield ill_client


# ---------------------------------------------------------------------------
# Live federation fixtures (v1.7)
# ---------------------------------------------------------------------------

SPOKE_URL_PREFIX = "http://spoke-"


@pytest_asyncio.fixture
async def live_spoke_catalogs(spoke_holdings):
    """Create in-process catalog service instances for each spoke library.

    Returns dict[library_code -> AsyncClient] where each client talks to a
    separate FastAPI app instance backed by its own in-memory SQLite database,
    seeded with that spoke's books.
    """
    from catalog.main import app as _catalog_template_app
    from catalog.routes import router as catalog_router

    spoke_clients: dict[str, AsyncClient] = {}
    engines = []

    for library_code, books in spoke_holdings.items():
        # Create a fresh FastAPI app for this spoke (share the same router)
        from fastapi import FastAPI
        spoke_app = FastAPI(title=f"Catalog - {library_code}")
        spoke_app.include_router(catalog_router)

        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        engines.append(engine)

        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        sfactory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

        # Must capture sfactory in closure
        def _make_override(sf):
            async def override():
                async with sf() as session:
                    yield session
            return override

        spoke_app.dependency_overrides[get_catalog_session] = _make_override(sfactory)

        # Seed books
        async with sfactory() as session:
            for idx, book in enumerate(books, start=1):
                model = BookModel(
                    id=book["id"],
                    title=book["title"],
                    author=book["author"],
                    isbn=book.get("isbn"),
                    genres=book.get("genres", []),
                    summary=book.get("summary"),
                    publication_year=book.get("publication_year"),
                    author_dates=book.get("author_dates"),
                    stratum=book.get("stratum"),
                    publisher=book.get("publisher"),
                    page_count=book.get("page_count"),
                    setting_era=book.get("setting_era"),
                    series=book.get("series"),
                    series_position=book.get("series_position"),
                    shelf_location=book.get("shelf_location"),
                    related_works=book.get("related_works", []),
                    notes=book.get("notes"),
                    in_library=True,
                    illustrations=book.get("illustrations", False),
                    illustrator=book.get("illustrator"),
                    age_range=book.get("age_range"),
                    reading_level=book.get("reading_level"),
                )
                session.add(model)
                session.add(
                    BookInstanceModel(
                        id=f"inst-{library_code}-{book['id']}-a",
                        book_id=book["id"],
                        barcode=f"SPOKE-{idx:06d}",
                        call_number=f"S-{idx:04d}",
                        status=InstanceStatus.AVAILABLE,
                        location="General Stacks",
                        condition=ItemCondition.GOOD,
                    )
                )
            await session.commit()

        client = AsyncClient(
            transport=ASGITransport(app=spoke_app),
            base_url=f"{SPOKE_URL_PREFIX}{library_code}:8000",
        )
        spoke_clients[library_code] = client

    yield spoke_clients

    for client in spoke_clients.values():
        await client.aclose()
    for engine in engines:
        await engine.dispose()


@pytest_asyncio.fixture
async def live_federation_client(
    ill_client, live_spoke_catalogs, spoke_holdings, registry_client, monkeypatch
):
    """ILL client wired to live in-process spoke catalogs via call_url patching.

    Intercepts call_remote_catalog() to route to the correct in-process ASGI
    test client. Also patches _is_known_local_book, call_circulation, and
    call_registry to support federated ILL flows.
    """
    from shared.http_client import ServiceNotFoundError

    # Build URL -> client mapping
    url_to_client: dict[str, AsyncClient] = {}
    url_by_code: dict[str, str] = {}
    for code, client in live_spoke_catalogs.items():
        url = f"{SPOKE_URL_PREFIX}{code}:8000"
        url_to_client[url] = client
        url_by_code[code] = url

    async def fake_call_url(base_url, endpoint, method="GET", data=None, params=None, timeout=10.0):
        """Route call_url() to the correct in-process spoke catalog."""
        client = url_to_client.get(base_url.rstrip("/"))
        if client is None:
            from shared.http_client import ServiceUnavailableError
            raise ServiceUnavailableError(
                f"No live spoke catalog at {base_url}",
                service=base_url,
                endpoint=endpoint,
            )
        if method == "GET":
            resp = await client.get(endpoint, params=params)
        elif method == "POST":
            resp = await client.post(endpoint, json=data, params=params)
        else:
            resp = await client.request(method, endpoint, json=data, params=params)

        if resp.status_code == 404:
            raise ServiceNotFoundError("not found", base_url, endpoint, 404, resp.text)
        resp.raise_for_status()
        return resp.json()

    async def fake_call_circulation(endpoint, *args, **kwargs):
        if endpoint.startswith("/patrons/"):
            patron_id = endpoint.split("/")[-1]
            return {"id": patron_id, "barcode": "HAN-P-FED", "blocked": False}
        return {}

    async def fake_call_registry(endpoint, *args, **kwargs):
        if endpoint.startswith("/libraries/"):
            code = endpoint.split("/")[-1]
            catalog_url = url_by_code.get(code)
            return {
                "code": code,
                "status": "active",
                "lending_enabled": True,
                "catalog_url": catalog_url,
            }
        return {}

    async def fake_call_service(
        service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0
    ):
        assert service == "registry"
        if method == "POST" and endpoint == "/a2a/message/send":
            return (
                await registry_client.post(
                    endpoint,
                    headers={"x-library-code": data["message"]["from_library"]},
                    json=data,
                )
            ).json()
        raise AssertionError(f"Unsupported call_service: {service} {method} {endpoint}")

    monkeypatch.setattr("ill.routes._is_known_local_book", lambda book_id: False)
    monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
    monkeypatch.setattr("ill.routes.call_catalog", lambda *a, **kw: (_ for _ in ()).throw(
        ServiceNotFoundError("not local", "catalog", "", 404, None)
    ))
    monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)
    monkeypatch.setattr("ill.routes.call_remote_catalog", fake_call_url)
    monkeypatch.setattr("ill.a2a_client.call_service", fake_call_service)
    yield ill_client
