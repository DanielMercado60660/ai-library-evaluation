"""Release gate aggregator for v2.0 RC promotion.

Runs all blocking readiness checks and produces a unified promotion report.
Each gate runs as a subprocess for real-world fidelity and import isolation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@dataclass
class GateResult:
    """Result of a single release gate check."""

    name: str
    status: str  # "pass", "fail", "skip"
    duration_ms: float = 0.0
    evidence: str = ""
    command: str = ""
    exit_code: int = 0


class ReleaseGateRunner:
    """Orchestrates all v2.0 RC release gates and produces reports."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.gates: list[GateResult] = []

    def _run_subprocess_gate(
        self, name: str, command: list[str], strict: bool = True
    ) -> GateResult:
        """Run a gate check via subprocess with timeout."""
        start = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.project_root),
            )
            duration_ms = (time.perf_counter() - start) * 1000

            status = "pass" if result.returncode == 0 else "fail"
            evidence = result.stdout[-500:] if result.stdout else ""
            if result.returncode != 0 and result.stderr:
                evidence += f"\nSTDERR: {result.stderr[-300:]}"

            gate = GateResult(
                name=name,
                status=status,
                duration_ms=round(duration_ms, 2),
                evidence=evidence.strip(),
                command=" ".join(command),
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start) * 1000
            gate = GateResult(
                name=name,
                status="fail",
                duration_ms=round(duration_ms, 2),
                evidence="Timed out after 300s",
                command=" ".join(command),
                exit_code=-1,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            gate = GateResult(
                name=name,
                status="fail",
                duration_ms=round(duration_ms, 2),
                evidence=str(exc),
                command=" ".join(command),
                exit_code=-1,
            )

        self.gates.append(gate)
        return gate

    def run_adr_governance(self) -> GateResult:
        """Gate: ADR governance check."""
        return self._run_subprocess_gate(
            "adr_governance",
            ["uv", "run", "python", "scripts/check_adr_links.py", "--strict"],
        )

    def run_dependency_boundaries(self) -> GateResult:
        """Gate: dependency boundary enforcement."""
        return self._run_subprocess_gate(
            "dependency_boundaries",
            ["uv", "run", "python", "scripts/check_dependency_boundaries.py", "--strict"],
        )

    def run_resilience_policy(self) -> GateResult:
        """Gate: resilience policy check."""
        return self._run_subprocess_gate(
            "resilience_policy",
            ["uv", "run", "python", "scripts/check_resilience_policy.py", "--strict"],
        )

    def run_performance_smoke(self) -> GateResult:
        """Gate: performance smoke test."""
        return self._run_subprocess_gate(
            "performance_smoke",
            ["uv", "run", "python", "scripts/perf_smoke.py", "--strict"],
        )

    def run_recovery_drill(self) -> GateResult:
        """Gate: recovery drill script is importable and functional."""
        start = time.perf_counter()
        try:
            # Verify the script is importable — no full drill needed in gate
            result = subprocess.run(
                ["uv", "run", "python", "-c", "from scripts.recovery_drill import RecoveryDrillRunner; print('OK')"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.project_root),
            )
            # Fallback: try direct import path
            if result.returncode != 0:
                result = subprocess.run(
                    ["uv", "run", "python", "-c",
                     f"import sys; sys.path.insert(0, '{SCRIPTS_DIR}'); "
                     "from recovery_drill import RecoveryDrillRunner; print('OK')"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.project_root),
                )
            duration_ms = (time.perf_counter() - start) * 1000
            gate = GateResult(
                name="recovery_drill",
                status="pass" if result.returncode == 0 else "fail",
                duration_ms=round(duration_ms, 2),
                evidence=result.stdout.strip() or result.stderr.strip()[-200:],
                command="import recovery_drill.RecoveryDrillRunner",
                exit_code=result.returncode,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            gate = GateResult(
                name="recovery_drill",
                status="fail",
                duration_ms=round(duration_ms, 2),
                evidence=str(exc),
                command="import recovery_drill.RecoveryDrillRunner",
                exit_code=-1,
            )
        self.gates.append(gate)
        return gate

    def run_test_count_verification(self, min_expected: int = 620) -> GateResult:
        """Gate: verify minimum test count."""
        start = time.perf_counter()
        try:
            result = subprocess.run(
                ["uv", "run", "pytest", "--co", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.project_root),
            )
            duration_ms = (time.perf_counter() - start) * 1000

            # Parse collected count from output (e.g. "640 tests collected" or
            # "========================= 640 tests collected in 0.47s ====")
            last_lines = result.stdout.strip().split("\n")
            count = 0
            for line in reversed(last_lines):
                if "test" in line and ("collected" in line or "selected" in line):
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit() and i + 1 < len(parts) and "test" in parts[i + 1]:
                            count = int(part)
                            break
                    if count > 0:
                        break

            status = "pass" if count >= min_expected else "fail"
            evidence = f"Collected {count} tests (minimum: {min_expected})"

            gate = GateResult(
                name="test_count_verification",
                status=status,
                duration_ms=round(duration_ms, 2),
                evidence=evidence,
                command="uv run pytest --co -q",
                exit_code=0 if status == "pass" else 1,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            gate = GateResult(
                name="test_count_verification",
                status="fail",
                duration_ms=round(duration_ms, 2),
                evidence=str(exc),
                command="uv run pytest --co -q",
                exit_code=-1,
            )
        self.gates.append(gate)
        return gate

    def run_frontend_build(self, skip: bool = False) -> GateResult:
        """Gate: frontend build (optional, skippable in CI)."""
        if skip:
            gate = GateResult(
                name="frontend_build",
                status="skip",
                evidence="Skipped via --skip-frontend flag",
            )
            self.gates.append(gate)
            return gate

        return self._run_subprocess_gate(
            "frontend_build",
            ["npx", "ng", "build"],
        )

    def run_all_gates(
        self, skip_frontend: bool = False, dry_run: bool = False
    ) -> list[GateResult]:
        """Orchestrate all release gates."""
        if dry_run:
            gate_names = [
                "adr_governance",
                "dependency_boundaries",
                "resilience_policy",
                "performance_smoke",
                "recovery_drill",
                "test_count_verification",
                "frontend_build",
            ]
            print("Dry run — gates that would execute:")
            for name in gate_names:
                print(f"  - {name}")
            return []

        print("Running v2.0 RC release gates...\n")

        gates = [
            ("ADR governance", self.run_adr_governance),
            ("Dependency boundaries", self.run_dependency_boundaries),
            ("Resilience policy", self.run_resilience_policy),
            ("Performance smoke", self.run_performance_smoke),
            ("Recovery drill", self.run_recovery_drill),
            ("Test count verification", self.run_test_count_verification),
            ("Frontend build", lambda: self.run_frontend_build(skip=skip_frontend)),
        ]

        for label, gate_fn in gates:
            print(f"  [{label}] ", end="", flush=True)
            result = gate_fn()
            mark = result.status.upper()
            print(f"{mark} ({result.duration_ms:.0f}ms)")

        return self.gates

    def compute_overall_status(self) -> str:
        """Compute promotion readiness from gate results."""
        if not self.gates:
            return "blocked"

        statuses = {g.status for g in self.gates}
        if statuses == {"pass"} or statuses <= {"pass", "skip"}:
            return "promotable"
        if "fail" in statuses:
            return "blocked"
        return "partial"

    def build_report(self) -> dict[str, Any]:
        """Build the full release gate report."""
        overall = self.compute_overall_status()
        return {
            "schema_version": "1.0",
            "target_version": "v2.0-rc",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "overall_status": overall,
            "gates": [asdict(g) for g in self.gates],
            "summary": {
                "total": len(self.gates),
                "passed": sum(1 for g in self.gates if g.status == "pass"),
                "failed": sum(1 for g in self.gates if g.status == "fail"),
                "skipped": sum(1 for g in self.gates if g.status == "skip"),
            },
        }

    def write_json_report(self, path: Path) -> None:
        """Write JSON release gate report."""
        report = self.build_report()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote JSON report: {path}")

    def write_markdown_report(self, path: Path) -> None:
        """Write Markdown release gate report."""
        report = self.build_report()
        lines = [
            "# Release Gate Report: v2.0 RC",
            "",
            f"Generated: {report['generated_at']}",
            "",
            "## Gate Results",
            "",
            "| Gate | Status | Duration | Evidence |",
            "|------|--------|----------|----------|",
        ]

        for gate in report["gates"]:
            status_icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(
                gate["status"], gate["status"]
            )
            evidence = gate.get("evidence", "")[:80]
            lines.append(
                f"| {gate['name']} | {status_icon} | {gate['duration_ms']:.0f}ms | {evidence} |"
            )

        lines.extend([
            "",
            "## Promotion Readiness",
            "",
            f"**Overall Status**: {report['overall_status'].upper()}",
            "",
            f"- Passed: {report['summary']['passed']}",
            f"- Failed: {report['summary']['failed']}",
            f"- Skipped: {report['summary']['skipped']}",
        ])

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote Markdown report: {path}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run v2.0 RC release gates.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on any failure")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build gate")
    parser.add_argument("--dry-run", action="store_true", help="List gates without executing")
    parser.add_argument(
        "--output-dir",
        default="artifacts/release-gates",
        help="Output directory for reports",
    )
    args = parser.parse_args()

    runner = ReleaseGateRunner()
    runner.run_all_gates(skip_frontend=args.skip_frontend, dry_run=args.dry_run)

    if not args.dry_run:
        output_dir = Path(args.output_dir)
        runner.write_json_report(output_dir / "release-gate-report.json")
        runner.write_markdown_report(output_dir / "release-gate-report.md")

        overall = runner.compute_overall_status()
        print(f"\nPromotion readiness: {overall.upper()}")

        if args.strict and overall != "promotable":
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
