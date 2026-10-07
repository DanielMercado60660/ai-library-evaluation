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

async function mockScenarioCatalog(page: import('@playwright/test').Page): Promise<void> {
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
}

test.describe('Chat route smoke', () => {
  test('loads home shell via default route', async ({ page }) => {
    // Mock backend calls to prevent errors
    await mockScenarioCatalog(page);
    await page.route('**://localhost:8000/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404 }),
    );

    await page.goto('/');

    // Should redirect to /#/home and show the landing page
    await page.waitForURL('**/#/home');
    await expect(page.getByText('Welcome to the Pachyderm Archive')).toBeVisible();
    await expect(page.getByRole('link', { name: /Assistant/ })).toBeVisible();
  });

  test('sidebar shows Assistant and Benchmarks links', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await page.route('**://localhost:8000/**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    );

    await page.goto('/#/chat');

    await expect(page.getByRole('link', { name: /Assistant/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Benchmarks/ })).toBeVisible();
  });

  test('non-staff can access analytics but not staff-only patron directory', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockScenarioCatalog(page);
    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404 }),
    );
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

    await page.goto('/#/chat');

    await expect(page.getByRole('link', { name: /Benchmarks/ })).toBeVisible();

    await page.goto('/#/runs');
    await page.waitForURL('**/#/runs');
    await expect(page.getByRole('heading', { name: 'Benchmark Runs' })).toBeVisible();

    await page.goto('/#/patrons');
    await page.waitForURL('**/#/access-denied**');
    await expect(page.getByRole('heading', { name: 'Access Restricted' })).toBeVisible();
  });

  test('submits a chat prompt and renders assistant response', async ({ page }) => {
    await mockScenarioCatalog(page);
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        message?: string;
        active_patron?: { id?: string; name?: string; role?: string };
      };
      expect(payload.message).toBe('Find books by Maren Greyhorn');
      expect(payload.active_patron?.id).toBe('patron-001');
      expect(payload.active_patron?.name).toBe('Trunsworth Greyvale');
      expect(payload.active_patron?.role).toBe('patron');

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response:
            'I found 2 match(es): The Tragedy of Lorde Tuskar, The Fall of Duchess Ivoryn',
          session_id: 'e2e-session-001',
          bound_patron_id: 'patron-001',
          session_rebound: false,
        }),
      });
    });
    await page.route('**://localhost:8000/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404 }),
    );

    await page.goto('/#/chat');

    const input = page.locator('input[name="userInput"]');
    await input.fill('Find books by Maren Greyhorn');
    await input.press('Enter');

    await expect(page.getByText('Find books by Maren Greyhorn')).toBeVisible();
    await expect(
      page.getByText(
        'I found 2 match(es): The Tragedy of Lorde Tuskar, The Fall of Duchess Ivoryn',
      ),
    ).toBeVisible();
  });

  test('live scenario run overrides empty forensic ledger state when report is unavailable', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await mockScenarioCatalog(page);
    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' }),
    );
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        active_patron?: { id?: string; name?: string; role?: string };
      };
      expect(payload.active_patron?.id).toBe('patron-003');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: 'Script reply',
          session_id: 'chat-smoke-live-run',
          bound_patron_id: 'patron-003',
          session_rebound: false,
        }),
      });
    });
    await page.route('**://localhost:8000/benchmark/runs', async (route) => {
      const payload = route.request().postDataJSON() as { actor_patron_id?: string };
      expect(payload.actor_patron_id).toBe('patron-003');
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-smoke-live-001',
          status: 'queued',
          artifact_dir: '/tmp/runs/run-smoke-live-001',
          model_name: 'gemini-3.0-flash',
          model_family: 'gemini',
          scenario_ids: ['tier1_author_search'],
          trigger_source: 'assistant_card',
          actor_patron_id: 'patron-003',
        }),
      });
    });
    await page.route('**://localhost:8000/benchmark/runs/run-smoke-live-001', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-smoke-live-001',
          suite: 'scenarios',
          status: 'running',
          started_at: '2026-02-10T00:00:00Z',
          completed_at: null,
          artifact_dir: '/tmp/runs/run-smoke-live-001',
          report_path: null,
          trace_path: '/tmp/runs/run-smoke-live-001/benchmark-trace.jsonl',
          artifact_paths: [],
          error_message: null,
          scenario_ids: ['tier1_author_search'],
          trigger_source: 'assistant_card',
          model_name: 'gemini-3.0-flash',
          model_family: 'gemini',
          actor_patron_id: 'patron-003',
        }),
      }),
    );
    await page.route('**://localhost:8000/benchmark/runs/run-smoke-live-001/trace', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            trace_id: 'trace-smoke-live',
            run_id: 'run-smoke-live-001',
            scenario_id: null,
            event_type: 'benchmark_run_start',
            source: 'benchmark_runner',
            timestamp: '2026-02-10T00:00:00Z',
            payload: { suite: 'scenarios' },
          },
        ]),
      }),
    );

    await page.goto('/#/chat');
    await expect(page.getByText('Load a benchmark report to view the audit stream.')).toBeVisible();

    await page.getByRole('button', { name: /Tier1 Author Search/i }).click();

    await expect(page.getByText('run-smoke-live-001')).toBeVisible();
    await expect(page.getByText('Benchmark Run Started')).toBeVisible();
    await expect(page.getByText('Load a benchmark report to view the audit stream.')).toHaveCount(0);
  });

  test('uses local fallback scenarios when agents scenario endpoint is unavailable', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await page.route('**://localhost:8000/benchmark/scenarios', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"offline"}' }),
    );
    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404 }),
    );

    await page.goto('/#/chat');

    await expect(page.getByRole('button', { name: /Tier1 Author Search/i })).toBeVisible();
    await expect(page.getByText('No benchmark scenarios found. Verify agents scenario manifest is available.')).toHaveCount(0);
  });

  test('submits a chat prompt against live backend (optional)', async ({ page, request }) => {
    test.skip(!process.env.E2E_LIVE_BACKEND, 'Set E2E_LIVE_BACKEND=1 to run live chat smoke.');

    let agentsHealthy = false;
    try {
      const health = await request.get('http://127.0.0.1:8000/health', { timeout: 2000 });
      agentsHealthy = health.ok();
    } catch {
      agentsHealthy = false;
    }
    test.skip(!agentsHealthy, 'Agents API is not running on http://127.0.0.1:8000.');

    await page.goto('/#/chat');

    const input = page.locator('input[name="userInput"]');
    await input.fill('Find books by Maren Greyhorn');
    await input.press('Enter');

    await expect(page.getByText('Find books by Maren Greyhorn')).toBeVisible();
    const assistantReply = page.locator('.msg.msg-agent .msg-text').last();
    await expect(assistantReply).toBeVisible();
    await expect(assistantReply).not.toHaveText(/Sorry, I encountered an error/i);
  });
});
