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

function acceptSwitchPrompt(page: import('@playwright/test').Page, choice: 'fresh' | 'keep'): void {
  page.once('dialog', async (dialog) => {
    await dialog.accept(choice);
  });
}

async function mockChatShellApis(page: import('@playwright/test').Page): Promise<void> {
  await page.route('**://localhost:800*/health', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"healthy"}' }),
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
        scenarios: [],
        scripts: {},
      }),
    }),
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
}

test.describe('Chat identity binding and patron switch policy', () => {
  test('chat payload includes active patron context', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockChatShellApis(page);

    const requests: Array<{
      message?: string;
      session_id?: string;
      active_patron?: { id?: string; name?: string; role?: string };
    }> = [];
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        message?: string;
        session_id?: string;
        active_patron?: { id?: string; name?: string; role?: string };
      };
      requests.push(payload);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: `ACK: ${payload.message ?? ''}`,
          session_id: 'chat-identity-001',
          bound_patron_id: payload.active_patron?.id ?? null,
          session_rebound: false,
        }),
      });
    });

    await page.goto('/#/chat');
    const input = page.locator('input[name="userInput"]');
    await input.fill('What books do I have checked out?');
    await input.press('Enter');

    await expect.poll(() => requests.length).toBe(1);
    expect(requests[0].active_patron?.id).toBe('patron-001');
    expect(requests[0].active_patron?.name).toBe('Trunsworth Greyvale');
    expect(requests[0].active_patron?.role).toBe('patron');
  });

  test('switch keep transcript preserves messages but rotates backend session', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockChatShellApis(page);

    const requests: Array<{
      message?: string;
      session_id?: string;
      active_patron?: { id?: string; name?: string; role?: string };
    }> = [];
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        message?: string;
        session_id?: string;
        active_patron?: { id?: string; name?: string; role?: string };
      };
      requests.push(payload);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: `ACK: ${payload.message ?? ''}`,
          session_id: `chat-identity-${requests.length}`,
          bound_patron_id: payload.active_patron?.id ?? null,
          session_rebound: false,
        }),
      });
    });

    await page.goto('/#/chat');
    const input = page.locator('input[name="userInput"]');
    await input.fill('First account question');
    await input.press('Enter');
    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'First account question' }),
    ).toHaveCount(1);

    acceptSwitchPrompt(page, 'keep');
    await page.selectOption('#quick-patron-select', 'patron-003');

    await expect(page.locator('.user-profile .name')).toHaveText('Marcus Tuskwell');
    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'First account question' }),
    ).toHaveCount(1);

    await input.fill('Second account question');
    await input.press('Enter');

    await expect.poll(() => requests.length).toBe(2);
    expect(requests[0].active_patron?.id).toBe('patron-001');
    expect(requests[0].session_id).toBeUndefined();
    expect(requests[1].active_patron?.id).toBe('patron-003');
    expect(requests[1].session_id).toBeUndefined();
  });

  test('switch start fresh clears transcript and starts a fresh chat session', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockChatShellApis(page);

    const requests: Array<{
      message?: string;
      session_id?: string;
      active_patron?: { id?: string; name?: string; role?: string };
    }> = [];
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        message?: string;
        session_id?: string;
        active_patron?: { id?: string; name?: string; role?: string };
      };
      requests.push(payload);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: `ACK: ${payload.message ?? ''}`,
          session_id: `chat-fresh-${requests.length}`,
          bound_patron_id: payload.active_patron?.id ?? null,
          session_rebound: false,
        }),
      });
    });

    await page.goto('/#/chat');
    const input = page.locator('input[name="userInput"]');
    await input.fill('Transient message');
    await input.press('Enter');
    await expect(
      page.locator('.msg.msg-user .msg-text', { hasText: 'Transient message' }),
    ).toHaveCount(1);

    acceptSwitchPrompt(page, 'fresh');
    await page.selectOption('#quick-patron-select', 'patron-003');

    await expect(page.locator('.msg.msg-user .msg-text', { hasText: 'Transient message' })).toHaveCount(0);

    await input.fill('New profile question');
    await input.press('Enter');

    await expect.poll(() => requests.length).toBe(2);
    expect(requests[1].active_patron?.id).toBe('patron-003');
    expect(requests[1].session_id).toBeUndefined();
  });
});
