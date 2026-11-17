import { expect, test } from '@playwright/test';
import { loginAsListener, pauseForVideo } from './helpers';

test('contextual playlist creation, adding discovery track, and playback queue conversion', async ({
  page,
}) => {
  const runSuffix = Date.now();
  const playlistName = `Sessão E2E Pop ${runSuffix}`;
  const queuePlaylistName = `Fila E2E Salva ${runSuffix}`;

  await loginAsListener(page);

  // Navigate to Playlists Studio and create a contextual playlist.
  await page.locator('aside.sidebar nav button', { hasText: 'Playlists' }).click();
  await expect(page).toHaveURL(/\/playlists$/);
  await pauseForVideo(page);

  await page.locator('.feature-banner button', { hasText: 'Criar playlist' }).click();
  await expect(
    page.locator('section.modal h2', { hasText: 'Uma playlist, do seu jeito.' }),
  ).toBeVisible();

  await page.locator('section.modal .genre-options button', { hasText: 'Duração' }).click();
  await page.locator('section.modal input[name="name"]').fill(playlistName);
  await page.locator('section.modal select[name="genre"]').selectOption('Pop');
  await page.locator('section.modal input[name="duration"]').fill('45');
  await pauseForVideo(page);

  const createPlaylistResponse = page.waitForResponse(
    (res) => res.url().includes('/api/playlists/deck') && res.status() === 201,
  );
  await page.getByRole('button', { name: /Criar minha playlist/i }).click();
  await createPlaylistResponse;

  await expect(
    page.locator('.playlist-grid .playlist-card', { hasText: playlistName }),
  ).toBeVisible();
  await pauseForVideo(page);

  // Return to Discovery and add current track to the created playlist.
  await page.locator('aside.sidebar nav button', { hasText: 'Descoberta' }).click();
  await expect(page.locator('.discovery-card')).toBeVisible();
  const discoveryTitle =
    (await page.locator('.discovery-card .track-heading h2').textContent())?.trim() ?? '';

  await page.getByRole('button', { name: 'Adicionar à playlist' }).click();
  await expect(page.locator('section.modal')).toBeVisible();

  const swipeAddResponse = page.waitForResponse(
    (res) => res.url().includes('/swipe-add') && res.status() === 200,
  );
  await page
    .locator('section.modal button.playlist-choice', { hasText: playlistName })
    .click();
  await swipeAddResponse;
  await expect(page.locator('section.modal')).toBeHidden();
  await pauseForVideo(page);

  // Open playlist details and verify the added track appears.
  await page.locator('aside.sidebar nav button', { hasText: 'Playlists' }).click();
  await page.locator('.playlist-grid .playlist-card', { hasText: playlistName }).click();
  await expect(page.locator('h1.hero-title', { hasText: playlistName })).toBeVisible();
  await expect(page.locator('.playlist-tracks-section')).toContainText(discoveryTitle);
  await pauseForVideo(page, 500);

  await page.getByRole('button', { name: /Voltar para Minhas Playlists/i }).click();

  // Switch to Temporary Playback Queue tab, add tracks, inspect last queue, and save as playlist.
  await page.locator('.playlist-hub-tabs button', { hasText: 'Fila de Reprodução' }).click();
  await expect(page.locator('.queue-workspace')).toBeVisible();
  await pauseForVideo(page);

  await page.getByRole('button', { name: 'Adicionar música à fila' }).click();
  await pauseForVideo(page, 300);
  await page.getByRole('button', { name: 'Adicionar música à fila' }).click();
  await expect(page.locator('.current-queue .song-row')).toHaveCount(2);
  await pauseForVideo(page);

  await page.locator('button.view-all-queue-btn').click();
  await expect(page.locator('.last-queue-tracks-panel')).toBeVisible();
  await pauseForVideo(page);

  await page.getByRole('button', { name: /Salvar Fila como Playlist/i }).click();
  await page.locator('section.modal input[name="queueName"]').fill(queuePlaylistName);
  await page
    .locator('section.modal textarea[name="queueDescription"]')
    .fill('Gerada a partir da fila temporária.');

  const saveQueueResponse = page.waitForResponse(
    (res) => res.url().includes('/api/playlists/deck') && res.status() === 201,
  );
  await page.getByRole('button', { name: /Salvar na biblioteca/i }).click();
  await saveQueueResponse;

  await page.locator('.playlist-hub-tabs button', { hasText: 'Minhas Playlists' }).click();
  await expect(
    page.locator('.playlist-grid .playlist-card', { hasText: queuePlaylistName }),
  ).toBeVisible();
  await pauseForVideo(page, 500);
});
