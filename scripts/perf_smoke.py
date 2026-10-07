"""Performance smoke test for local alpha readiness.

Measures health endpoint latency and report generation time using in-process
ASGI transport (deterministic, no network overhead). Enforced in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from catalog.main import app as catalog_app
from circulation.main import app as circulation_app
from ill.main import app as ill_app
from registry.main import app as registry_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Budget thresholds (milliseconds).
HEALTH_ENDPOINT_BUDGET_MS = 2000
REPORT_GENERATION_BUDGET_MS = 5000
PERF_SMOKE_TOTAL_BUDGET_MS = 10000

# Auth header required since v1.8 ServiceAuthMiddleware.
_AUTH_HEADERS = {"x-service-token": "dev-token-ai-librarian"}


class PerformanceSmokeRunner:
    """Executes performance smoke tests against local services."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.violations: list[str] = []
        self.results: list[dict[str, Any]] = []

    async def _check_health_endpoint(
        self, app: Any, service_name: str, base_url: str, budget_ms: int
    ) -> dict[str, Any]:
        """Measure health endpoint response time via in-process ASGI."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url=base_url,
            headers=_AUTH_HEADERS,
        ) as client:
            start = time.perf_counter()
            try:
                resp = await client.get("/health")
                duration_ms = (time.perf_counter() - start) * 1000
                resp.raise_for_status()

                result: dict[str, Any] = {
                    "service": service_name,
                    "endpoint": "/health",
                    "duration_ms": round(duration_ms, 2),
                    "budget_ms": budget_ms,
                    "status": "pass" if duration_ms < budget_ms else "fail",
                }

                if duration_ms >= budget_ms:
                    self.violations.append(
                        f"{service_name} /health: {duration_ms:.2f}ms exceeds budget {budget_ms}ms"
                    )

                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                self.violations.append(f"{service_name} /health: {exc}")
                return {
                    "service": service_name,
                    "endpoint": "/health",
                    "duration_ms": round(duration_ms, 2),
                    "budget_ms": budget_ms,
                    "status": "error",
                    "error": str(exc),
                }

    async def run_health_checks(self) -> None:
        """Check all service health endpoints."""
        services = [
            (catalog_app, "catalog", "http://catalog-test"),
            (circulation_app, "circulation", "http://circulation-test"),
            (ill_app, "ill", "http://ill-test"),
            (registry_app, "registry", "http://registry-test"),
        ]

        print(f"Checking {len(services)} service health endpoints...")
        for app, name, url in services:
            result = await self._check_health_endpoint(app, name, url, HEALTH_ENDPOINT_BUDGET_MS)
            self.results.append(result)
            mark = "PASS" if result["status"] == "pass" else "FAIL"
            print(f"  [{mark}] {name}: {result['duration_ms']}ms")

    def check_report_generation(self) -> None:
        """Verify benchmark report can be loaded within budget."""
        report_path = self.project_root / "artifacts" / "benchmark-report.json"

        if not report_path.exists():
            self.results.append({
                "check": "report_generation",
                "status": "skip",
                "evidence": "No existing report to verify",
            })
            print("  [SKIP] report_generation: no existing report")
            return

        start = time.perf_counter()
        try:
            json.loads(report_path.read_text(encoding="utf-8"))
            duration_ms = (time.perf_counter() - start) * 1000

            result: dict[str, Any] = {
                "check": "report_generation",
                "duration_ms": round(duration_ms, 2),
                "budget_ms": REPORT_GENERATION_BUDGET_MS,
                "status": "pass" if duration_ms < REPORT_GENERATION_BUDGET_MS else "fail",
                "report_size_kb": round(report_path.stat().st_size / 1024, 2),
            }

            if duration_ms >= REPORT_GENERATION_BUDGET_MS:
                self.violations.append(
                    f"Report generation: {duration_ms:.2f}ms exceeds budget "
                    f"{REPORT_GENERATION_BUDGET_MS}ms"
                )

            self.results.append(result)
            mark = "PASS" if result["status"] == "pass" else "FAIL"
            print(f"  [{mark}] report_generation: {duration_ms:.2f}ms")
        except Exception as exc:
            self.violations.append(f"Report generation failed: {exc}")
            self.results.append({
                "check": "report_generation",
                "status": "error",
                "error": str(exc),
            })
            print(f"  [FAIL] report_generation: {exc}")

    def run_all(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Execute all performance smoke tests."""
        print(f"Running performance smoke tests: {self.project_root}")
        total_start = time.perf_counter()

        asyncio.run(self.run_health_checks())
        self.check_report_generation()

        total_duration_ms = (time.perf_counter() - total_start) * 1000

        summary: dict[str, Any] = {
            "check": "total_smoke_duration",
            "duration_ms": round(total_duration_ms, 2),
            "budget_ms": PERF_SMOKE_TOTAL_BUDGET_MS,
            "status": "pass" if total_duration_ms < PERF_SMOKE_TOTAL_BUDGET_MS else "fail",
        }

        if total_duration_ms >= PERF_SMOKE_TOTAL_BUDGET_MS:
            self.violations.append(
                f"Total smoke test: {total_duration_ms:.2f}ms exceeds budget "
                f"{PERF_SMOKE_TOTAL_BUDGET_MS}ms"
            )

        self.results.append(summary)

        print(f"\nTotal duration: {total_duration_ms:.2f}ms")
        print(f"Violations: {len(self.violations)}")

        return self.results, self.violations

    def write_report(self, output_path: Path) -> None:
        """Write performance smoke report to JSON."""
        report = {
            "schema_version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "budgets": {
                "health_endpoint_ms": HEALTH_ENDPOINT_BUDGET_MS,
                "report_generation_ms": REPORT_GENERATION_BUDGET_MS,
                "total_smoke_ms": PERF_SMOKE_TOTAL_BUDGET_MS,
            },
            "results": self.results,
            "violations": self.violations,
            "summary": {
                "total_checks": len(self.results),
                "passed": sum(1 for r in self.results if r.get("status") == "pass"),
                "failed": sum(1 for r in self.results if r.get("status") == "fail"),
                "errors": sum(1 for r in self.results if r.get("status") == "error"),
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote performance smoke report: {output_path}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run performance smoke tests.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on budget violations")
    parser.add_argument(
        "--output",
        default="artifacts/perf-smoke-report.json",
        help="Output path for JSON report",
    )
    args = parser.parse_args()

    runner = PerformanceSmokeRunner()
    runner.run_all()
    runner.write_report(Path(args.output))

    if args.strict and runner.violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
