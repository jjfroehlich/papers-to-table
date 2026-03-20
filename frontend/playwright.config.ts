import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '../tests/e2e',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
  },
  webServer: [
    {
      command: "python - <<'PY'\nfrom pathlib import Path\nfrom backend.app.config import load_config\nfrom backend.app.runner import Runner\nconfig = load_config('tests/fixtures/configs/test-config.json')\nconfig.paths.output_dir = 'artifacts'\nRunner(Path('artifacts')).execute(config)\nPY\npython -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
      cwd: '..',
      port: 8000,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      cwd: 'frontend',
      port: 4173,
      reuseExistingServer: true,
    },
  ],
})
