import {
  dismissTutorialIfOpen,
  expect,
  humanClick,
  humanFill,
  pauseForVideo,
  test,
} from './helpers';

test('onboarding registration with age validation, genre filters, discovery swipes, and collections', async ({
  page,
}) => {
  await page.goto('/discover');
  await expect(page.locator('.auth-card')).toBeVisible();
  await pauseForVideo(page, 800);

  await humanClick(page, page.locator('.auth-switch button'));
  await expect(page.locator('input[name="name"]')).toBeVisible();

  // Verify underage guard rejects birth date under 18 years old.
  await humanClick(page, page.locator('input[name="birthDate"]'), 150);
  await page.locator('input[name="birthDate"]').fill('2012-05-15');
  await expect(page.locator('.auth-field-error')).toContainText(
    'Cadastro direto permitido apenas para maiores de 18 anos.',
  );
  await expect(page.locator('button[type="submit"]')).toBeDisabled();
  await pauseForVideo(page, 950);

  // Fill valid adult registration on Individual plan (enables blocked-genre filter).
  const uniqueEmail = `e2e.onboarding.${Date.now()}@ribbit.example.com`;
  await humanFill(page, page.locator('input[name="name"]'), 'Beatriz E2E');
  await humanFill(page, page.locator('input[name="email"]'), uniqueEmail);
  await humanClick(page, page.locator('input[name="birthDate"]'), 150);
  await page.locator('input[name="birthDate"]').fill('1998-05-20');
  await humanClick(page, page.locator('select[name="planId"]'), 150);
  await page.locator('select[name="planId"]').selectOption('2');
  await humanFill(page, page.locator('input[name="password"]'), 'RibbitE2E2026!');
  await humanFill(page, page.locator('input[name="confirmPassword"]'), 'RibbitE2E2026!');
  await humanClick(page, page.locator('.auth-check input[type="checkbox"]'), 300);
  await pauseForVideo(page, 700);

  const discoveryReady = page.waitForResponse(
    (response) =>
      response.url().includes('/api/discovery/next') && response.status() === 200,
  );
  await humanClick(page, page.locator('button[type="submit"]'), 200);
  await discoveryReady;

  await expect(page.locator('aside.sidebar')).toBeVisible();
  await dismissTutorialIfOpen(page);
  await expect(page.locator('.discovery-card')).toBeVisible();
  await pauseForVideo(page, 1000);

  // Configure favorite and blocked genres via Configurações -> Editar filtros.
  await humanClick(
    page,
    page.locator('aside.sidebar').getByRole('button', { name: 'Configurações' }),
  );
  await expect(page).toHaveURL(/\/settings$/);
  await pauseForVideo(page, 700);
  await humanClick(page, page.getByRole('button', { name: 'Editar filtros' }));
  await expect(
    page.locator('section.modal h2', { hasText: 'Qual é a sua frequência?' }),
  ).toBeVisible();
  await humanClick(
    page,
    page
      .locator('section.modal .genre-options')
      .nth(0)
      .getByRole('button', { name: 'Rock', exact: true }),
  );
  const blockedUpdate = page.waitForResponse(
    (response) =>
      response.url().includes('/api/profile/blocked-genres') &&
      response.request().method() === 'PUT' &&
      response.status() === 200,
  );
  await humanClick(
    page,
    page
      .locator('section.modal .genre-options')
      .nth(1)
      .getByRole('button', { name: 'Hip Hop', exact: true }),
    200,
  );
  await blockedUpdate;
  await pauseForVideo(page, 750);

  await humanClick(page, page.getByRole('button', { name: /Salvar preferências/i }));
  await expect(page.locator('section.modal')).toBeHidden();
  await pauseForVideo(page, 850);

  await humanClick(page, page.locator('aside.sidebar nav button', { hasText: 'Descoberta' }));
  await expect(page.locator('.discovery-card')).toBeVisible();
  await pauseForVideo(page, 700);

  // Perform three distinct discovery swipes: like, love (superlike), reject.
  const trackHeading = page.locator('.discovery-card .track-heading h2');

  const likedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(likedTitle.length).toBeGreaterThan(0);
  const likeNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await humanClick(page, page.getByRole('button', { name: 'Curtir música' }), 250);
  await likeNext;
  await expect(trackHeading).not.toHaveText(likedTitle);
  await pauseForVideo(page, 900);

  const lovedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(lovedTitle.length).toBeGreaterThan(0);
  const loveNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await humanClick(page, page.getByRole('button', { name: 'Amar música' }), 250);
  await loveNext;
  await expect(trackHeading).not.toHaveText(lovedTitle);
  await pauseForVideo(page, 900);

  const rejectedTitle = (await trackHeading.textContent())?.trim() ?? '';
  expect(rejectedTitle.length).toBeGreaterThan(0);
  const rejectNext = page.waitForResponse((res) => res.url().includes('/api/discovery/next'));
  await humanClick(page, page.getByRole('button', { name: 'Rejeitar música' }), 250);
  await rejectNext;
  await pauseForVideo(page, 900);

  // Verify the collections reflect all three interactions.
  await humanClick(page, page.locator('aside.sidebar button', { hasText: 'Músicas curtidas' }));
  await expect(page).toHaveURL(/\/likes$/);
  await expect(page.locator('.collection-list')).toContainText(likedTitle);
  await expect(page.locator('.collection-list')).toContainText(lovedTitle);
  await pauseForVideo(page, 1000);

  await humanClick(page, page.locator('aside.sidebar button', { hasText: 'Minhas amadas' }));
  await expect(page).toHaveURL(/\/loved$/);
  await expect(page.locator('.collection-list')).toContainText(lovedTitle);
  await pauseForVideo(page, 1000);

  await humanClick(page, page.locator('aside.sidebar button', { hasText: 'Rejeitadas' }));
  await expect(page).toHaveURL(/\/rejected$/);
  await expect(page.locator('.collection-list')).toContainText(rejectedTitle);
  await pauseForVideo(page, 1100);
});
