import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { RunService } from './run.service';
import {
  RunCreateRequest,
  RunCreateResponse,
  RunListResponse,
  RunMetadata,
  BenchmarkReport,
  TraceEvent,
  RunComparisonRequest,
  RunComparisonResponse,
  LeaderboardResponse,
} from '../../shared/models/benchmark.models';

describe('RunService', () => {
  let service: RunService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [RunService],
    });

    service = TestBed.inject(RunService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('createRun should POST to /benchmark/runs', () => {
    const request: RunCreateRequest = {
      suite: 'scenarios',
      model_name: 'gemini-3.0-flash',
    };
    const response: RunCreateResponse = {
      run_id: 'run-001',
      status: 'queued',
      artifact_dir: '/tmp/artifacts',
      model_name: 'gemini-3.0-flash',
      model_family: 'gemini',
    };

    service.createRun(request).subscribe((r) => {
      expect(r.run_id).toBe('run-001');
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs') && r.method === 'POST');
    expect(req.request.body.suite).toBe('scenarios');
    req.flush(response);
  });

  it('listRuns should GET /benchmark/runs', () => {
    const response: RunListResponse = { runs: [], total: 0 };

    service.listRuns().subscribe((r) => {
      expect(r.total).toBe(0);
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs') && r.method === 'GET');
    req.flush(response);
  });

  it('getRun should GET /benchmark/runs/:id', () => {
    const metadata: RunMetadata = {
      run_id: 'run-001',
      suite: 'scenarios',
      status: 'passed',
      model_name: 'gemini-3.0-flash',
      model_family: 'gemini',
      started_at: '2026-01-01T00:00:00Z',
      completed_at: '2026-01-01T00:01:00Z',
      artifact_dir: '/tmp',
      report_path: null,
      trace_path: null,
      artifact_paths: [],
      error_message: null,
    };

    service.getRun('run-001').subscribe((r) => {
      expect(r.run_id).toBe('run-001');
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001'));
    req.flush(metadata);
  });

  it('getRunReport should GET /benchmark/runs/:id/report', () => {
    const report = { schema_version: '1.5' } as BenchmarkReport;

    service.getRunReport('run-001').subscribe((r) => {
      expect(r.schema_version).toBe('1.5');
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001/report'));
    req.flush(report);
  });

  it('getRunTrace should GET /benchmark/runs/:id/trace', () => {
    const events: TraceEvent[] = [
      {
        trace_id: 't1',
        run_id: 'run-001',
        scenario_id: null,
        event_type: 'test_start',
        source: 'test',
        timestamp: '2026-01-01T00:00:00Z',
        payload: {},
      },
    ];

    service.getRunTrace('run-001').subscribe((r) => {
      expect(r.length).toBe(1);
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001/trace'));
    req.flush(events);
  });

  it('compareRuns should POST to /benchmark/compare', () => {
    const request: RunComparisonRequest = { run_ids: ['r1', 'r2'] };
    const response = { baseline_run_id: 'r1', ranked_run_ids: ['r1', 'r2'] } as RunComparisonResponse;

    service.compareRuns(request).subscribe((r) => {
      expect(r.baseline_run_id).toBe('r1');
    });

    const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/compare') && r.method === 'POST');
    req.flush(response);
  });

  it('getLeaderboard should include query params', () => {
    const response: LeaderboardResponse = { min_runs: 1, total_models: 0, rows: [] };

    service.getLeaderboard('scenarios', 10, 2).subscribe();

    const req = httpMock.expectOne((r) => r.url.includes('/benchmark/leaderboard'));
    expect(req.request.params.get('suite')).toBe('scenarios');
    expect(req.request.params.get('limit')).toBe('10');
    expect(req.request.params.get('min_runs')).toBe('2');
    req.flush(response);
  });

  it('pollRunStatus should complete on terminal status', fakeAsync(() => {
    const statuses: string[] = [];

    service.pollRunStatus('run-001', 500).subscribe((m) => {
      statuses.push(m.status);
    });

    // First poll — running
    tick(0);
    const req1 = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001'));
    req1.flush({
      run_id: 'run-001', suite: 's', status: 'running', model_name: 'm',
      model_family: 'f', started_at: '', completed_at: null, artifact_dir: '',
      report_path: null, trace_path: null, artifact_paths: [], error_message: null,
    } as RunMetadata);

    // Second poll — passed (terminal)
    tick(500);
    const req2 = httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001'));
    req2.flush({
      run_id: 'run-001', suite: 's', status: 'passed', model_name: 'm',
      model_family: 'f', started_at: '', completed_at: '', artifact_dir: '',
      report_path: null, trace_path: null, artifact_paths: [], error_message: null,
    } as RunMetadata);

    expect(statuses).toEqual(['running', 'passed']);
  }));
});
