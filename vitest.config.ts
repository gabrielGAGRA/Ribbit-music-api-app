import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@ribbit/shared-types': path.resolve(__dirname, './view/src/types/index.ts'),
      '@core': path.resolve(__dirname, './view/src/app/core'),
      '@shared': path.resolve(__dirname, './view/src/app/shared'),
      '@features': path.resolve(__dirname, './view/src/app/features'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./view/src/test-setup.ts'],
    env: {
      TUNNEL_URL: 'https://grumpy-books-scream.loca.lt',
    },
  },
});
