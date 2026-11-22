import { test as base, expect, type Locator, type Page } from '@playwright/test';

export const DEMO_USER_EMAIL = 'usuario@ribbit.example.com';
export const DEMO_USER_PASSWORD = 'RibbitUser2026!';

/**
 * Injects a visible mouse pointer and click-ripple overlay into every page
 * so recorded Playwright WebM videos clearly show cursor movement and clicks.
 */
export async function installHumanCursor(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const setupCursor = () => {
      if (document.getElementById('ribbit-e2e-cursor')) {
        return;
      }

      const style = document.createElement('style');
      style.textContent = `
        #ribbit-e2e-cursor {
          position: fixed;
          top: 0;
          left: 0;
          width: 24px;
          height: 24px;
          pointer-events: none;
          z-index: 2147483647;
          transform: translate(-100px, -100px);
          transition: transform 0.04s linear;
          filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.35));
        }
        .ribbit-e2e-ripple {
          position: fixed;
          width: 28px;
          height: 28px;
          margin-left: -14px;
          margin-top: -14px;
          border-radius: 9999px;
          border: 3px solid #22c55e;
          background: rgba(34, 197, 94, 0.22);
          pointer-events: none;
          z-index: 2147483646;
          animation: ribbit-e2e-click 0.45s ease-out forwards;
        }
        @keyframes ribbit-e2e-click {
          0% { transform: scale(0.4); opacity: 1; }
          100% { transform: scale(1.7); opacity: 0; }
        }
      `;
      document.head.appendChild(style);

      const cursor = document.createElement('div');
      cursor.id = 'ribbit-e2e-cursor';
      cursor.innerHTML = `
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M4 2L20 12.5L12.5 14.2L9.2 21.5L4 2Z" fill="#111827" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
        </svg>
      `;
      document.body.appendChild(cursor);

      const moveCursor = (x: number, y: number) => {
        cursor.style.transform = `translate(${x - 3}px, ${y - 2}px)`;
      };

      const showRipple = (x: number, y: number) => {
        const ripple = document.createElement('div');
        ripple.className = 'ribbit-e2e-ripple';
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        document.body.appendChild(ripple);
        window.setTimeout(() => ripple.remove(), 460);
      };

      window.addEventListener(
        'pointermove',
        (event) => moveCursor(event.clientX, event.clientY),
        true,
      );
      window.addEventListener(
        'mousemove',
        (event) => moveCursor(event.clientX, event.clientY),
        true,
      );
      window.addEventListener(
        'pointerdown',
        (event) => {
          moveCursor(event.clientX, event.clientY);
          showRipple(event.clientX, event.clientY);
        },
        true,
      );
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', setupCursor, { once: true });
    } else {
      setupCursor();
    }
  });
}

export const test = base.extend({
  page: async ({ page }, use) => {
    await installHumanCursor(page);
    await use(page);
  },
});

export { expect };

/** Pauses briefly so state transitions remain readable in recorded E2E demonstration videos. */
export async function pauseForVideo(page: Page, ms = 900): Promise<void> {
  await page.waitForTimeout(ms);
}

/** Smoothly glides the visible cursor to the locator before clicking it. */
export async function humanClick(
  page: Page,
  locator: Locator,
  pauseAfterMs = 450,
): Promise<void> {
  await locator.waitFor({ state: 'visible' });
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 14 });
    await page.waitForTimeout(160);
  }
  await locator.click();
  if (pauseAfterMs > 0) {
    await page.waitForTimeout(pauseAfterMs);
  }
}

/** Moves the visible cursor to an input and fills it at a human-readable pace. */
export async function humanFill(
  page: Page,
  locator: Locator,
  value: string,
  pauseAfterMs = 300,
): Promise<void> {
  await humanClick(page, locator, 120);
  await locator.fill('');
  await locator.pressSequentially(value, { delay: 32 });
  if (pauseAfterMs > 0) {
    await page.waitForTimeout(pauseAfterMs);
  }
}

/** Dismisses the interactive Ribby onboarding tutorial if it appears after login. */
export async function dismissTutorialIfOpen(page: Page): Promise<void> {
  const skipBtn = page.getByRole('button', { name: 'Pular tutorial' });
  try {
    await skipBtn.waitFor({ state: 'visible', timeout: 2000 });
    await humanClick(page, skipBtn, 400);
  } catch {
    // Tutorial did not open for this session
  }
}

/** Authenticates a listener account via the UI login form and waits for discovery hydration. */
export async function loginAsListener(
  page: Page,
  email = DEMO_USER_EMAIL,
  password = DEMO_USER_PASSWORD,
): Promise<void> {
  await page.goto('/discover');
  await expect(page.locator('input[name="email"]')).toBeVisible();
  await pauseForVideo(page, 600);

  const discoveryNextPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/discovery/next') && response.status() === 200,
  );
  const playlistsPromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/playlists') && response.status() === 200,
  );

  await humanFill(page, page.locator('input[name="email"]'), email, 250);
  await humanFill(page, page.locator('input[name="password"]'), password, 250);
  await humanClick(page, page.locator('button[type="submit"]'), 200);

  await expect(page.locator('aside.sidebar')).toBeVisible();
  await Promise.all([discoveryNextPromise, playlistsPromise]);
  await dismissTutorialIfOpen(page);
  await expect(page.locator('.discovery-card')).toBeVisible();
  await pauseForVideo(page, 850);
}
