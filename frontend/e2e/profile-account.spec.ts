import { expect, test } from '@playwright/test';

interface StoredUser {
  id: string;
  name: string;
  role: 'patron' | 'staff';
  avatarInitials: string;
}

const PATRONS = [
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
  {
    id: 'patron-008',
    barcode: 'HAN-P-008',
    name: 'Keeper Tuskmere',
    email: 'k.tuskmere@archive.hml',
    phone: '555-0108',
    category: 'staff',
    checkout_limit: 25,
    hold_limit: 25,
    blocked: false,
    block_reason: null,
  },
];

const SUMMARIES: Record<string, unknown> = {
  'patron-001': {
    patron: PATRONS[0],
    checkouts: [],
    holds: [],
    fines: [],
    total_fines_owed: 0,
  },
  'patron-003': {
    patron: PATRONS[1],
    checkouts: [],
    holds: [],
    fines: [],
    total_fines_owed: 0,
  },
  'patron-008': {
    patron: PATRONS[2],
    checkouts: [],
    holds: [],
    fines: [],
    total_fines_owed: 0,
  },
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

async function mockProfileApis(page: import('@playwright/test').Page): Promise<void> {
  await page.route('**://localhost:8002/patrons', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PATRONS),
    }),
  );

  await page.route('**://localhost:8002/patrons/*/summary', (route) => {
    const url = route.request().url();
    const patronId = url.split('/patrons/')[1]?.split('/summary')[0] ?? '';
    const summary = SUMMARIES[patronId];

    if (!summary) {
      return route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: `Patron ${patronId} not found` }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(summary),
    });
  });

  await page.route('**://localhost:8003/requests**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    }),
  );
}

test.describe('My Account access and profile flows', () => {
  test('staff can switch between patron accounts', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-003',
      name: 'Marcus Tuskwell',
      role: 'staff',
      avatarInitials: 'MT',
    });
    await mockProfileApis(page);

    await page.goto('/#/profile');

    await expect(page.locator('#patron-switcher-select')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Marcus Tuskwell' })).toBeVisible();

    acceptSwitchPrompt(page, 'fresh');
    await page.selectOption('#patron-switcher-select', 'patron-001');

    await page.waitForURL('**/#/profile/patron-001');
    await expect(page.getByRole('heading', { name: 'Trunsworth Greyvale' })).toBeVisible();
  });

  test('profile notifications can be marked as read', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockProfileApis(page);

    await page.goto('/#/profile');

    await expect(page.getByRole('tab', { name: /Notifications \(1\)/ })).toBeVisible();
    await page.getByRole('tab', { name: /Notifications \(1\)/ }).click();
    await expect(page.getByText('Hold Available')).toBeVisible();

    await page.getByRole('button', { name: /Mark all as read/i }).click();
    await expect(page.getByRole('tab', { name: /Notifications \(0\)/ })).toBeVisible();
  });

  test('switching to a staff patron profile grants staff navigation', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockProfileApis(page);

    await page.goto('/#/profile/patron-003');

    await page.waitForURL('**/#/profile/patron-003');
    await expect(page.locator('#patron-switcher-select')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Marcus Tuskwell' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Patrons' })).toBeVisible();

    await page.getByRole('link', { name: 'Patrons' }).click();
    await page.waitForURL('**/#/patrons');
    await expect(page.getByRole('heading', { name: 'Patron Directory' })).toBeVisible();
  });

  test('switching active patron in My Account updates subsequent Assistant identity context', async ({ page }) => {
    await setStoredUser(page, {
      id: 'patron-001',
      name: 'Trunsworth Greyvale',
      role: 'patron',
      avatarInitials: 'TG',
    });
    await mockProfileApis(page);

    let capturedPatronId: string | null = null;
    await page.route('**://localhost:8000/chat', async (route) => {
      const payload = route.request().postDataJSON() as {
        active_patron?: { id?: string; role?: string };
        message?: string;
      };
      capturedPatronId = payload.active_patron?.id ?? null;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          response: `ACK: ${payload.message ?? ''}`,
          session_id: 'profile-switch-chat-session',
          bound_patron_id: payload.active_patron?.id ?? null,
          session_rebound: false,
        }),
      });
    });
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

    await page.goto('/#/profile');
    acceptSwitchPrompt(page, 'fresh');
    await page.selectOption('#patron-switcher-select', 'patron-003');
    await page.waitForURL('**/#/profile/patron-003');

    await page.goto('/#/chat');
    const input = page.locator('input[name="userInput"]');
    await input.fill('Who am I currently logged in as?');
    await input.press('Enter');

    await expect.poll(() => capturedPatronId).toBe('patron-003');
    await expect(page.getByText('ACK: Who am I currently logged in as?')).toBeVisible();
  });
});
