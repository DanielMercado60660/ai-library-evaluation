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
        scenarios: [
          {
            id: 'tier1_author_search',
            nodeid_pattern: 'test_tier1_find_book_by_author',
            tier: 1,
            expected_steps: 3,
            policy_checks: 1,
            tool_calls_total: 1,
            taxonomy_hint: 'tool_misuse',
          },
        ],
        scripts: {
          tier1_author_search: ['Do you have any books by Maren Greyhorn?'],
        },
      }),
    }),
  );
  await page.route('**://localhost:8000/benchmark/report', (route) =>
    route.fulfill({ status: 404 }),
  );
}

test.describe('Run orchestration routes', () => {
  test.beforeEach(async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
  });

  test('shows empty state when no runs exist', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ runs: [], total: 0 }),
        });
      }
      return route.continue();
    });

    await page.goto('/#/runs');

    await expect(page.getByRole('heading', { name: 'Benchmark Runs' })).toBeVisible();
    await expect(page.getByText('No benchmark runs yet')).toBeVisible();
    await expect(page.getByRole('button', { name: 'New Benchmark Run' })).toBeVisible();
  });

  test('renders run list with mocked data', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            runs: [
              {
                run_id: 'run-abc-001',
                suite: 'scenarios',
                status: 'passed',
                started_at: '2026-01-15T10:00:00Z',
                completed_at: '2026-01-15T10:02:30Z',
                artifact_dir: '/tmp/runs/run-abc-001',
                report_path: '/tmp/runs/run-abc-001/report.json',
                trace_path: '/tmp/runs/run-abc-001/trace.jsonl',
                artifact_paths: [],
                error_message: null,
              },
              {
                run_id: 'run-abc-002',
                suite: 'scenarios',
                status: 'failed',
                started_at: '2026-01-15T11:00:00Z',
                completed_at: '2026-01-15T11:01:00Z',
                artifact_dir: '/tmp/runs/run-abc-002',
                report_path: null,
                trace_path: null,
                artifact_paths: [],
                error_message: 'Test failure',
              },
            ],
            total: 2,
          }),
        });
      }
      return route.continue();
    });

    await page.goto('/#/runs');

    await expect(page.getByText('run-abc-001')).toBeVisible();
    await expect(page.getByText('run-abc-002')).toBeVisible();
    await expect(page.getByText('passed')).toBeVisible();
    await expect(page.getByText('failed')).toBeVisible();
  });

  test('creates a new run and navigates to detail', async ({ page }) => {
    await mockBackendDefaults(page);

    // Initial list: empty
    let listCallCount = 0;
    await page.route('**://localhost:8000/benchmark/runs', (route) => {
      if (route.request().method() === 'GET') {
        listCallCount++;
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ runs: [], total: 0 }),
        });
      }
      // POST: create run
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 202,
          contentType: 'application/json',
          body: JSON.stringify({
            run_id: 'run-new-001',
            status: 'queued',
            artifact_dir: '/tmp/runs/run-new-001',
          }),
        });
      }
      return route.continue();
    });

    // Mock the run detail endpoint for navigation target
    await page.route('**://localhost:8000/benchmark/runs/run-new-001', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-new-001',
          suite: 'scenarios',
          status: 'queued',
          started_at: '2026-01-15T12:00:00Z',
          completed_at: null,
          artifact_dir: '/tmp/runs/run-new-001',
          report_path: null,
          trace_path: null,
          artifact_paths: [],
          error_message: null,
        }),
      }),
    );

    await page.goto('/#/runs');
    await page.getByRole('button', { name: 'New Benchmark Run' }).click();
    await page.getByRole('button', { name: 'Start Run' }).click();

    // Should navigate to the run detail page
    await page.waitForURL('**/#/runs/run-new-001');
    await expect(page.getByText('run-new-001')).toBeVisible();
  });

  test('shows error state for nonexistent run', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-nonexistent', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not found"}' }),
    );

    await page.goto('/#/runs/run-nonexistent');

    await expect(page.getByText(/not found/i)).toBeVisible();
  });

  test('navigates between Assistant and Benchmarks via sidebar links', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ runs: [], total: 0 }),
      }),
    );

    // Start on chat
    await page.goto('/#/chat');
    await expect(page.locator('input[name="userInput"]')).toBeVisible();

    // Navigate to runs
    await page.getByRole('link', { name: /Benchmarks/ }).click();
    await page.waitForURL('**/#/runs');
    await expect(page.getByRole('heading', { name: 'Benchmark Runs' })).toBeVisible();

    // Navigate back to chat
    await page.getByRole('link', { name: /Assistant/ }).click();
    await page.waitForURL('**/#/chat');
    await expect(page.locator('input[name="userInput"]')).toBeVisible();
  });

  test('run detail shows action links when report/trace available', async ({ page }) => {
    await mockBackendDefaults(page);
    await page.route('**://localhost:8000/benchmark/runs/run-detail-001', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-detail-001',
          suite: 'scenarios',
          status: 'passed',
          started_at: '2026-01-15T10:00:00Z',
          completed_at: '2026-01-15T10:02:30Z',
          artifact_dir: '/tmp/runs/run-detail-001',
          report_path: '/tmp/runs/run-detail-001/report.json',
          trace_path: '/tmp/runs/run-detail-001/trace.jsonl',
          artifact_paths: ['report.json', 'trace.jsonl'],
          error_message: null,
        }),
      }),
    );
    await page.route('**://localhost:8000/benchmark/runs/run-detail-001/trace', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            trace_id: 'trace-001',
            run_id: 'run-detail-001',
            scenario_id: null,
            event_type: 'benchmark_run_start',
            source: 'benchmark_runner',
            timestamp: '2026-01-15T10:00:00Z',
            payload: { suite: 'scenarios' },
          },
          {
            trace_id: 'trace-001',
            run_id: 'run-detail-001',
            scenario_id: 'tier1_author_search',
            event_type: 'scenario_step_end',
            source: 'benchmark_runner',
            timestamp: '2026-01-15T10:00:02Z',
            payload: { step_id: 'tool_execution', title: 'Execute Tool Calls', status: 'pass' },
          },
        ]),
      }),
    );

    await page.goto('/#/runs/run-detail-001');

    await expect(page.getByText('run-detail-001')).toBeVisible();
    await expect(page.getByText('passed')).toBeVisible();
    await expect(page.getByText('Audit Stream')).toBeVisible();
    await expect(page.getByText('Benchmark Run Started')).toBeVisible();
    await expect(page.getByText('View Report')).toBeVisible();
    await expect(page.getByText('View Trace')).toBeVisible();
  });
});
