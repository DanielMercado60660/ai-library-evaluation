"""Reliability policy tests.

Validates timeout defaults, retry behavior, circuit breaker transitions,
and the resilience checker output for the current codebase.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestTimeoutDefaults:
    """Verify default timeout configuration."""

    def test_default_timeout_is_10s(self):
        """call_service uses timeout=10.0 by default."""
        import inspect
        from shared.http_client import call_service

        sig = inspect.signature(call_service)
        assert sig.parameters["timeout"].default == 10.0


class TestRetryDefaults:
    """Verify @with_retry decorator defaults."""

    def test_retry_default_max_3_attempts(self):
        """@with_retry uses max_attempts=3 by default."""
        from agents.utils.resilience import with_retry
        import inspect

        sig = inspect.signature(with_retry)
        assert sig.parameters["max_attempts"].default == 3

    @pytest.mark.asyncio
    async def test_retry_does_not_retry_non_retryable_errors(self):
        """Exceptions outside DEFAULT_RETRYABLE_EXCEPTIONS are not retried."""
        from agents.utils.resilience import with_retry

        call_count = 0

        @with_retry(max_attempts=3)
        async def failing_call():
            nonlocal call_count
            call_count += 1
            raise ValueError("non-retryable error")

        with pytest.raises(ValueError):
            await failing_call()

        # Should NOT have retried — ValueError is not in DEFAULT_RETRYABLE_EXCEPTIONS
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_retries_on_timeout(self):
        """TimeoutError triggers retry up to max_attempts."""
        from agents.utils.resilience import with_retry

        call_count = 0

        @with_retry(max_attempts=3, initial_delay=0.01)
        async def timeout_call():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("timed out")

        with pytest.raises(TimeoutError):
            await timeout_call()

        assert call_count == 3


class TestCircuitBreaker:
    """Verify circuit breaker state transitions."""

    def test_circuit_breaker_opens_after_threshold(self):
        """CB opens after failure_threshold consecutive failures."""
        from agents.utils.resilience import CircuitBreaker, CircuitBreakerOpenError

        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=0.1)
        for _ in range(3):
            cb._on_failure()

        with pytest.raises(CircuitBreakerOpenError):
            cb._check_state()

    def test_circuit_breaker_recovers_after_timeout(self):
        """CB transitions to half-open after recovery timeout."""
        import time
        from agents.utils.resilience import CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.05)
        for _ in range(2):
            cb._on_failure()

        time.sleep(0.1)  # Wait past recovery timeout
        # Should NOT raise — circuit is half-open now
        cb._check_state()


class TestResilienceChecker:
    """Verify the resilience policy checker passes on current codebase."""

    def test_resilience_checker_passes_current_codebase(self):
        """scripts/check_resilience_policy.py reports 0 violations."""
        from check_resilience_policy import ResiliencePolicyChecker

        checker = ResiliencePolicyChecker()
        violations = checker.run_all()
        assert violations == [], f"Resilience violations: {violations}"


class TestHealthContract:
    """Health endpoints respond for all services."""

    @pytest.mark.asyncio
    async def test_health_endpoints_respond(self):
        """All 4 backend services /health respond 200."""
        from httpx import ASGITransport, AsyncClient
        from catalog.main import app as catalog_app
        from circulation.main import app as circulation_app
        from ill.main import app as ill_app
        from registry.main import app as registry_app

        for name, app in [
            ("catalog", catalog_app),
            ("circulation", circulation_app),
            ("ill", ill_app),
            ("registry", registry_app),
        ]:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/health")
                assert resp.status_code == 200, f"{name} health failed"
