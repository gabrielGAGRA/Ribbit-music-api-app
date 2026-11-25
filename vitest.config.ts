import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@ribbit/shared-types': path.resolve(__dirname, './view/src/app/core/models/index.ts'),
      '@core': path.resolve(__dirname, './view/src/app/core'),
      '@shared': path.resolve(__dirname, './view/src/app/shared'),
      '@features': path.resolve(__dirname, './view/src/app/features'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['view/**/*.spec.ts'],
    setupFiles: ['./view/src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcovonly'],
      include: ['view/src/app/**/*.ts'],
      exclude: [
        '**/*.spec.ts',
        'view/src/app/core/models/**',
        'view/src/app/app.routes.ts',
        'view/src/test-setup.ts',
      ],
      thresholds: {
        lines: 85,
        statements: 85,
        functions: 85,
      },
    },
  },
});
