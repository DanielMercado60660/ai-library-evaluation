import { expect, test } from '@playwright/test';

interface StoredUser {
  id: string;
  name: string;
  role: 'patron' | 'staff';
  avatarInitials: string;
}

const RUNS = [
  {
    run_id: 'run-001',
    suite: 'scenarios',
    status: 'passed',
    model_name: 'gemini-3.0-flash',
    model_family: 'gemini',
    started_at: '2026-02-10T10:00:00Z',
    completed_at: '2026-02-10T10:02:00Z',
    artifact_dir: '/tmp/runs/run-001',
    report_path: '/tmp/runs/run-001/benchmark-report.json',
    trace_path: '/tmp/runs/run-001/benchmark-trace.jsonl',
    artifact_paths: [],
    error_message: null,
  },
  {
    run_id: 'run-002',
    suite: 'scenarios',
    status: 'failed',
    model_name: 'gemini-3.0-pro',
    model_family: 'gemini',
    started_at: '2026-02-10T11:00:00Z',
    completed_at: '2026-02-10T11:03:00Z',
    artifact_dir: '/tmp/runs/run-002',
    report_path: '/tmp/runs/run-002/benchmark-report.json',
    trace_path: '/tmp/runs/run-002/benchmark-trace.jsonl',
    artifact_paths: [],
    error_message: null,
  },
  {
    run_id: 'run-003',
    suite: 'scenarios',
    status: 'running',
    model_name: 'gemini-3.0-flash',
    model_family: 'gemini',
    started_at: '2026-02-10T12:00:00Z',
    completed_at: null,
    artifact_dir: '/tmp/runs/run-003',
    report_path: null,
    trace_path: null,
    artifact_paths: [],
    error_message: null,
  },
];

const LEADERBOARD = {
  suite: 'scenarios',
  min_runs: 1,
  total_models: 2,
  rows: [
    {
      rank: 1,
      model_name: 'gemini-3.0-flash',
      model_family: 'gemini',
      run_count: 2,
      avg_composite_score: 96.2,
      avg_completion_rate: 95.0,
      avg_policy_compliance: 99.0,
      avg_tool_precision: 97.0,
      avg_hallucinations: 0,
    },
    {
      rank: 2,
      model_name: 'gemini-3.0-pro',
      model_family: 'gemini',
      run_count: 1,
      avg_composite_score: 71.5,
      avg_completion_rate: 70.0,
      avg_policy_compliance: 80.0,
      avg_tool_precision: 75.0,
      avg_hallucinations: 2,
    },
  ],
};

const COMPARISON = {
  baseline_run_id: 'run-001',
  ranked_run_ids: ['run-001', 'run-002'],
  runs: [
    {
      run_id: 'run-001',
      suite: 'scenarios',
      status: 'passed',
      model_name: 'gemini-3.0-flash',
      model_family: 'gemini',
      total_scenarios: 2,
      completion_rate_percent: 98,
      policy_compliance_percent: 100,
      tool_precision_percent: 100,
      hallucinations: 0,
      composite_score: 99.3,
    },
    {
      run_id: 'run-002',
      suite: 'scenarios',
      status: 'failed',
      model_name: 'gemini-3.0-pro',
      model_family: 'gemini',
      total_scenarios: 2,
      completion_rate_percent: 80,
      policy_compliance_percent: 85,
      tool_precision_percent: 75,
      hallucinations: 2,
      composite_score: 67.0,
    },
  ],
  run_deltas: [
    {
      run_id: 'run-002',
      baseline_run_id: 'run-001',
      composite_score_delta: -32.3,
      completion_rate_delta: -18.0,
      policy_compliance_delta: -15.0,
      tool_precision_delta: -25.0,
      hallucinations_delta: 2,
    },
  ],
  tier_deltas: [
    {
      run_id: 'run-002',
      baseline_run_id: 'run-001',
      tier: 1,
      completion_rate_delta: -10,
      policy_compliance_delta: -8,
      tool_precision_delta: -12,
      hallucinations_delta: 1,
    },
  ],
  scenario_deltas: [
    {
      run_id: 'run-002',
      baseline_run_id: 'run-001',
      scenario_id: 'tier1_author_search',
      completion_delta: -10,
      policy_compliance_delta: -10,
      tool_precision_delta: -20,
      hallucinations_delta: 1,
    },
  ],
};

