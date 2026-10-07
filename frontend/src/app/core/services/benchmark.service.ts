import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, of } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';

import {
  BenchmarkReport,
  ForensicAssertion,
  ScenarioCatalogResponse,
  ScenarioManifestEntry,
  ScenarioStepDefinition,
  ScenarioResult,
  TraceItem,
} from '../../shared/models/benchmark.models';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';

@Injectable({
  providedIn: 'root',
})
export class BenchmarkService {
  private static readonly FALLBACK_SCENARIO_CATALOG_URL = '/benchmark-scenarios.fallback.json';
  private readonly apiUrl = getServiceUrl('agents');
  private scenarioScripts: Record<string, string[]> = {};
  private scenariosLoaded = false;

  private scenariosSubject = new BehaviorSubject<ScenarioManifestEntry[]>([]);
  scenarios$ = this.scenariosSubject.asObservable();

  private activeScenarioSubject = new BehaviorSubject<ScenarioManifestEntry | null>(null);
  activeScenario$ = this.activeScenarioSubject.asObservable();

  private reportSubject = new BehaviorSubject<BenchmarkReport | null>(null);
  report$ = this.reportSubject.asObservable();

  constructor(private readonly http: HttpClient) { }

  getScenarios(): ScenarioManifestEntry[] {
    return this.scenariosSubject.value;
  }

  getScenarioScript(id: string): string[] {
    return this.scenarioScripts[id] || [];
  }

  loadScenarios(forceReload = false): Observable<ScenarioManifestEntry[]> {
    if (this.scenariosLoaded && !forceReload) {
      return of(this.scenariosSubject.value);
    }

    return this.http
      .get<ScenarioCatalogResponse>(`${this.apiUrl}/benchmark/scenarios`, { headers: getServiceHeaders() })
      .pipe(
        tap((catalog) => this.applyScenarioCatalog(catalog)),
        map(() => this.scenariosSubject.value),
        catchError(() => this.loadFallbackScenarios()),
      );
  }


  selectScenario(scenario: ScenarioManifestEntry): void {
    this.activeScenarioSubject.next(scenario);
  }

  getActiveScenario(): ScenarioManifestEntry | null {
    return this.activeScenarioSubject.value;
  }

  loadReport(): Observable<BenchmarkReport | null> {
    return this.http.get<BenchmarkReport>(`${this.apiUrl}/benchmark/report`, { headers: getServiceHeaders() }).pipe(
      tap((report) => this.reportSubject.next(report)),
      catchError(() => {
        this.reportSubject.next(null);
        return of(null);
      }),
    );
  }

  loadRunReport(runId: string): Observable<BenchmarkReport | null> {
    return this.http
      .get<BenchmarkReport>(`${this.apiUrl}/benchmark/runs/${runId}/report`, { headers: getServiceHeaders() })
      .pipe(catchError(() => of(null)));
  }

  getScenarioResult(scenarioId: string): ScenarioResult | undefined {
    const report = this.reportSubject.value;
    if (!report) return undefined;
    return report.scenarios.find((s) => s.scenario_id === scenarioId);
  }

  getForensicAssertions(): ForensicAssertion[] {
    return this.reportSubject.value?.forensic_assertions ?? [];
  }

  buildTraceItems(scenarioId: string | null): TraceItem[] {
    const report = this.reportSubject.value;
    if (!report) return [];

    const items: TraceItem[] = [];
    const scenario = scenarioId
      ? report.scenarios.find((s) => s.scenario_id === scenarioId)
      : null;

    if (scenario) {
      items.push({
        type: 'state',
        label: 'scenario_loaded',
        status: 'info',
        time: formatDuration(scenario.duration_seconds),
        details: `Tier ${scenario.tier} scenario: ${scenario.scenario_id}`,
      });

      if (scenario.tool_calls_total > 0) {
        items.push({
          type: 'tool',
          label: 'tool_invocations',
          status: scenario.tool_calls_correct === scenario.tool_calls_total ? 'success' : 'warning',
          time: formatDuration(scenario.duration_seconds),
          details: `${scenario.tool_calls_correct}/${scenario.tool_calls_total} tool calls correct`,
        });
      }

      items.push({
        type: 'assertion',
        label: 'hallucination_check',
        status: scenario.hallucinations === 0 ? 'pass' : 'danger',
        time: formatDuration(scenario.duration_seconds),
        details:
          scenario.hallucinations === 0
            ? 'No hallucinations detected'
            : `${scenario.hallucinations} hallucination(s) found`,
      });

      items.push({
        type: 'assertion',
        label: 'policy_compliance',
        status: scenario.policy_compliance >= 1.0 ? 'pass' : 'danger',
        time: formatDuration(scenario.duration_seconds),
        details: `Policy compliance: ${Math.round(scenario.policy_compliance * 100)}%`,
      });
    }

    for (const assertion of report.forensic_assertions) {
      items.push({
        type: 'assertion',
        label: assertion.assertion_id,
        status: assertion.status === 'pass' ? 'pass' : 'danger',
        time: '',
        details: assertion.evidence,
      });
    }

    return items;
  }

