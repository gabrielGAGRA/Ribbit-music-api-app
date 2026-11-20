import { expect, humanClick, humanFill, loginAsListener, pauseForVideo, test } from './helpers';

test('catalog search with filters, track details, 5-star review lifecycle, and community feed', async ({
  page,
}) => {
  const reviewerEmail = `e2e.reviews.${Date.now()}@ribbit.example.com`;
  const reviewerPassword = 'RibbitE2E2026!';
  const registerRes = await page.request.post('/api/auth/register', {
    data: {
      email: reviewerEmail,
      password: reviewerPassword,
      display_name: 'Crítico E2E',
      birth_date: '1995-04-12',
      plan_id: 2,
    },
  });
  expect(registerRes.status()).toBe(201);

  await loginAsListener(page, reviewerEmail, reviewerPassword);

  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Comunidade' }));
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.locator('.community-reviews')).toBeVisible();
  await pauseForVideo(page, 850);

  // Open search filters modal and apply genre Pop.
  await humanClick(page, page.locator('button.search-filter-button'));
  await expect(page.locator('section.modal h2', { hasText: 'Filtrar sua busca' })).toBeVisible();
  await humanClick(
    page,
    page
      .locator('section.modal .genre-options')
      .getByRole('button', { name: 'Pop', exact: true }),
  );
  await pauseForVideo(page, 700);

  const filterSearchResponse = page.waitForResponse(
    (res) => res.url().includes('/api/tracks/search') && res.status() === 200,
  );
  await humanClick(page, page.getByRole('button', { name: /Aplicar filtros/i }), 200);
  await filterSearchResponse;

  // Search for Blinding Lights and inspect results.
  const searchResponse = page.waitForResponse(
    (res) =>
      res.url().includes('/api/tracks/search') &&
      res.url().includes('Blinding') &&
      res.status() === 200,
  );
  await humanFill(page, page.locator('.explore-search input'), 'Blinding', 200);
  await searchResponse;

  await expect(page.locator('.search-results')).toContainText('Blinding Lights');
  await pauseForVideo(page, 850);

  // Open track details modal, test review delete lifecycle, then publish a kept 5-star review.
  const reviewsLoaded = page.waitForResponse(
    (res) => res.url().includes('/api/reviews/track/') && res.status() === 200,
  );
  await humanClick(
    page,
    page.getByRole('button', { name: 'Ver detalhes de Blinding Lights' }),
    200,
  );
  await reviewsLoaded;
  await expect(page.locator('section.modal h2', { hasText: 'Blinding Lights' })).toBeVisible();
  await pauseForVideo(page, 700);

  await humanClick(page, page.getByRole('button', { name: 'Avaliar com 4 estrelas' }));
  const tempComment = 'Rascunho temporário para validar exclusão.';
  await humanFill(page, page.locator('section.modal input[name="commentText"]'), tempComment);
  await pauseForVideo(page, 650);

  const publishTempResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/reviews') && res.status() === 201,
  );
  await humanClick(page, page.getByRole('button', { name: 'Publicar avaliação' }), 200);
  await publishTempResponse;
  await expect(page.locator('.comment-list')).toContainText(tempComment);
  await pauseForVideo(page, 850);

  const deleteResponse = page.waitForResponse(
    (res) =>
      res.url().includes('/api/reviews/') &&
      res.request().method() === 'DELETE' &&
      res.status() === 200,
  );
  await humanClick(page, page.locator('.comment-list button', { hasText: 'Excluir' }), 200);
  await deleteResponse;
  await expect(page.locator('.comment-list')).not.toContainText(tempComment);
  await pauseForVideo(page, 700);

  // Publish final 5-star review so it appears in the 30-day Community Reviews feed.
  await humanClick(page, page.getByRole('button', { name: 'Avaliar com 5 estrelas' }));
  const commentText = 'Synthpop envolvente e viciante para dirigir a noite!';
  await humanFill(page, page.locator('section.modal input[name="commentText"]'), commentText);
  await pauseForVideo(page, 650);

  const publishResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/reviews') && res.status() === 201,
  );
  await humanClick(page, page.getByRole('button', { name: 'Publicar avaliação' }), 200);
  await publishResponse;

  await expect(page.locator('.comment-list')).toContainText(commentText);
  await pauseForVideo(page, 950);

  await humanClick(page, page.locator('button.modal-close'));
  await expect(page.locator('section.modal')).toBeHidden();

  // Clear search, sort community reviews by most liked, and like a review card.
  await humanClick(page, page.getByRole('button', { name: 'Limpar busca' }));
  await expect(page.locator('.community-reviews .review-card').first()).toBeVisible();
  await humanClick(page, page.locator('select[aria-label="Ordenar reviews"]'), 150);
  await page.locator('select[aria-label="Ordenar reviews"]').selectOption('likes');
  await pauseForVideo(page, 800);

  const likeReviewResponse = page.waitForResponse(
    (res) => res.url().includes('/api/reviews/') && res.url().includes('/like'),
  );
  await humanClick(
    page,
    page.locator('.community-reviews .review-card').first().locator('button'),
    200,
  );
  await likeReviewResponse;
  await expect(page.locator('.community-reviews .review-card').first().locator('button')).toHaveClass(
    /liked/,
  );
  await pauseForVideo(page, 1100);
});
