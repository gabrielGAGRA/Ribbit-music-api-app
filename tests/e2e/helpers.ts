import { expect, type Page } from '@playwright/test';

export const DEMO_USER_EMAIL = 'usuario@ribbit.example.com';
export const DEMO_USER_PASSWORD = 'RibbitUser2026!';

/** Pauses briefly so state transitions remain readable in recorded E2E demonstration videos. */
export async function pauseForVideo(page: Page, ms = 450): Promise<void> {
  await page.waitForTimeout(ms);
}

/** Authenticates a listener account via the UI login form and waits for discovery hydration. */
export async function loginAsListener(
  page: Page,
  email = DEMO_USER_EMAIL,
  password = DEMO_USER_PASSWORD,
): Promise<void> {
  await page.goto('/discover');
  await expect(page.locator('input[name="email"]')).toBeVisible();

  const discoveryNextPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/discovery/next') && response.status() === 200,
  );
  const playlistsPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/playlists') && response.status() === 200,
  );

  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();

  await expect(page.locator('aside.sidebar')).toBeVisible();
  await Promise.all([discoveryNextPromise, playlistsPromise]);
  await expect(page.locator('.discovery-card')).toBeVisible();
  await pauseForVideo(page, 400);
}
