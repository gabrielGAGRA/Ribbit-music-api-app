import { expect, test } from '@playwright/test';
import { pauseForVideo } from './helpers';

test('onboarding registration with age validation, genre filters, discovery swipes, and collections', async ({
  page,
}) => {
  await page.goto('/discover');
  await expect(page.locator('.auth-card')).toBeVisible();
  await pauseForVideo(page);

  await page.locator('.auth-switch button').click();
  await expect(page.locator('input[name="name"]')).toBeVisible();

  // Verify underage guard rejects birth date under 18 years old.
  await page.locator('input[name="birthDate"]').fill('2012-05-15');
  await expect(page.locator('.auth-field-error')).toContainText(
    'Cadastro direto permitido apenas para maiores de 18 anos.',
  );
  await expect(page.locator('button[type="submit"]')).toBeDisabled();
  await pauseForVideo(page);

  // Fill valid adult registration on Individual plan (enables blocked-genre filter).
  const uniqueEmail = `e2e.onboarding.${Date.now()}@ribbit.example.com`;
  await page.locator('input[name="name"]').fill('Beatriz E2E');
  await page.locator('input[name="email"]').fill(uniqueEmail);
  await page.locator('input[name="birthDate"]').fill('1998-05-20');
  await page.locator('select[name="planId"]').selectOption('2');
  await page.locator('input[name="password"]').fill('RibbitE2E2026!');
  await page.locator('input[name="confirmPassword"]').fill('RibbitE2E2026!');
  await page.locator('.auth-check input[type="checkbox"]').check();
  await pauseForVideo(page);

  const discoveryReady = page.waitForResponse(
    (response) =>
      response.url().includes('/api/discovery/next') && response.status() === 200,
  );
  await page.locator('button[type="submit"]').click();
  await discoveryReady;

  await expect(page.locator('aside.sidebar')).toBeVisible();
  await expect(page.locator('.discovery-card')).toBeVisible();
  await pauseForVideo(page, 500);

  // Configure favorite and blocked genres in the frequency modal.
  await page.locator('button.filter-button', { hasText: 'Ajustar filtros' }).click();
  await expect(
    page.locator('section.modal h2', { hasText: 'Qual é a sua frequência?' }),
  ).toBeVisible();
  await page
    .locator('section.modal .genre-options')
    .nth(0)
    .getByRole('button', { name: 'Rock', exact: true })
    .click();
  const blockedUpdate = page.waitForResponse(
    (response) =>
      response.url().includes('/api/profile/blocked-genres') &&
      response.request().method() === 'PUT' &&
      response.status() === 200,
  );
  await page
    .locator('section.modal .genre-options')
    .nth(1)
    .getByRole('button', { name: 'Hip-hop', exact: true })
    .click();
  await blockedUpdate;
  await pauseForVideo(page);

  await page.getByRole('button', { name: /Salvar preferências/i }).click();
  await expect(page.locator('section.modal')).toBeHidden();
  await pauseForVideo(page);

  // Perform three distinct discovery swipes: like, love (superlike), reject.
  const trackHeading = page.locator('.discovery-card .track-heading h2');

  const likedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(likedTitle.length).toBeGreaterThan(0);
  const likeNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await page.getByRole('button', { name: 'Curtir música' }).click();
  await likeNext;
  await expect(trackHeading).not.toHaveText(likedTitle);
  await pauseForVideo(page);

  const lovedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(lovedTitle.length).toBeGreaterThan(0);
  const loveNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await page.getByRole('button', { name: 'Amar música' }).click();
  await loveNext;
  await expect(trackHeading).not.toHaveText(lovedTitle);
  await pauseForVideo(page);

  const rejectedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(rejectedTitle.length).toBeGreaterThan(0);
  const rejectNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await page.getByRole('button', { name: 'Rejeitar música' }).click();
  await rejectNext;
  await pauseForVideo(page);

  // Verify the collections reflect all three interactions.
  await page.locator('aside.sidebar button', { hasText: 'Músicas curtidas' }).click();
  await expect(page).toHaveURL(/\/likes$/);
  await expect(page.locator('.collection-list')).toContainText(likedTitle);
  await expect(page.locator('.collection-list')).toContainText(lovedTitle);
  await pauseForVideo(page);

  await page.locator('aside.sidebar button', { hasText: 'Minhas amadas' }).click();
  await expect(page).toHaveURL(/\/loved$/);
  await expect(page.locator('.collection-list')).toContainText(lovedTitle);
  await pauseForVideo(page);

  await page.locator('aside.sidebar button', { hasText: 'Rejeitadas' }).click();
  await expect(page).toHaveURL(/\/rejected$/);
  await expect(page.locator('.collection-list')).toContainText(rejectedTitle);
  await pauseForVideo(page, 500);
});