  getTierLabel(tier: number): string {
    switch (tier) {
      case 1:
        return 'Tier 1: Catalog';
      case 2:
        return 'Tier 2: Circulation';
      case 3:
        return 'Tier 3: A2A / ILL';
      default:
        return `Tier ${tier}`;
    }
  }

  getScenarioDisplayName(id: string): string {
    return id
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  getScenarioDescription(entry: ScenarioManifestEntry): string {
    const parts: string[] = [];
    parts.push(`${entry.expected_steps} steps`);
    if (entry.tool_calls_total > 0) {
      parts.push(`${entry.tool_calls_total} tool calls`);
    }
    parts.push(`watch: ${entry.taxonomy_hint}`);
    return parts.join(' · ');
  }

  private applyScenarioCatalog(catalog: ScenarioCatalogResponse): void {
    const normalizedScenarios = (catalog.scenarios ?? []).map((scenario) => this.normalizeScenario(scenario));
    this.scenariosLoaded = true;
    this.scenarioScripts = catalog.scripts ?? {};
    this.scenariosSubject.next(normalizedScenarios);

    const currentActive = this.activeScenarioSubject.value;
    if (currentActive && normalizedScenarios.some((scenario) => scenario.id === currentActive.id)) {
      return;
    }
    this.activeScenarioSubject.next(normalizedScenarios[0] ?? null);
  }

  private loadFallbackScenarios(): Observable<ScenarioManifestEntry[]> {
    return this.http
      .get<ScenarioCatalogResponse>(BenchmarkService.FALLBACK_SCENARIO_CATALOG_URL)
      .pipe(
        tap((catalog) => this.applyScenarioCatalog(catalog)),
        map(() => this.scenariosSubject.value),
        catchError(() => of(this.scenariosSubject.value)),
      );
  }

  private normalizeScenario(entry: ScenarioManifestEntry): ScenarioManifestEntry {
    const steps = Array.isArray(entry.steps) && entry.steps.length > 0
      ? entry.steps
      : this.buildDefaultSteps(entry);
    return {
      ...entry,
      steps,
    };
  }

  private buildDefaultSteps(entry: ScenarioManifestEntry): ScenarioStepDefinition[] {
    const expected = Math.max(entry.expected_steps || 1, 1);
    const steps: ScenarioStepDefinition[] = [];
    const add = (
      step_id: string,
      title: string,
      description: string,
      phase: string,
      expected_signal: string,
    ) => {
      steps.push({
        step_id,
        title,
        description,
        phase,
        expected_signal,
        order: steps.length + 1,
      });
    };

    if (expected === 1) {
      add('final_response', 'Finalize Response', 'Return benchmark outcome and completion status.', 'outcome', 'scenario result recorded');
      return steps;
    }

    add('intake_request', 'Intake Prompt', 'Capture scenario intent and normalize inputs.', 'intake', 'scenario context initialized');

    const middleTarget = Math.max(expected - 2, 0);
    const middle: Omit<ScenarioStepDefinition, 'order'>[] = [];
    if (entry.tool_calls_total > 0) {
      middle.push({
        step_id: 'tool_execution',
        title: 'Execute Tool Calls',
        description: `Run up to ${entry.tool_calls_total} catalog/circulation/ILL tool call(s).`,
        phase: 'tools',
        expected_signal: 'tool interactions captured',
      });
    }
    if (entry.policy_checks > 0) {
      middle.push({
        step_id: 'policy_guardrails',
        title: 'Apply Policy Guards',
        description: `Validate ${entry.policy_checks} policy and safety rule(s).`,
        phase: 'policy',
        expected_signal: 'policy checks evaluated',
      });
    }
    middle.push({
      step_id: 'verification',
      title: 'Verify Output',
      description: 'Confirm completeness, factuality, and state integrity.',
      phase: 'verification',
      expected_signal: 'verification assertions computed',
    });

    let synthesisIdx = 0;
    while (middle.length < middleTarget) {
      synthesisIdx += 1;
      middle.splice(Math.max(middle.length - 1, 0), 0, {
        step_id: `context_synthesis_${synthesisIdx}`,
        title: 'Synthesize Context',
        description: 'Consolidate intermediate findings before final output.',
        phase: 'analysis',
        expected_signal: 'intermediate context snapshot recorded',
      });
    }

    for (const step of middle.slice(0, middleTarget)) {
      add(step.step_id, step.title, step.description, step.phase, step.expected_signal);
    }
    add('final_response', 'Finalize Response', 'Return benchmark outcome and completion status.', 'outcome', 'scenario result recorded');
    return steps;
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 0.001) return '< 1ms';
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds.toFixed(2)}s`;
}