async function setStoredUser(page: import('@playwright/test').Page, user: StoredUser): Promise<void> {
  await page.addInitScript((storedUser) => {
    localStorage.setItem('ai_librarian_current_user', JSON.stringify(storedUser));
  }, user);
}

function acceptSwitchPrompt(page: import('@playwright/test').Page, choice: 'fresh' | 'keep' = 'fresh'): void {
  page.once('dialog', async (dialog) => {
    await dialog.accept(choice);
  });
}

async function mockRunApis(page: import('@playwright/test').Page): Promise<void> {
  await page.route('**://localhost:8000/benchmark/runs', (route) => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ runs: RUNS, total: RUNS.length }),
      });
    }
    return route.continue();
  });

  await page.route('**://localhost:8000/benchmark/leaderboard**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(LEADERBOARD),
    }),
  );

  await page.route('**://localhost:8000/benchmark/compare', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(COMPARISON),
    }),
  );
}

test.describe('Analytics and comparison flows', () => {
  test('analytics page renders for patron', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockRunApis(page);

    await page.goto('/#/analytics');

    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible();
    await expect(page.getByText('Run Comparison Workbench')).toBeVisible();
    await expect(page.locator('.runs-row .col-model').first()).toHaveText('gemini-3.0-flash');
  });

  test('runs page compare action deep-links into analytics', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await mockRunApis(page);

    await page.goto('/#/runs');

    const checkboxes = page.locator('.table-row input[type="checkbox"]');
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();
    await page.getByRole('button', { name: 'Compare in Analytics' }).click();

    await page.waitForURL('**/#/analytics**');
    await expect(page).toHaveURL(/runs=run-001,run-002/);
  });

  test('analytics deep-link preloads selected runs and compares', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await mockRunApis(page);

    await page.goto('/#/analytics?runs=run-001,run-002');

    await expect(page.locator('.runs-row input[type="checkbox"]:checked')).toHaveCount(2);
    await page.getByRole('button', { name: 'Compare Selected Runs' }).click();

    await expect(page.getByText('Comparison Results')).toBeVisible();
    const comparisonPanel = page.locator('section.panel').filter({ hasText: 'Comparison Results' });
    const runRows = comparisonPanel.locator('.result-table').first().locator('.result-row');
    await expect(runRows.nth(0)).toContainText('run-001');
    await expect(runRows.nth(1)).toContainText('run-002');
  });

  test('leaderboard order is rendered with rank 1 first', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockRunApis(page);

    await page.goto('/#/analytics');

    await expect(page.getByText('Leaderboard')).toBeVisible();
    const firstLeaderboardRow = page.locator('.panel').nth(2).locator('.result-row').first();
    await expect(firstLeaderboardRow).toContainText('1');
    await expect(firstLeaderboardRow).toContainText('gemini-3.0-flash');
  });

  test('top-bar quick patron switch updates active persona and staff nav', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockRunApis(page);

    await page.route('**://localhost:8002/patrons', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'patron-001',
            barcode: 'HAN-P-001',
            name: 'Trunsworth Greyvale',
            email: 't.greyvale@pachydon.edu',
            phone: '555-0101',
            category: 'adult',
            checkout_limit: 10,
            hold_limit: 10,
            blocked: false,
            block_reason: null,
          },
          {
            id: 'patron-003',
            barcode: 'HAN-P-003',
            name: 'Marcus Tuskwell',
            email: 'm.tuskwell@greyhall.edu',
            phone: '555-0103',
            category: 'staff',
            checkout_limit: 25,
            hold_limit: 25,
            blocked: false,
            block_reason: null,
          },
        ]),
      }),
    );

    await page.goto('/#/home');

    await expect(page.getByRole('link', { name: 'Patrons' })).toHaveCount(0);
    acceptSwitchPrompt(page, 'fresh');
    await page.selectOption('#quick-patron-select', 'patron-003');

    await expect(page.locator('.user-profile .name')).toHaveText('Marcus Tuskwell');
    await expect(page.getByRole('link', { name: 'Patrons' })).toBeVisible();
  });
});
