import { expect, test } from '@playwright/test';
import { loginAsListener, pauseForVideo } from './helpers';

test('collaborative jam creation, swipe voting, queue inspection, skip consensus, and closing', async ({
  page,
}) => {
  await loginAsListener(page);

  await page.locator('aside.sidebar nav button', { hasText: 'Jams' }).click();
  await expect(page).toHaveURL(/\/jams$/);
  await pauseForVideo(page);

  // Create a collaborative Jam room with threshold 1 so skip consensus advances immediately.
  await page.locator('.jam-banner button', { hasText: 'Criar uma Jam' }).click();
  await expect(
    page.locator('section.modal h2', { hasText: 'O som fica melhor junto.' }),
  ).toBeVisible();

  await page.locator('section.modal input[name="roomName"]').fill('Pond E2E Ao Vivo');
  await page.locator('section.modal input[name="hours"]').fill('1');
  await page.locator('section.modal input[name="minutes"]').fill('30');
  await page.locator('section.modal input[name="threshold"]').fill('1');
  await pauseForVideo(page);

  const createJamResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/jams') && res.status() === 201,
  );
  const deckLoadResponse = page.waitForResponse(
    (res) => res.url().includes('/deck') && res.status() === 200,
  );
  await page.locator('section.modal button[type="submit"]').click();
  await Promise.all([createJamResponse, deckLoadResponse]);

  await expect(page.locator('.jam-swipe-workspace')).toBeVisible();
  await expect(page.locator('.jam-swipe-header .eyebrow')).toHaveText('Pond E2E Ao Vivo');
  await expect(page.locator('.room-code-pill')).toHaveText(/\d{6}/);
  await pauseForVideo(page);

  // Vote on Jam deck tracks (first becomes active track, second and third populate queue).
  const vote1 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await page.getByRole('button', { name: 'Curtir música', exact: true }).click();
  await vote1;
  await pauseForVideo(page);

  const vote2 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await page.getByRole('button', { name: 'Supercurtir música', exact: true }).click();
  await vote2;
  await expect(page.locator('.superlikes-quota')).toContainText('1/');
  await pauseForVideo(page);

  const vote3 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await page.getByRole('button', { name: 'Curtir música', exact: true }).click();
  await vote3;
  await pauseForVideo(page);

  // Switch to Room & Queue overview, vote to skip current track, and close Jam.
  await page.locator('.jam-view-tabs button', { hasText: 'Fila & Sala' }).click();
  await expect(page.locator('.jam-room')).toBeVisible();
  await expect(page.locator('.jam-room .live-label')).toHaveText('AO VIVO');
  await pauseForVideo(page, 500);

  const skipResponse = page.waitForResponse(
    (res) => res.url().includes('/skip-vote') && res.status() === 200,
  );
  await page.getByRole('button', { name: /Votar para pular/i }).click();
  await skipResponse;
  await pauseForVideo(page);

  const closeResponse = page.waitForResponse(
    (res) => res.url().includes('/close') && res.status() === 200,
  );
  await page.getByRole('button', { name: 'Encerrar Jam' }).click();
  await closeResponse;

  await expect(page.locator('.join-panel')).toBeVisible();
  await pauseForVideo(page, 450);
});
