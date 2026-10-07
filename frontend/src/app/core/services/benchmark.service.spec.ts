import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { BenchmarkService } from './benchmark.service';
import {
  BenchmarkReport,
  ScenarioCatalogResponse,
  ScenarioManifestEntry,
  ScenarioResult,
} from '../../shared/models/benchmark.models';

function makeScenarioCatalog(scenarios: Partial<ScenarioManifestEntry>[] = []): ScenarioCatalogResponse {
  return {
    manifest_version: '1.0',
    suite: 'scenarios',
    generated_at: '2026-01-01T00:00:00Z',
    scenarios: scenarios.map((s, i) => ({
      id: s.id ?? `scenario_${i}`,
      nodeid_pattern: s.nodeid_pattern ?? `test::scenario_${i}`,
      tier: s.tier ?? 1,
      expected_steps: s.expected_steps ?? 2,
      policy_checks: s.policy_checks ?? 0,
      tool_calls_total: s.tool_calls_total ?? 1,
      taxonomy_hint: s.taxonomy_hint ?? 'catalog',
      steps: s.steps ?? [],
    })),
    scripts: {},
  };
}

function makeReport(overrides: Partial<BenchmarkReport> = {}): BenchmarkReport {
  return {
    schema_version: '1.5',
    suite: 'scenarios',
    generated_at: '2026-01-01T00:00:00Z',
    summary: {
      total: 1, passed: 1, failed: 0, skipped: 0,
      completion: 1, step_accuracy: 1, policy_compliance: 1,
      hallucinations: 0, tool_calls_total: 1, tool_calls_correct: 1,
      tool_precision: 1, completion_rate_percent: 100,
      step_accuracy_percent: 100, policy_compliance_percent: 100,
      tool_precision_percent: 100,
    },
    scenarios: [{
      scenario_id: 'scenario_0',
      nodeid: 'test::scenario_0',
      status: 'passed',
      tier: 1,
      duration_seconds: 1.5,
      completion: 1,
      step_accuracy: 1,
      policy_compliance: 1,
      hallucinations: 0,
      tool_calls_total: 1,
      tool_calls_correct: 1,
      taxonomy: 'catalog',
      detail: '',
    }],
    forensic_assertions: [],
    ...overrides,
  };
}

describe('BenchmarkService', () => {
  let service: BenchmarkService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [BenchmarkService],
    });

    service = TestBed.inject(BenchmarkService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  describe('loadScenarios', () => {
    it('should fetch from /benchmark/scenarios and populate scenarios$', () => {
      const catalog = makeScenarioCatalog([{ id: 's1', tier: 1 }, { id: 's2', tier: 2 }]);

      let scenarios: ScenarioManifestEntry[] = [];
      service.scenarios$.subscribe((s) => (scenarios = s));

      service.loadScenarios().subscribe();
      const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios'));
      req.flush(catalog);

      expect(scenarios.length).toBe(2);
      expect(scenarios[0].id).toBe('s1');
    });

    it('should cache results on second call', () => {
      const catalog = makeScenarioCatalog([{ id: 's1' }]);

      service.loadScenarios().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios')).flush(catalog);

      // Second call — no HTTP request
      service.loadScenarios().subscribe();
      httpMock.expectNone((r) => r.url.endsWith('/benchmark/scenarios'));
    });

    it('should force reload when forceReload=true', () => {
      const catalog = makeScenarioCatalog([{ id: 's1' }]);

      service.loadScenarios().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios')).flush(catalog);

      service.loadScenarios(true).subscribe();
      const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios'));
      req.flush(catalog);
    });

    it('should fall back to static JSON on error', () => {
      service.loadScenarios().subscribe();

      const req = httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios'));
      req.error(new ProgressEvent('error'));

      // Should attempt fallback
      const fallback = httpMock.expectOne((r) => r.url.includes('benchmark-scenarios.fallback.json'));
      fallback.flush(makeScenarioCatalog([{ id: 'fallback' }]));
    });
  });

  describe('selectScenario', () => {
    it('should update activeScenario$', () => {
      const catalog = makeScenarioCatalog([{ id: 's1' }, { id: 's2' }]);

      service.loadScenarios().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/scenarios')).flush(catalog);

      let active: ScenarioManifestEntry | null = null;
      service.activeScenario$.subscribe((s) => (active = s));

      const scenarios = service.getScenarios();
      service.selectScenario(scenarios[1]);

      expect(active).toBeTruthy();
      expect(active!.id).toBe('s2');
    });
  });

  describe('loadReport', () => {
    it('should fetch from /benchmark/report and populate report$', () => {
      const report = makeReport();

      let loaded: BenchmarkReport | null = null;
      service.report$.subscribe((r) => (loaded = r));

      service.loadReport().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/report')).flush(report);

      expect(loaded).toBeTruthy();
      expect(loaded!.schema_version).toBe('1.5');
    });

    it('should set report$ to null on error', () => {
      let loaded: BenchmarkReport | null = makeReport();
      service.report$.subscribe((r) => (loaded = r));

      service.loadReport().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/report')).error(new ProgressEvent('error'));

      expect(loaded).toBeNull();
    });
  });

  describe('loadRunReport', () => {
    it('should fetch from /benchmark/runs/:id/report', () => {
      const report = makeReport();

      service.loadRunReport('run-001').subscribe((r) => {
        expect(r?.schema_version).toBe('1.5');
      });

      httpMock.expectOne((r) => r.url.endsWith('/benchmark/runs/run-001/report')).flush(report);
    });
  });

  describe('getScenarioResult', () => {
    it('should find scenario by id in current report', () => {
      const report = makeReport();

      service.loadReport().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/report')).flush(report);

      const result = service.getScenarioResult('scenario_0');
      expect(result).toBeTruthy();
      expect(result?.scenario_id).toBe('scenario_0');
    });

    it('should return undefined for unknown scenario', () => {
      const report = makeReport();

      service.loadReport().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/report')).flush(report);

      expect(service.getScenarioResult('nonexistent')).toBeUndefined();
    });
  });

  describe('buildTraceItems', () => {
    it('should construct trace items from report data', () => {
      const report = makeReport();

      service.loadReport().subscribe();
      httpMock.expectOne((r) => r.url.endsWith('/benchmark/report')).flush(report);

      const items = service.buildTraceItems('scenario_0');
      expect(items.length).toBeGreaterThan(0);
      expect(items.some((i) => i.label === 'hallucination_check')).toBeTrue();
    });
  });

  describe('getTierLabel', () => {
    it('should return correct tier labels', () => {
      expect(service.getTierLabel(1)).toBe('Tier 1: Catalog');
      expect(service.getTierLabel(2)).toBe('Tier 2: Circulation');
      expect(service.getTierLabel(3)).toBe('Tier 3: A2A / ILL');
      expect(service.getTierLabel(99)).toBe('Tier 99');
    });
  });

  describe('getScenarioDisplayName', () => {
    it('should convert underscored id to title case', () => {
      expect(service.getScenarioDisplayName('simple_search')).toBe('Simple Search');
    });
  });
});
