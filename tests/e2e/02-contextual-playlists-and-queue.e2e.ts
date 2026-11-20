import { expect, humanClick, humanFill, loginAsListener, pauseForVideo, test } from './helpers';

test('contextual playlist creation, adding discovery track, and in-playlist swipe deck', async ({
  page,
}) => {
  const runSuffix = Date.now();
  const playlistName = `Sessão E2E Pop ${runSuffix}`;

  await loginAsListener(page);

  // Navigate to Playlists Studio and create a contextual playlist.
  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Playlists' }));
  await expect(page).toHaveURL(/\/playlists$/);
  await pauseForVideo(page, 850);

  await humanClick(page, page.locator('.feature-banner button', { hasText: 'Criar playlist' }));
  await expect(
    page.locator('section.modal h2', { hasText: 'Uma playlist, do seu jeito.' }),
  ).toBeVisible();

  await humanClick(
    page,
    page.locator('section.modal .genre-options button', { hasText: 'Duração' }),
  );
  await humanFill(page, page.locator('section.modal input[name="name"]'), playlistName);
  await humanClick(page, page.locator('section.modal select[name="genre"]'), 150);
  await page.locator('section.modal select[name="genre"]').selectOption('Pop');
  await humanFill(page, page.locator('section.modal input[name="duration"]'), '45');
  await pauseForVideo(page, 700);

  const createPlaylistResponse = page.waitForResponse(
    (res) => res.url().includes('/api/playlists/deck') && res.status() === 201,
  );
  await humanClick(page, page.getByRole('button', { name: /Criar minha playlist/i }), 200);
  await createPlaylistResponse;

  await expect(
    page.locator('.playlist-grid .playlist-card', { hasText: playlistName }),
  ).toBeVisible();
  await pauseForVideo(page, 950);

  // Return to Discovery and add current track to the created playlist.
  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Descoberta' }));
  await expect(page.locator('.discovery-card')).toBeVisible();
  const discoveryTitle =
    (await page.locator('.discovery-card .track-heading h2').textContent())?.trim() ?? '';

  await humanClick(page, page.getByRole('button', { name: 'Adicionar à playlist' }));
  await expect(page.locator('section.modal')).toBeVisible();

  const swipeAddResponse = page.waitForResponse(
    (res) => res.url().includes('/swipe-add') && res.status() === 200,
  );
  await humanClick(
    page,
    page.locator('section.modal button.playlist-choice', { hasText: playlistName }),
    200,
  );
  await swipeAddResponse;
  await expect(page.locator('section.modal')).toBeHidden();
  await pauseForVideo(page, 850);

  // Open playlist details, verify the added track, and use the in-playlist contextual swipe deck.
  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Playlists' }));
  await humanClick(page, page.locator('.playlist-grid .playlist-card', { hasText: playlistName }));
  await expect(page.locator('h1.hero-title', { hasText: playlistName })).toBeVisible();
  await expect(page.locator('.playlist-tracks-section')).toContainText(discoveryTitle);
  await pauseForVideo(page, 900);

  await humanClick(page, page.getByRole('button', { name: 'Adicionar com Swipe' }), 350);
  await expect(page.locator('.playlist-swipe-card')).toBeVisible();
  await pauseForVideo(page, 850);

  const deckTitle =
    (await page.locator('.playlist-swipe-card .track-heading h2').textContent())?.trim() ?? '';
  const deckAddResponse = page.waitForResponse(
    (res) => res.url().includes('/swipe-add') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: 'Adicionar à playlist' }), 250);
  await deckAddResponse;
  await pauseForVideo(page, 850);

  await humanClick(page, page.getByRole('button', { name: 'Passar música' }), 650);

  await humanClick(page, page.getByRole('button', { name: 'Ver Faixas Salvas', exact: true }));
  await expect(page.locator('.playlist-tracks-section')).toContainText(discoveryTitle);
  if (deckTitle) {
    await expect(page.locator('.playlist-tracks-section')).toContainText(deckTitle);
  }
  await pauseForVideo(page, 1000);

  await humanClick(page, page.getByRole('button', { name: /Voltar para Minhas Playlists/i }));
  await expect(
    page.locator('.playlist-grid .playlist-card', { hasText: playlistName }),
  ).toBeVisible();
  await pauseForVideo(page, 900);
});
