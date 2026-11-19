import { expect, test } from '@playwright/test';
import { loginAsListener, pauseForVideo } from './helpers';

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

  await page.locator('aside.sidebar nav button', { hasText: 'Explorar' }).click();
  await expect(page).toHaveURL(/\/explore$/);
  await expect(page.locator('.community-reviews')).toBeVisible();
  await pauseForVideo(page);

  // Open search filters modal and apply genre Pop.
  await page.locator('button.search-filter-button').click();
  await expect(page.locator('section.modal h2', { hasText: 'Filtrar sua busca' })).toBeVisible();
  await page
    .locator('section.modal .genre-options')
    .getByRole('button', { name: 'Pop', exact: true })
    .click();
  await pauseForVideo(page);

  const filterSearchResponse = page.waitForResponse(
    (res) => res.url().includes('/api/tracks/search') && res.status() === 200,
  );
  await page.getByRole('button', { name: /Aplicar filtros/i }).click();
  await filterSearchResponse;

  // Search for Blinding Lights and inspect results.
  const searchResponse = page.waitForResponse(
    (res) =>
      res.url().includes('/api/tracks/search') &&
      res.url().includes('Blinding') &&
      res.status() === 200,
  );
  await page.locator('.explore-search input').fill('Blinding');
  await searchResponse;

  await expect(page.locator('.search-results')).toContainText('Blinding Lights');
  await pauseForVideo(page);

  // Open track details modal, test review delete lifecycle, then publish a kept 5-star review.
  const reviewsLoaded = page.waitForResponse(
    (res) => res.url().includes('/api/reviews/track/') && res.status() === 200,
  );
  await page.getByRole('button', { name: 'Ver detalhes de Blinding Lights' }).click();
  await reviewsLoaded;
  await expect(page.locator('section.modal h2', { hasText: 'Blinding Lights' })).toBeVisible();

  await page.getByRole('button', { name: 'Avaliar com 4 estrelas' }).click();
  const tempComment = 'Rascunho temporário para validar exclusão.';
  await page.locator('section.modal input[name="commentText"]').fill(tempComment);
  await pauseForVideo(page, 350);

  const publishTempResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/reviews') && res.status() === 201,
  );
  await page.getByRole('button', { name: 'Publicar comentário' }).click();
  await publishTempResponse;
  await expect(page.locator('.comment-list')).toContainText(tempComment);
  await pauseForVideo(page, 400);

  const deleteResponse = page.waitForResponse(
    (res) =>
      res.url().includes('/api/reviews/') &&
      res.request().method() === 'DELETE' &&
      res.status() === 200,
  );
  await page.locator('.comment-list button', { hasText: 'Excluir' }).click();
  await deleteResponse;
  await expect(page.locator('.comment-list')).not.toContainText(tempComment);

  // Publish final 5-star review so it appears in the 30-day Community Reviews feed.
  await page.getByRole('button', { name: 'Avaliar com 5 estrelas' }).click();
  const commentText = 'Synthpop envolvente e viciante para dirigir a noite!';
  await page.locator('section.modal input[name="commentText"]').fill(commentText);
  await pauseForVideo(page);

  const publishResponse = page.waitForResponse(
    (res) => res.url().endsWith('/api/reviews') && res.status() === 201,
  );
  await page.getByRole('button', { name: 'Publicar comentário' }).click();
  await publishResponse;

  await expect(page.locator('.comment-list')).toContainText(commentText);
  await pauseForVideo(page, 500);

  await page.locator('button.modal-close').click();
  await expect(page.locator('section.modal')).toBeHidden();

  // Clear search, sort community reviews by most liked, and like a review card.
  await page.getByRole('button', { name: 'Limpar busca' }).click();
  await expect(page.locator('.community-reviews .review-card').first()).toBeVisible();
  await page.locator('select[aria-label="Ordenar reviews"]').selectOption('likes');
  await pauseForVideo(page);

  const likeReviewResponse = page.waitForResponse(
    (res) => res.url().includes('/api/reviews/') && res.url().includes('/like'),
  );
  await page.locator('.community-reviews .review-card').first().locator('button').click();
  await likeReviewResponse;
  await expect(page.locator('.community-reviews .review-card').first().locator('button')).toHaveClass(
    /liked/,
  );
  await pauseForVideo(page, 500);
});
