"""Deterministic run comparison and leaderboard helpers for v2.1."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from agents.benchmark_api_models import (
    LeaderboardResponse,
    LeaderboardRow,
    RunComparisonResponse,
    RunMetricDelta,
    RunMetadata,
    RunScoreSnapshot,
    RunStatus,
    ScenarioDelta,
    TierDelta,
)

_COMPLETED_STATUSES = {RunStatus.PASSED, RunStatus.FAILED}


def is_completed_run(metadata: RunMetadata) -> bool:
    """Return whether a run is eligible for comparison/leaderboard."""
    return metadata.status in _COMPLETED_STATUSES


def load_report(metadata: RunMetadata) -> dict[str, Any] | None:
    """Load a run report JSON payload from metadata path."""
    if not metadata.report_path:
        return None
    report_path = Path(metadata.report_path)
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def composite_score(summary: dict[str, Any]) -> float:
    """Compute composite score using v2.1 weighting contract."""
    total = max(int(summary.get("total", 0) or 0), 1)
    completion_norm = float(summary.get("completion_rate_percent", 0.0) or 0.0) / 100.0
    policy_norm = float(summary.get("policy_compliance_percent", 0.0) or 0.0) / 100.0
    tool_norm = float(summary.get("tool_precision_percent", 0.0) or 0.0) / 100.0
    hallucinations = float(summary.get("hallucinations", 0.0) or 0.0)
    hallucination_penalty = min(hallucinations / float(total), 1.0)
    score = 100.0 * (
        (0.35 * completion_norm)
        + (0.25 * policy_norm)
        + (0.25 * tool_norm)
        + (0.15 * (1.0 - hallucination_penalty))
    )
    return round(score, 4)


def build_snapshot(metadata: RunMetadata, report: dict[str, Any]) -> RunScoreSnapshot:
    """Create typed run snapshot used in comparison/leaderboard outputs."""
    summary = report.get("summary", {})
    return RunScoreSnapshot(
        run_id=metadata.run_id,
        suite=metadata.suite,
        status=metadata.status,
        model_name=metadata.model_name or "unknown",
        model_family=metadata.model_family or "gemini",
        total_scenarios=int(summary.get("total", 0) or 0),
        completion_rate_percent=round(float(summary.get("completion_rate_percent", 0.0) or 0.0), 4),
        policy_compliance_percent=round(float(summary.get("policy_compliance_percent", 0.0) or 0.0), 4),
        tool_precision_percent=round(float(summary.get("tool_precision_percent", 0.0) or 0.0), 4),
        hallucinations=int(summary.get("hallucinations", 0) or 0),
        composite_score=composite_score(summary),
    )


def _rank_key(snapshot: RunScoreSnapshot) -> tuple[float, float, float, float, str]:
    return (
        -snapshot.composite_score,
        -snapshot.policy_compliance_percent,
        -snapshot.tool_precision_percent,
        float(snapshot.hallucinations),
        snapshot.run_id,
    )


def _tier_aggregate(report: dict[str, Any]) -> dict[int, dict[str, float]]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for scenario in report.get("scenarios", []):
        tier = int(scenario.get("tier", 0) or 0)
        buckets[tier].append(scenario)

    output: dict[int, dict[str, float]] = {}
    for tier, scenarios in buckets.items():
        count = max(len(scenarios), 1)
        completion_avg = sum(float(s.get("completion", 0.0) or 0.0) for s in scenarios) / count
        policy_avg = sum(float(s.get("policy_compliance", 0.0) or 0.0) for s in scenarios) / count
        tool_total = sum(int(s.get("tool_calls_total", 0) or 0) for s in scenarios)
        tool_correct = sum(int(s.get("tool_calls_correct", 0) or 0) for s in scenarios)
        tool_precision = (float(tool_correct) / float(tool_total)) if tool_total > 0 else 1.0
        hallucinations = sum(int(s.get("hallucinations", 0) or 0) for s in scenarios)
        output[tier] = {
            "completion_rate": completion_avg * 100.0,
            "policy_compliance": policy_avg * 100.0,
            "tool_precision": tool_precision * 100.0,
            "hallucinations": float(hallucinations),
        }
    return output


def _scenario_index(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    index: dict[str, dict[str, float]] = {}
    for scenario in report.get("scenarios", []):
        scenario_id = str(scenario.get("scenario_id", "") or "")
        if not scenario_id:
            continue
        tool_total = int(scenario.get("tool_calls_total", 0) or 0)
        tool_correct = int(scenario.get("tool_calls_correct", 0) or 0)
        tool_precision = (float(tool_correct) / float(tool_total)) * 100.0 if tool_total > 0 else 100.0
        index[scenario_id] = {
            "completion": float(scenario.get("completion", 0.0) or 0.0) * 100.0,
            "policy_compliance": float(scenario.get("policy_compliance", 0.0) or 0.0) * 100.0,
            "tool_precision": tool_precision,
            "hallucinations": float(int(scenario.get("hallucinations", 0) or 0)),
        }
    return index


def build_comparison(run_reports: list[tuple[RunMetadata, dict[str, Any]]]) -> RunComparisonResponse:
    """Build a run-to-run comparison payload against baseline run_id[0]."""
    if len(run_reports) < 2:
        raise ValueError("At least two runs are required for comparison")

    snapshots = [build_snapshot(metadata, report) for metadata, report in run_reports]
    baseline_snapshot = snapshots[0]
    baseline_run_id = baseline_snapshot.run_id

    ranked = sorted(snapshots, key=_rank_key)
    ranked_ids = [snapshot.run_id for snapshot in ranked]

    run_deltas: list[RunMetricDelta] = []
    tier_deltas: list[TierDelta] = []
    scenario_deltas: list[ScenarioDelta] = []

    baseline_report = run_reports[0][1]
    baseline_tiers = _tier_aggregate(baseline_report)
    baseline_scenarios = _scenario_index(baseline_report)

    for idx in range(1, len(run_reports)):
        candidate_metadata, candidate_report = run_reports[idx]
        candidate_snapshot = snapshots[idx]

        run_deltas.append(
            RunMetricDelta(
                run_id=candidate_snapshot.run_id,
                baseline_run_id=baseline_run_id,
                composite_score_delta=round(candidate_snapshot.composite_score - baseline_snapshot.composite_score, 4),
                completion_rate_delta=round(
                    candidate_snapshot.completion_rate_percent - baseline_snapshot.completion_rate_percent,
                    4,
                ),
                policy_compliance_delta=round(
                    candidate_snapshot.policy_compliance_percent - baseline_snapshot.policy_compliance_percent,
                    4,
                ),
                tool_precision_delta=round(
                    candidate_snapshot.tool_precision_percent - baseline_snapshot.tool_precision_percent,
                    4,
                ),
                hallucinations_delta=round(
                    float(candidate_snapshot.hallucinations - baseline_snapshot.hallucinations),
                    4,
                ),
            )
        )

        candidate_tiers = _tier_aggregate(candidate_report)
        for tier in sorted(set(baseline_tiers.keys()) & set(candidate_tiers.keys())):
            base = baseline_tiers[tier]
            cand = candidate_tiers[tier]
            tier_deltas.append(
                TierDelta(
                    run_id=candidate_metadata.run_id,
                    baseline_run_id=baseline_run_id,
                    tier=tier,
                    completion_rate_delta=round(cand["completion_rate"] - base["completion_rate"], 4),
                    policy_compliance_delta=round(cand["policy_compliance"] - base["policy_compliance"], 4),
                    tool_precision_delta=round(cand["tool_precision"] - base["tool_precision"], 4),
                    hallucinations_delta=round(cand["hallucinations"] - base["hallucinations"], 4),
                )
            )

        candidate_scenarios = _scenario_index(candidate_report)
        for scenario_id in sorted(set(baseline_scenarios.keys()) & set(candidate_scenarios.keys())):
            base = baseline_scenarios[scenario_id]
            cand = candidate_scenarios[scenario_id]
            scenario_deltas.append(
                ScenarioDelta(
                    run_id=candidate_metadata.run_id,
                    baseline_run_id=baseline_run_id,
                    scenario_id=scenario_id,
                    completion_delta=round(cand["completion"] - base["completion"], 4),
                    policy_compliance_delta=round(cand["policy_compliance"] - base["policy_compliance"], 4),
                    tool_precision_delta=round(cand["tool_precision"] - base["tool_precision"], 4),
                    hallucinations_delta=int(round(cand["hallucinations"] - base["hallucinations"])),
                )
            )

    return RunComparisonResponse(
        baseline_run_id=baseline_run_id,
        ranked_run_ids=ranked_ids,
        runs=snapshots,
        run_deltas=run_deltas,
        tier_deltas=tier_deltas,
        scenario_deltas=scenario_deltas,
    )


def build_leaderboard(
    run_reports: list[tuple[RunMetadata, dict[str, Any]]],
    *,
    suite: str | None,
    min_runs: int,
    limit: int,
) -> LeaderboardResponse:
    """Build model-grouped leaderboard response from completed runs."""
    grouped: dict[str, list[RunScoreSnapshot]] = defaultdict(list)
    families: dict[str, str] = {}

    for metadata, report in run_reports:
        if suite and metadata.suite != suite:
            continue
        snapshot = build_snapshot(metadata, report)
        key = snapshot.model_name or "unknown"
        grouped[key].append(snapshot)
        families[key] = snapshot.model_family

    rows: list[LeaderboardRow] = []
    for model_name, snapshots in grouped.items():
        if len(snapshots) < min_runs:
            continue
        count = len(snapshots)
        avg_composite = sum(s.composite_score for s in snapshots) / count
        avg_completion = sum(s.completion_rate_percent for s in snapshots) / count
        avg_policy = sum(s.policy_compliance_percent for s in snapshots) / count
        avg_tool = sum(s.tool_precision_percent for s in snapshots) / count
        avg_hallucinations = sum(float(s.hallucinations) for s in snapshots) / count
        rows.append(
            LeaderboardRow(
                rank=0,
                model_name=model_name,
                model_family=families.get(model_name, "gemini"),
                run_count=count,
                avg_composite_score=round(avg_composite, 4),
                avg_completion_rate=round(avg_completion, 4),
                avg_policy_compliance=round(avg_policy, 4),
                avg_tool_precision=round(avg_tool, 4),
                avg_hallucinations=round(avg_hallucinations, 4),
            )
        )

    rows = sorted(
        rows,
        key=lambda row: (
            -row.avg_composite_score,
            -row.avg_policy_compliance,
            -row.avg_tool_precision,
            row.avg_hallucinations,
            row.model_name,
        ),
    )

    if limit > 0:
        rows = rows[:limit]

    ranked_rows: list[LeaderboardRow] = []
    for idx, row in enumerate(rows, start=1):
        ranked_rows.append(
            LeaderboardRow(
                rank=idx,
                model_name=row.model_name,
                model_family=row.model_family,
                run_count=row.run_count,
                avg_composite_score=row.avg_composite_score,
                avg_completion_rate=row.avg_completion_rate,
                avg_policy_compliance=row.avg_policy_compliance,
                avg_tool_precision=row.avg_tool_precision,
                avg_hallucinations=row.avg_hallucinations,
            )
        )

    return LeaderboardResponse(
        suite=suite,
        min_runs=min_runs,
        total_models=len(ranked_rows),
        rows=ranked_rows,
    )
