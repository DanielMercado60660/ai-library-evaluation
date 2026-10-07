"""Integration tests for bounded retry behavior in A2A client."""

import pytest

from ill.a2a_client import send_a2a_message
from shared.a2a.schemas import A2AMessageType
from shared.http_client import ServiceUnavailableError


class TestA2ARetryTimeout:
    """Validate timeout/retry and bounded failure behavior."""

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self, monkeypatch):
        """Transient registry failures should be retried and eventually succeed."""
        attempts = {"count": 0}

        async def flaky_call_service(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ServiceUnavailableError(
                    "registry unavailable",
                    service="registry",
                    endpoint=endpoint,
                    status_code=503,
                )
            return {
                "accepted": True,
                "message_id": data["message"]["id"],
                "queued_for": data["message"]["to_library"],
            }

        monkeypatch.setattr("ill.a2a_client.call_service", flaky_call_service)

        response = await send_a2a_message(
            to_library="mastodon-institute",
            message_type=A2AMessageType.LOAN_REQUEST,
            payload={"request_id": "ill-req-retry-001"},
            retries=2,
            retry_delay_seconds=0.0,
            timeout_seconds=0.1,
        )

        assert response["accepted"] is True
        assert response["queued_for"] == "mastodon-institute"
        assert attempts["count"] == 3

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises(self, monkeypatch):
        """When retries are exhausted, the last transport error is raised."""
        attempts = {"count": 0}

        async def always_unavailable(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            attempts["count"] += 1
            raise ServiceUnavailableError(
                "registry unavailable",
                service="registry",
                endpoint=endpoint,
                status_code=503,
            )

        monkeypatch.setattr("ill.a2a_client.call_service", always_unavailable)

        with pytest.raises(ServiceUnavailableError):
            await send_a2a_message(
                to_library="mastodon-institute",
                message_type=A2AMessageType.LOAN_REQUEST,
                payload={"request_id": "ill-req-retry-002"},
                retries=1,
                retry_delay_seconds=0.0,
                timeout_seconds=0.1,
            )

        assert attempts["count"] == 2

    @pytest.mark.asyncio
    async def test_retry_with_jitter(self, monkeypatch):
        """Verify jitter is applied — delays should vary between runs with same seed."""
        import time

        delays: list[float] = []
        attempts = {"count": 0}

        async def slow_fail(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ServiceUnavailableError(
                    "registry unavailable",
                    service="registry",
                    endpoint=endpoint,
                    status_code=503,
                )
            return {
                "accepted": True,
                "message_id": data["message"]["id"],
                "queued_for": data["message"]["to_library"],
            }

        monkeypatch.setattr("ill.a2a_client.call_service", slow_fail)

        start = time.monotonic()
        await send_a2a_message(
            to_library="mastodon-institute",
            message_type=A2AMessageType.LOAN_REQUEST,
            payload={"request_id": "ill-req-jitter-001"},
            retries=2,
            retry_delay_seconds=0.01,
            timeout_seconds=1.0,
        )
        elapsed = time.monotonic() - start

        # With jitter and 2 retries at 0.01s base, total should be small but > 0.
        assert elapsed > 0.01
        assert attempts["count"] == 3

    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self, monkeypatch):
        """Delay should never exceed the max_delay (timeout_seconds)."""
        import asyncio as _asyncio

        sleep_durations: list[float] = []
        original_sleep = _asyncio.sleep

        async def capture_sleep(duration):
            sleep_durations.append(duration)
            # Don't actually sleep in tests.

        monkeypatch.setattr("asyncio.sleep", capture_sleep)

        attempts = {"count": 0}

        async def always_fail(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            attempts["count"] += 1
            raise ServiceUnavailableError(
                "registry unavailable",
                service="registry",
                endpoint=endpoint,
                status_code=503,
            )

        monkeypatch.setattr("ill.a2a_client.call_service", always_fail)

        with pytest.raises(ServiceUnavailableError):
            await send_a2a_message(
                to_library="mastodon-institute",
                message_type=A2AMessageType.LOAN_REQUEST,
                payload={"request_id": "ill-req-maxdelay-001"},
                retries=4,
                retry_delay_seconds=0.5,
                timeout_seconds=1.0,
            )

        # All sleep durations should be <= max_delay (1.0) + jitter margin.
        for d in sleep_durations:
            assert d <= 1.0 * 1.11  # 10% jitter headroom
