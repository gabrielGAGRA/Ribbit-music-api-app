import { expect, humanClick, humanFill, pauseForVideo, test } from './helpers';

test('admin login, executive dashboard, plan pricing update, users audit, and catalog moderation', async ({
  page,
}) => {
  await page.goto('/admin/login');
  await expect(page.locator('h2', { hasText: 'Entrar no Painel Admin' })).toBeVisible();
  await pauseForVideo(page, 850);

  await humanFill(page, page.locator('#admin-login-email'), 'admin@ribbit.example.com');
  await humanFill(page, page.locator('#admin-login-password'), 'RibbitLocal2026!');
  await pauseForVideo(page, 600);

  const loginResponse = page.waitForResponse(
    (res) => res.url().includes('/api/admin/login') && res.status() === 200,
  );
  await humanClick(
    page,
    page.locator('button[type="submit"]', { hasText: 'Acessar Console Admin' }),
    200,
  );
  await loginResponse;

  // Inspect Executive Dashboard KPIs and breakdowns.
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(page.locator('.kpi-strip')).toContainText('Receita líquida mensal estimada');
  await expect(page.locator('.plan-breakdown-table')).toBeVisible();
  await expect(page.locator('.genre-rank-list')).toBeVisible();
  await pauseForVideo(page, 1100);

  // Update Individual subscription price and verify recalculation toast.
  await humanClick(page, page.locator('aside.admin-sidebar button', { hasText: 'Planos & Preços' }));
  await expect(page).toHaveURL(/\/admin\/plans$/);
  await pauseForVideo(page, 700);
  const individualCard = page.locator('.plan-admin-card', { hasText: 'Individual' });
  await humanClick(
    page,
    individualCard.getByRole('button', { name: /Editar parâmetros do plano/i }),
  );
  await humanFill(page, individualCard.locator('#plan-price-2'), '19.9');
  await pauseForVideo(page, 650);

  const updatePlanResponse = page.waitForResponse(
    (res) =>
      res.url().includes('/api/admin/plans/2') &&
      res.request().method() === 'PUT' &&
      res.status() === 200,
  );
  await humanClick(page, individualCard.getByRole('button', { name: /Salvar plano/i }), 200);
  await updatePlanResponse;

  await expect(page.locator('.admin-toast')).toContainText('Plano "Individual" atualizado');
  await expect(individualCard).toContainText('R$ 19,90');
  await pauseForVideo(page, 950);

  // Audit Users & Administrators.
  await humanClick(
    page,
    page.locator('aside.admin-sidebar button', { hasText: 'Usuários & Admins' }),
  );
  await expect(page).toHaveURL(/\/admin\/users$/);
  await humanFill(page, page.locator('#admin-users-search'), 'Usuário');
  await expect(page.locator('.users-table')).toContainText('Usuário Demo');
  await pauseForVideo(page, 900);

  await humanClick(page, page.getByRole('tab', { name: /Administradores/i }));
  await humanFill(page, page.locator('#admin-users-search'), '');
  await expect(page.locator('.admins-table')).toContainText('Administrador Local');
  await pauseForVideo(page, 900);

  // Moderate catalog tracks (+18 flag, soft-delete block, restore) and inspect reviews tab.
  await humanClick(page, page.locator('aside.admin-sidebar button', { hasText: 'Moderação' }));
  await expect(page).toHaveURL(/\/admin\/moderation$/);
  await humanFill(page, page.locator('#moderation-track-search'), '7 Years');

  const trackRow = page.locator('.tracks-table tbody tr', { hasText: '7 Years' });
  await expect(trackRow).toBeVisible();

  const explicitResponse = page.waitForResponse(
    (res) => res.url().includes('/explicit') && res.status() === 200,
  );
  await humanClick(page, trackRow.locator('button.explicit-toggle'), 200);
  await explicitResponse;
  await expect(trackRow.locator('button.explicit-toggle')).toContainText('+18 Explícita');
  await pauseForVideo(page, 850);

  const blockResponse = page.waitForResponse(
    (res) => res.url().includes('/block') && res.status() === 200,
  );
  await humanClick(page, trackRow.getByRole('button', { name: 'Bloquear faixa' }), 200);
  await blockResponse;
  await expect(page.locator('.admin-toast')).toContainText('7 Years');
  await pauseForVideo(page, 700);

  await humanClick(page, page.getByRole('tab', { name: /Faixas Bloqueadas/i }));
  const blockedTrackRow = page.locator('.tracks-table tbody tr', {
    hasText: '7 Years',
  });
  await expect(blockedTrackRow).toBeVisible();
  await pauseForVideo(page, 850);

  const restoreResponse = page.waitForResponse(
    (res) => res.url().includes('/block') && res.status() === 200,
  );
  await humanClick(
    page,
    blockedTrackRow.getByRole('button', { name: 'Restaurar ao catálogo' }),
    200,
  );
  await restoreResponse;
  await expect(page.locator('.admin-toast')).toContainText('restaurada ao catálogo ativo');
  await pauseForVideo(page, 700);

  await humanClick(page, page.getByRole('tab', { name: /Top Reviews 30d/i }));
  await expect(page.locator('.reviews-list')).toBeVisible();
  await pauseForVideo(page, 1000);
});
