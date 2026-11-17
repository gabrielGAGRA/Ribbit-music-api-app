import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from '@playwright/test';

function resolvePythonBin(): string {
  const fromEnv = process.env['PYTHON_BIN'];
  if (fromEnv && fromEnv.trim().length > 0) {
    return fromEnv;
  }
  const candidates = [
    path.resolve(process.cwd(), '.venv', 'Scripts', 'python.exe'),
    path.resolve(process.cwd(), '.venv', 'bin', 'python'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return 'python';
}

const pythonBin = resolvePythonBin();
const backendCommand = `"${pythonBin}" scripts/prepare_e2e_db.py && "${pythonBin}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000`;

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.e2e.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: {
    timeout: 12_000,
  },
  retries: process.env['CI'] ? 1 : 0,
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['html', { open: 'never' }],
  ],
  outputDir: 'test-results',
  use: {
    baseURL: 'http://localhost:4200',
    headless: true,
    viewport: { width: 1280, height: 720 },
    video: {
      mode: 'on',
      size: { width: 1280, height: 720 },
    },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 15_000,
  },
  webServer: [
    {
      command: backendCommand,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        ...process.env,
        DATABASE_PATH: 'e2e.db',
        PYTHONUNBUFFERED: '1',
      },
    },
    {
      command: 'npm run start',
      url: 'http://localhost:4200',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        ...process.env,
        API_PROXY_TARGET: 'http://127.0.0.1:8000',
      },
    },
  ],
});
