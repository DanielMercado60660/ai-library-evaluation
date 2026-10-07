"""EvalDatabaseSeeder — resets and seeds all backend services for eval runs.

Calls ``POST /admin/reset-and-seed`` on each service (catalog, circulation,
ILL, registry). These endpoints are gated behind ``EVAL_MODE=true`` on each
service. The seeder passes the ``x-service-token`` header for auth.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_SERVICE_TOKEN_HEADER = "x-service-token"
_DEFAULT_TOKEN = "dev-token-ai-librarian"


class EvalDatabaseSeeder:
    """Resets and seeds all backend services for a deterministic eval run."""

    def __init__(
        self,
        service_urls: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        defaults = {
            "catalog": os.getenv("CATALOG_URL", "http://localhost:8001"),
            "circulation": os.getenv("CIRCULATION_URL", "http://localhost:8002"),
            "ill": os.getenv("RECOMMENDATION_URL", "http://localhost:8003"),
            "registry": os.getenv("AUTH_URL", "http://localhost:8004"),
        }
        self._urls = {**defaults, **(service_urls or {})}
        self._timeout = timeout
        self._token = os.getenv("SERVICE_AUTH_TOKEN", _DEFAULT_TOKEN)

    async def reset_and_seed_all(self) -> dict[str, dict]:
        """Call ``POST /admin/reset-and-seed`` on every service.

        Returns:
            Mapping of service name to the JSON response body.

        Raises:
            RuntimeError: If any service returns a non-2xx status.
        """
        results: dict[str, dict] = {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for service, base_url in self._urls.items():
                url = f"{base_url.rstrip('/')}/admin/reset-and-seed"
                logger.info("Seeding %s at %s", service, url)
                resp = await client.post(
                    url,
                    headers={_SERVICE_TOKEN_HEADER: self._token},
                )
                if resp.status_code >= 400:
                    detail = resp.text[:300]
                    raise RuntimeError(
                        f"Seed failed for {service} ({resp.status_code}): {detail}"
                    )
                results[service] = resp.json()
                logger.info(
                    "Seeded %s: %s", service, results[service]
                )
        return results

    async def verify_seed(self) -> bool:
        """Smoke-check that a known book and patron are reachable.

        Returns:
            True if both lookups succeed.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Check a known book
            catalog_url = self._urls["catalog"].rstrip("/")
            book_resp = await client.get(
                f"{catalog_url}/books/book-001",
                headers={_SERVICE_TOKEN_HEADER: self._token},
            )
            if book_resp.status_code != 200:
                logger.warning("Seed verification: book-001 not found")
                return False

            # Check a known patron
            circ_url = self._urls["circulation"].rstrip("/")
            patron_resp = await client.get(
                f"{circ_url}/patrons/patron-001",
                headers={_SERVICE_TOKEN_HEADER: self._token},
            )
            if patron_resp.status_code != 200:
                logger.warning("Seed verification: patron-001 not found")
                return False

        logger.info("Seed verification passed")
        return True
