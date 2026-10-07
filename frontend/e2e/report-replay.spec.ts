import { expect, test } from '@playwright/test';

interface StoredUser {
  id: string;
  name: string;
  role: 'patron' | 'staff';
  avatarInitials: string;
}

async function setStoredUser(page: import('@playwright/test').Page, user: StoredUser): Promise<void> {
  await page.addInitScript((storedUser) => {
    localStorage.setItem('ai_librarian_current_user', JSON.stringify(storedUser));
  }, user);
}

/** Helper: mock all background service calls so pages load cleanly. */
async function mockBackendDefaults(page: import('@playwright/test').Page) {
  await page.route('**://localhost:800*/health', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
  );
  await page.route('**://localhost:8000/benchmark/scenarios', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        manifest_version: '1.4',
        suite: 'v1_scenarios',
        generated_at: '2026-02-09T00:00:00Z',
        scenarios: [],
        scripts: {},
      }),
    }),
  );
  await page.route('**://localhost:8000/benchmark/report', (route) =>
    route.fulfill({ status: 404 }),
  );
}

const MOCK_REPORT = {
  schema_version: '1.1',
  generated_at: '2026-01-15T10:02:30Z',
  summary: {
    total: 12,
    passed: 10,
    failed: 2,
    completion: 0.83,
    completion_rate_percent: 83,
    hallucinations: 1,
    tool_precision: 0.92,
    tool_precision_percent: 92,
    policy_compliance: 1.0,
    policy_compliance_percent: 100,
  },
  scenarios: [
    {
      scenario_id: 'search_by_author',
      tier: 1,
      status: 'passed',
      completion: 1.0,
      tool_calls_correct: 2,
      tool_calls_total: 2,
      hallucinations: 0,
      duration_seconds: 3.45,
    },
    {
      scenario_id: 'ill_request_flow',
      tier: 3,
      status: 'failed',
      completion: 0.5,
      tool_calls_correct: 1,
      tool_calls_total: 3,
      hallucinations: 1,
      duration_seconds: 8.12,
    },
  ],
  forensic_assertions: [
    {
      assertion_id: 'inventory_conservation_v1',
      status: 'pass',
      severity: 'critical',
      evidence: 'Total inventory count is conserved across all operations.',
    },
    {
      assertion_id: 'financial_integrity_v1',
      status: 'fail',
      severity: 'critical',
      evidence: 'Fine balance mismatch detected: expected $5.00, found $4.50.',
    },
  ],
};

const MOCK_TRACE: Array<Record<string, unknown>> = [
  {
    trace_id: 'tr-001',
    run_id: 'run-trace-001',
    scenario_id: null,
    event_type: 'benchmark_run_start',
    source: 'benchmark_runner',
    timestamp: '2026-01-15T10:00:00Z',
    payload: { suite: 'scenarios' },
  },
  {
    trace_id: 'tr-002',
    run_id: 'run-trace-001',
    scenario_id: 'search_by_author',
    event_type: 'scenario_start',
    source: 'benchmark_runner',
    timestamp: '2026-01-15T10:00:01Z',
    payload: { tier: 1 },
  },
  {
    trace_id: 'tr-003',
    run_id: 'run-trace-001',
    scenario_id: 'search_by_author',
    event_type: 'scenario_end',
    source: 'benchmark_runner',
    timestamp: '2026-01-15T10:00:04Z',
    payload: { status: 'passed', duration: 3.45 },
  },
];

test.describe('Report view', () => {
  test.beforeEach(async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
  });

  test('renders benchmark report with metrics', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-rpt-001/report', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_REPORT),
      }),
    );

    await page.goto('/#/reports/run-rpt-001');

    // Header
    await expect(page.getByText('Benchmark Report')).toBeVisible();
    await expect(page.getByText('v1.1')).toBeVisible();

    // Summary metrics
    // Summary metric cards
    await expect(page.locator('.metric-value').filter({ hasText: '83%' })).toBeVisible();
    await expect(page.locator('.metric-value').filter({ hasText: '92%' })).toBeVisible();
    await expect(page.locator('.metric-value').filter({ hasText: '100%' })).toBeVisible();

    // Scenarios passed progress
    await expect(page.getByText('10/12')).toBeVisible();

    // Scenario table
    await expect(page.getByText('Search By Author')).toBeVisible();
    await expect(page.getByText('Ill Request Flow')).toBeVisible();
  });

  test('renders forensic assertions', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-rpt-001/report', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_REPORT),
      }),
    );

    await page.goto('/#/reports/run-rpt-001');

    await expect(page.getByText('Forensic Assertions')).toBeVisible();
    await expect(page.getByText('inventory_conservation_v1')).toBeVisible();
    await expect(page.getByText('financial_integrity_v1')).toBeVisible();
    await expect(page.getByText(/Fine balance mismatch/)).toBeVisible();
  });

  test('shows error when report is not available', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-no-report/report', (route) =>
      route.fulfill({ status: 404 }),
    );

    await page.goto('/#/reports/run-no-report');

    await expect(page.getByText(/not available/i)).toBeVisible();
  });
});

test.describe('Replay view', () => {
  test.beforeEach(async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
  });

  test('renders trace event timeline', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-trace-001/trace', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_TRACE),
      }),
    );

    await page.goto('/#/replay/run-trace-001');

    // Header
    await expect(page.getByText('Trace Replay')).toBeVisible();
    await expect(page.getByText('3 events')).toBeVisible();

    // Event types visible
    await expect(page.getByText('benchmark_run_start')).toBeVisible();
    await expect(page.getByText('scenario_start')).toBeVisible();
    await expect(page.getByText('scenario_end')).toBeVisible();
  });

  test('shows empty state when trace not available', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-no-trace/trace', (route) =>
      route.fulfill({ status: 404 }),
    );

    await page.goto('/#/replay/run-no-trace');

    await expect(page.getByText(/not available/i)).toBeVisible();
  });
});
