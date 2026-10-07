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

test.describe('Assistant scenario click-to-run', () => {
  test('clicking a scenario starts benchmark run, replays script, and streams live audit events', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });

    let runStatusPollCount = 0;
    let createRunPayload: Record<string, unknown> | null = null;

    await page.route('**://localhost:800*/health', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
    );
    await page.route('**://localhost:8002/patrons', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'patron-001', name: 'Trunsworth Greyvale', category: 'ADULT' },
          { id: 'patron-003', name: 'Marcus Tuskwell', category: 'STAFF' },
        ]),
      }),
    );
    await page.route('**://localhost:8000/benchmark/report', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"not found"}' }),
    );
    await page.route('**://localhost:8000/benchmark/scenarios', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          manifest_version: '1.4',
          suite: 'v1_scenarios',
          generated_at: '2026-02-10T00:00:00Z',
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
            tier1_author_search: [
              'Do you have any books by Maren Greyhorn?',
            ],
          },
        }),
      }),
    );
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        message?: string;
        active_patron?: { id?: string; name?: string; role?: string };
      };
      const message = payload.message ?? '';
      expect(payload.active_patron?.id).toBe('patron-003');
      expect(payload.active_patron?.name).toBe('Marcus Tuskwell');
      expect(payload.active_patron?.role).toBe('staff');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: `ACK: ${message}`,
          session_id: 'assistant-scenario-session',
          bound_patron_id: 'patron-003',
          session_rebound: false,
        }),
      });
    });
    await page.route('**://localhost:8000/benchmark/runs', async (route) => {
      if (route.request().method() !== 'POST') {
        return route.continue();
      }
      createRunPayload = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-assistant-001',
          status: 'queued',
          artifact_dir: '/tmp/runs/run-assistant-001',
          model_name: 'gemini-3.0-flash',
          model_family: 'gemini',
          scenario_ids: ['tier1_author_search'],
          trigger_source: 'assistant_card',
          actor_patron_id: 'patron-003',
        }),
      });
    });
    await page.route('**://localhost:8000/benchmark/runs/run-assistant-001', (route) => {
      runStatusPollCount += 1;
      const status = runStatusPollCount < 2 ? 'running' : 'passed';
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-assistant-001',
          suite: 'scenarios',
          status,
          started_at: '2026-02-10T00:00:00Z',
          completed_at: status === 'passed' ? '2026-02-10T00:00:02Z' : null,
          artifact_dir: '/tmp/runs/run-assistant-001',
          report_path: status === 'passed' ? '/tmp/runs/run-assistant-001/benchmark-report.json' : null,
          trace_path: '/tmp/runs/run-assistant-001/benchmark-trace.jsonl',
          artifact_paths: [],
          error_message: null,
          scenario_ids: ['tier1_author_search'],
          trigger_source: 'assistant_card',
          model_name: 'gemini-3.0-flash',
          model_family: 'gemini',
          actor_patron_id: 'patron-003',
        }),
      });
    });
    await page.route('**://localhost:8000/benchmark/runs/run-assistant-001/trace', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            trace_id: 'trace-assistant-001',
            run_id: 'run-assistant-001',
            scenario_id: null,
            event_type: 'benchmark_run_start',
            source: 'benchmark_runner',
            timestamp: '2026-02-10T00:00:00Z',
            payload: { suite: 'scenarios' },
          },
          {
            trace_id: 'trace-assistant-001',
            run_id: 'run-assistant-001',
            scenario_id: 'tier1_author_search',
            event_type: 'scenario_step_start',
            source: 'benchmark_runner',
            timestamp: '2026-02-10T00:00:01Z',
            payload: {
              step_id: 'tool_execution',
              title: 'Execute Tool Calls',
              description: 'Run catalog tool calls.',
              phase: 'tools',
            },
          },
          {
            trace_id: 'trace-assistant-001',
            run_id: 'run-assistant-001',
            scenario_id: 'tier1_author_search',
            event_type: 'tool_call',
            source: 'catalog_tools',
            timestamp: '2026-02-10T00:00:01Z',
            payload: {
              tool: 'catalog.search_books',
              phase: 'start',
              status: 'running',
              call_id: 'call-001',
              input: { author: 'Maren Greyhorn' },
            },
          },
        ]),
      }),
    );

    await page.goto('/#/chat');

    const input = page.locator('input[name="userInput"]');
    await input.fill('temporary prefill');
    await input.press('Enter');
    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'temporary prefill' }),
    ).toBeVisible();

    await page.getByRole('button', { name: /Tier1 Author Search/i }).click();

    await expect.poll(() => createRunPayload).not.toBeNull();
    expect(createRunPayload).toMatchObject({
      suite: 'scenarios',
      scenario_ids: ['tier1_author_search'],
      trigger_source: 'assistant_card',
      actor_patron_id: 'patron-003',
    });

    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'temporary prefill' }),
    ).toHaveCount(0);
    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'Do you have any books by Maren Greyhorn?' }),
    ).toBeVisible();
    await expect(page.getByText('ACK: Do you have any books by Maren Greyhorn?')).toBeVisible();

    await expect(page.getByText('run-assistant-001')).toBeVisible();
    await expect(page.getByText('Tool Start: catalog.search_books')).toBeVisible();

    const runLink = page.getByRole('link', { name: 'Open Run Detail' });
    await expect(runLink).toBeVisible();
    await expect(runLink).toHaveAttribute('href', /runs\/run-assistant-001/);
  });
});
