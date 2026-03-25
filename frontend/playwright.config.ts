import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')
const frontendRoot = __dirname

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  globalSetup: './tests/e2e/global-setup.ts',
  webServer: [
    {
      command: `python -m uvicorn backend.app.main:app --app-dir ${repoRoot} --host 127.0.0.1 --port 8000`,
      cwd: repoRoot,
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      cwd: frontendRoot,
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: true,
    },
  ],
})
