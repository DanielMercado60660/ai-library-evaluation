"""Integration tests for A2A denial and late-message handling."""

from datetime import datetime, UTC

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from registry.main import app as registry_app
from registry.db import get_session as registry_get_session
from registry.models import PartnerLibraryModel, LibraryMetricsModel
from registry.a2a_relay import relay_store


@pytest_asyncio.fixture
async def registry_client():
    """In-process registry app client with in-memory DB."""
    relay_store.clear()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_registry_session():
        async with session_factory() as session:
            yield session

    registry_app.dependency_overrides[registry_get_session] = override_registry_session

    async with session_factory() as session:
        for code, name in [
            ("mastodon-institute", "Mastodon Institute Library"),
            ("mammoth-valley", "Mammoth Valley Library"),
        ]:
            partner = PartnerLibraryModel(
                code=code,
                name=name,
                display_name=name,
                status="active",
                member_since=datetime.now(UTC),
            )
            session.add(partner)
            session.add(
                LibraryMetricsModel(
                    library_code=partner.code,
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


class TestA2ADenialAndLateMessages:
    """Validate denial and idempotent late-message behavior."""

    @pytest.mark.asyncio
    async def test_denial_path_sets_request_to_denied(self, client, registry_client, monkeypatch):
        """A denied loan response should transition request status to denied."""

        async def fake_call_circulation(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/patrons/"):
                patron_id = endpoint.split("/")[-1]
                return {
                    "id": patron_id,
                    "barcode": "HAN-P-411",
                    "blocked": False,
                }
            return {}

        async def fake_call_catalog(endpoint: str, *args, **kwargs):
            from shared.http_client import ServiceNotFoundError

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

        async def fake_call_service(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            assert service == "registry"
            if method == "POST" and endpoint == "/a2a/message/send":
                return (
                    await registry_client.post(
                        endpoint,
                        headers={"x-library-code": data["message"]["from_library"]},
                        json=data,
                    )
                ).json()
            raise AssertionError(f"Unsupported call_service in test: {service} {method} {endpoint}")

        monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
        monkeypatch.setattr("ill.routes.call_catalog", fake_call_catalog)
        monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)
        monkeypatch.setattr("ill.a2a_client.call_service", fake_call_service)

        create = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-a2a-deny-001",
                "patron_id": "patron-a2a-deny-001",
                "source_library": "mastodon-institute",
            },
        )
        assert create.status_code == 201
        request_id = create.json()["id"]

        send_denial = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "loan_response",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"approved": False, "reason": "restricted_item"},
                }
            },
        )
        assert send_denial.status_code == 200

        inbox = await registry_client.get(
            "/a2a/messages/hanno-memorial",
            headers={"x-library-code": "hanno-memorial"},
        )
        assert inbox.status_code == 200
        message = next(
            msg
            for msg in inbox.json()["messages"]
            if msg.get("type") == "loan_response" and msg.get("correlation_id") == request_id
        )

        apply_denial = await client.post("/a2a/inbound", json={"message": message})
        assert apply_denial.status_code == 200
        assert apply_denial.json()["updated_status"] == "denied"

        current = await client.get(f"/requests/{request_id}")
        assert current.status_code == 200
        body = current.json()
        assert body["status"] == "denied"
        assert body["denial_reason"] == "restricted_item"

    @pytest.mark.asyncio
    async def test_late_denial_after_ship_is_noop(self, client, registry_client, monkeypatch):
        """A late denial after shipping should not overwrite shipped status."""

        async def fake_call_circulation(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/patrons/"):
                return {"id": "patron-a2a-late", "barcode": "HAN-P-412", "blocked": False}
            return {}

        async def fake_call_catalog(endpoint: str, *args, **kwargs):
            from shared.http_client import ServiceNotFoundError

            raise ServiceNotFoundError("not found", "catalog", endpoint, 404, None)

        async def fake_call_registry(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/libraries/"):
                code = endpoint.split("/")[-1]
                return {"code": code, "status": "active", "lending_enabled": True}
            return {}

        async def fake_call_service(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            assert service == "registry"
            if method == "POST" and endpoint == "/a2a/message/send":
                return (
                    await registry_client.post(
                        endpoint,
                        headers={"x-library-code": data["message"]["from_library"]},
                        json=data,
                    )
                ).json()
            raise AssertionError(f"Unsupported call_service in test: {service} {method} {endpoint}")

        monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
        monkeypatch.setattr("ill.routes.call_catalog", fake_call_catalog)
        monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)
        monkeypatch.setattr("ill.a2a_client.call_service", fake_call_service)

        create = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-a2a-late-001",
                "patron_id": "patron-a2a-late",
                "source_library": "mastodon-institute",
            },
        )
        assert create.status_code == 201
        request_id = create.json()["id"]

        send_approved = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "loan_response",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"approved": True},
                }
            },
        )
        assert send_approved.status_code == 200

        ship_msg = (
            await registry_client.get(
                "/a2a/messages/hanno-memorial",
                headers={"x-library-code": "hanno-memorial"},
            )
        ).json()["messages"]
        ship_msg = next(
            msg
            for msg in ship_msg
            if msg.get("type") == "loan_response" and msg.get("correlation_id") == request_id
        )
        applied = await client.post("/a2a/inbound", json={"message": ship_msg})
        assert applied.status_code == 200
        assert applied.json()["updated_status"] == "shipped"

        send_late_denial = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "loan_response",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"approved": False, "reason": "late_denial"},
                }
            },
        )
        assert send_late_denial.status_code == 200

        late_msg = (
            await registry_client.get(
                "/a2a/messages/hanno-memorial",
                headers={"x-library-code": "hanno-memorial"},
            )
        ).json()["messages"]
        late_msg = next(
            msg
            for msg in late_msg
            if msg.get("type") == "loan_response" and msg.get("correlation_id") == request_id
        )
        late_applied = await client.post("/a2a/inbound", json={"message": late_msg})
        assert late_applied.status_code == 200
        assert late_applied.json()["updated_status"] == "shipped"

        final = await client.get(f"/requests/{request_id}")
        assert final.status_code == 200
        assert final.json()["status"] == "shipped"
