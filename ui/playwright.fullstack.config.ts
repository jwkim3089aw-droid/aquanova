import { defineConfig, devices } from '@playwright/test';

const reuseExistingServer =
  process.env.AQUANOVA_E2E_REUSE_SERVERS === '1';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'nf-fullstack.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 90_000,
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command:
        'cd .. && python -m uvicorn app.main:app ' +
        '--host 127.0.0.1 --port 8003',
      url: 'http://127.0.0.1:8003/health',
      reuseExistingServer,
      timeout: 120_000,
    },
    {
      command:
        'npm run dev -- --host 127.0.0.1 ' +
        '--port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      env: {
        VITE_API_URL: 'http://127.0.0.1:8003',
      },
      reuseExistingServer,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
