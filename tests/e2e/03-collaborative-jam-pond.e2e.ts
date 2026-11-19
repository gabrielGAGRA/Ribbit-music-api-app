import { expect, humanClick, humanFill, loginAsListener, pauseForVideo, test } from './helpers';

test('collaborative jam creation, swipe voting, queue inspection, skip consensus, and closing', async ({
  page,
}) => {
  await loginAsListener(page);

  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Jams' }));
  await expect(page).toHaveURL(/\/jams$/);
  await pauseForVideo(page, 850);

  // Create a collaborative Jam room with threshold 1 so skip consensus advances immediately.
  await humanClick(page, page.locator('.jam-banner button', { hasText: 'Criar uma Jam' }));
  await expect(
    page.locator('section.modal h2', { hasText: 'O som fica melhor junto.' }),
  ).toBeVisible();

  await humanFill(page, page.locator('section.modal input[name="roomName"]'), 'Pond E2E Ao Vivo');
  await humanFill(page, page.locator('section.modal input[name="hours"]'), '1');
  await humanFill(page, page.locator('section.modal input[name="minutes"]'), '30');
  await humanFill(page, page.locator('section.modal input[name="threshold"]'), '1');
  await pauseForVideo(page, 700);

  const createJamResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/jams') && res.status() === 201,
  );
  const deckLoadResponse = page.waitForResponse(
    (res) => res.url().includes('/deck') && res.status() === 200,
  );
  await humanClick(page, page.locator('section.modal button[type="submit"]'), 200);
  await Promise.all([createJamResponse, deckLoadResponse]);

  await expect(page.locator('.jam-swipe-workspace')).toBeVisible();
  await expect(page.locator('.jam-swipe-header .eyebrow')).toHaveText('Pond E2E Ao Vivo');
  await expect(page.locator('.room-code-pill')).toHaveText(/\d{6}/);
  await pauseForVideo(page, 950);

  // Vote on Jam deck tracks (first becomes active track, second and third populate queue).
  const vote1 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: 'Curtir música', exact: true }), 250);
  await vote1;
  await pauseForVideo(page, 900);

  const vote2 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await humanClick(
    page,
    page.getByRole('button', { name: 'Supercurtir música', exact: true }),
    250,
  );
  await vote2;
  await expect(page.locator('.superlikes-quota')).toContainText('1/');
  await pauseForVideo(page, 900);

  const vote3 = page.waitForResponse(
    (res) => res.url().includes('/deck-vote') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: 'Curtir música', exact: true }), 250);
  await vote3;
  await pauseForVideo(page, 900);

  // Switch to Room & Queue overview, vote to skip current track, and close Jam.
  await humanClick(page, page.locator('.jam-view-tabs button', { hasText: 'Fila & Sala' }));
  await expect(page.locator('.jam-room')).toBeVisible();
  await expect(page.locator('.jam-room .live-label')).toHaveText('AO VIVO');
  await pauseForVideo(page, 1000);

  const skipResponse = page.waitForResponse(
    (res) => res.url().includes('/skip-vote') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: /Votar para pular/i }), 250);
  await skipResponse;
  await pauseForVideo(page, 950);

  const closeResponse = page.waitForResponse(
    (res) => res.url().includes('/close') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: 'Encerrar Jam' }), 250);
  await closeResponse;

  await expect(page.locator('.join-panel')).toBeVisible();
  await pauseForVideo(page, 1000);
});
