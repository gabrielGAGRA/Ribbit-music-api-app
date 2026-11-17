import { expect, test } from '@playwright/test';
import { pauseForVideo } from './helpers';

test('admin login, executive dashboard, plan pricing update, users audit, and catalog moderation', async ({
  page,
}) => {
  await page.goto('/admin/login');
  await expect(page.locator('h2', { hasText: 'Entrar no Painel Admin' })).toBeVisible();
  await pauseForVideo(page);

  await page.getByRole('button', { name: 'Preencher credenciais demo' }).click();
  await pauseForVideo(page, 350);
  await page.locator('button[type="submit"]', { hasText: 'Acessar Console Admin' }).click();

  // Inspect Executive Dashboard KPIs and breakdowns.
  await expect(page).toHaveURL(/\/admin\/dashboard$/);
  await expect(page.locator('.kpi-strip')).toContainText('Receita líquida mensal estimada');
  await expect(page.locator('.plan-breakdown-table')).toBeVisible();
  await expect(page.locator('.genre-rank-list')).toBeVisible();
  await pauseForVideo(page, 500);

  // Update Individual subscription price and verify recalculation toast.
  await page.locator('aside.admin-sidebar button', { hasText: 'Planos & Preços' }).click();
  await expect(page).toHaveURL(/\/admin\/plans$/);
  const individualCard = page.locator('.plan-admin-card', { hasText: 'Individual' });
  await individualCard.getByRole('button', { name: /Editar parâmetros do plano/i }).click();
  await individualCard.locator('#plan-price-2').fill('19.9');
  await pauseForVideo(page);
  await individualCard.getByRole('button', { name: /Salvar plano/i }).click();

  await expect(page.locator('.admin-toast')).toContainText('Plano "Individual" atualizado');
  await expect(individualCard).toContainText('R$ 19,90');
  await pauseForVideo(page);

  // Audit Users & Administrators.
  await page.locator('aside.admin-sidebar button', { hasText: 'Usuários & Admins' }).click();
  await expect(page).toHaveURL(/\/admin\/users$/);
  await page.locator('#admin-users-search').fill('Carolina');
  await expect(page.locator('.users-table')).toContainText('Carolina Santos');
  await pauseForVideo(page);

  await page.getByRole('tab', { name: /Administradores/i }).click();
  await page.locator('#admin-users-search').fill('');
  await expect(page.locator('.admins-table')).toContainText('Administrador Local');
  await pauseForVideo(page);

  // Moderate catalog tracks (+18 flag, soft-delete block, restore) and abusive reviews.
  await page.locator('aside.admin-sidebar button', { hasText: 'Moderação' }).click();
  await expect(page).toHaveURL(/\/admin\/moderation$/);
  await page.locator('#moderation-track-search').fill('Vento');

  const ventoRow = page.locator('.tracks-table tbody tr', { hasText: 'Vento de Outubro' });
  await expect(ventoRow).toBeVisible();
  await ventoRow.locator('button.explicit-toggle').click();
  await expect(ventoRow.locator('button.explicit-toggle')).toContainText('+18 Explícita');
  await pauseForVideo(page);

  await ventoRow.getByRole('button', { name: 'Bloquear faixa' }).click();
  await expect(page.locator('.admin-toast')).toContainText('Vento de Outubro');

  await page.getByRole('tab', { name: /Faixas Bloqueadas/i }).click();
  const blockedVentoRow = page.locator('.tracks-table tbody tr', { hasText: 'Vento de Outubro' });
  await expect(blockedVentoRow).toBeVisible();
  await pauseForVideo(page);

  await blockedVentoRow.getByRole('button', { name: 'Restaurar ao catálogo' }).click();
  await expect(page.locator('.admin-toast')).toContainText('restaurada ao catálogo ativo');

  await page.getByRole('tab', { name: /Top Reviews 30d/i }).click();
  const spamReviewCard = page.locator('.review-mod-card', { hasText: 'Verso Cortante' });
  await expect(spamReviewCard).toBeVisible();
  await pauseForVideo(page);

  await spamReviewCard.getByRole('button', { name: /Excluir avaliação/i }).click();
  await expect(spamReviewCard).toBeHidden();
  await pauseForVideo(page, 500);
});
