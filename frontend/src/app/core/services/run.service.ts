import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, timer } from 'rxjs';
import { catchError, switchMap, takeWhile } from 'rxjs/operators';
import { getServiceHeaders, getServiceUrl } from '../config/app-config';

import {
  BenchmarkReport,
  LeaderboardResponse,
  ModelCatalogResponse,
  RunComparisonRequest,
  RunComparisonResponse,
  RunCreateRequest,
  RunCreateResponse,
  RunListResponse,
  RunMetadata,
  TraceEvent,
} from '../../shared/models/benchmark.models';

@Injectable({
  providedIn: 'root',
})
export class RunService {
  private readonly apiUrl = getServiceUrl('agents');

  constructor(private readonly http: HttpClient) { }

  createRun(request: RunCreateRequest): Observable<RunCreateResponse> {
    return this.http.post<RunCreateResponse>(`${this.apiUrl}/benchmark/runs`, request, { headers: getServiceHeaders() });
  }

  listRuns(): Observable<RunListResponse> {
    return this.http.get<RunListResponse>(`${this.apiUrl}/benchmark/runs`, { headers: getServiceHeaders() });
  }

  getRun(runId: string): Observable<RunMetadata> {
    return this.http.get<RunMetadata>(`${this.apiUrl}/benchmark/runs/${runId}`, { headers: getServiceHeaders() });
  }

  getRunReport(runId: string): Observable<BenchmarkReport> {
    return this.http.get<BenchmarkReport>(`${this.apiUrl}/benchmark/runs/${runId}/report`, { headers: getServiceHeaders() });
  }

  getRunTrace(runId: string): Observable<TraceEvent[]> {
    return this.http.get<TraceEvent[]>(`${this.apiUrl}/benchmark/runs/${runId}/trace`, { headers: getServiceHeaders() });
  }

  getRunArtifacts(runId: string): Observable<{ run_id: string; artifacts: string[] }> {
    return this.http.get<{ run_id: string; artifacts: string[] }>(
      `${this.apiUrl}/benchmark/runs/${runId}/artifacts`,
      { headers: getServiceHeaders() }
    );
  }

  getModels(): Observable<ModelCatalogResponse> {
    return this.http.get<ModelCatalogResponse>(
      `${this.apiUrl}/benchmark/models`,
      { headers: getServiceHeaders() },
    );
  }

  compareRuns(request: RunComparisonRequest): Observable<RunComparisonResponse> {
    return this.http.post<RunComparisonResponse>(
      `${this.apiUrl}/benchmark/compare`,
      request,
      { headers: getServiceHeaders() },
    );
  }

  getLeaderboard(suite?: string, limit = 20, minRuns = 1): Observable<LeaderboardResponse> {
    const params: Record<string, string> = {
      limit: String(limit),
      min_runs: String(minRuns),
    };
    if (suite) {
      params['suite'] = suite;
    }
    return this.http.get<LeaderboardResponse>(
      `${this.apiUrl}/benchmark/leaderboard`,
      { headers: getServiceHeaders(), params },
    );
  }

  pollRunStatus(runId: string, intervalMs = 3000): Observable<RunMetadata> {
    return timer(0, intervalMs).pipe(
      switchMap(() => this.getRun(runId)),
      takeWhile((m) => m.status === 'queued' || m.status === 'running', true),
    );
  }

  pollRunTrace(runId: string, intervalMs = 2000): Observable<TraceEvent[]> {
    return timer(0, intervalMs).pipe(
      switchMap(() =>
        this.getRunTrace(runId).pipe(
          catchError(() => of([])),
        ),
      ),
    );
  }
}
