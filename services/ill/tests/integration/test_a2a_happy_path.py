"""Integration test for A2A-backed outbound ILL happy path."""

from datetime import datetime, UTC, timedelta

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

    # Seed one partner library used in the test.
    async with session_factory() as session:
        partner = PartnerLibraryModel(
            code="mastodon-institute",
            name="Mastodon Institute Library",
            display_name="Mastodon Institute",
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


class TestA2AHappyPath:
    """Validate full request -> shipped -> received -> returned -> closed lifecycle."""

    @pytest.mark.asyncio
    async def test_a2a_outbound_borrow_happy_path(self, client, db_session, registry_client, monkeypatch):
        """Exercise A2A send/receive flow with deterministic partner responses."""
        # Deterministic stubs for non-A2A dependencies.
        async def fake_call_circulation(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/patrons/"):
                patron_id = endpoint.split("/")[-1]
                return {
                    "id": patron_id,
                    "barcode": "HAN-P-777",
                    "blocked": False,
                }
            return {}

        async def fake_call_catalog(endpoint: str, *args, **kwargs):
            # Simulate "not in local catalog" so ILL request can proceed.
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

        # Step 1: Library A creates outbound request; should enqueue LOAN_REQUEST to partner inbox.
        create = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-a2a-001",
                "patron_id": "patron-a2a-001",
                "source_library": "mastodon-institute",
            },
        )
        assert create.status_code == 201
        created = create.json()
        request_id = created["id"]
        assert created["status"] == "requested"

        partner_inbox = await registry_client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert partner_inbox.status_code == 200
        partner_messages = partner_inbox.json()["messages"]
        assert len(partner_messages) == 1
        assert partner_messages[0]["type"] == "loan_request"
        assert partner_messages[0]["correlation_id"] == request_id

        # Partner acks receipt of request message.
        ack_partner = await registry_client.post(
            f"/a2a/messages/{partner_messages[0]['id']}/ack",
            headers={"x-library-code": "mastodon-institute"},
            json={"library_code": "mastodon-institute"},
        )
        assert ack_partner.status_code == 200

        # Step 2: Library B sends loan response (approved) back through relay.
        response_msg = {
            "message": {
                "type": "loan_response",
                "from_library": "mastodon-institute",
                "to_library": "hanno-memorial",
                "correlation_id": request_id,
                "payload": {"approved": True},
            }
        }
        send_response = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json=response_msg,
        )
        assert send_response.status_code == 200

        # Deliver relay message to ILL callback endpoint.
        hanno_inbox = await registry_client.get(
            "/a2a/messages/hanno-memorial",
            headers={"x-library-code": "hanno-memorial"},
        )
        assert hanno_inbox.status_code == 200
        inbound = hanno_inbox.json()["messages"]
        assert len(inbound) == 1

        inbound_response = await client.post("/a2a/inbound", json={"message": inbound[0]})
        assert inbound_response.status_code == 200
        assert inbound_response.json()["updated_status"] == "shipped"

        ack_hanno = await registry_client.post(
            f"/a2a/messages/{inbound[0]['id']}/ack",
            headers={"x-library-code": "hanno-memorial"},
            json={"library_code": "hanno-memorial"},
        )
        assert ack_hanno.status_code == 200

        # Step 3: Library A receives the item.
        received = await client.post(f"/requests/{request_id}/receive")
        assert received.status_code == 200
        assert received.json()["status"] == "received"
        due_date = datetime.fromisoformat(received.json()["due_date"].replace("Z", "+00:00"))
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)
        assert (due_date - datetime.now(UTC)) >= timedelta(days=27)

        # Step 4: Library A returns the item, which should emit ITEM_RETURNED to partner.
        returned = await client.post(f"/requests/{request_id}/return")
        assert returned.status_code == 200
        assert returned.json()["status"] == "returned"

        partner_return_inbox = await registry_client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert partner_return_inbox.status_code == 200
        return_messages = partner_return_inbox.json()["messages"]
        assert len(return_messages) == 1
        assert return_messages[0]["type"] == "item_returned"
        assert return_messages[0]["correlation_id"] == request_id

        # Step 5: Partner sends return-ack, local request closes.
        send_ack = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "item_return_ack",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"accepted": True},
                }
            },
        )
        assert send_ack.status_code == 200

        hanno_final_inbox = await registry_client.get(
            "/a2a/messages/hanno-memorial",
            headers={"x-library-code": "hanno-memorial"},
        )
        assert hanno_final_inbox.status_code == 200
        final_msgs = hanno_final_inbox.json()["messages"]
        assert len(final_msgs) == 1

        close_response = await client.post("/a2a/inbound", json={"message": final_msgs[0]})
        assert close_response.status_code == 200
        assert close_response.json()["updated_status"] == "closed"

        final = await client.get(f"/requests/{request_id}")
        assert final.status_code == 200
        assert final.json()["status"] == "closed"
        assert final.json()["closed_at"] is not None
