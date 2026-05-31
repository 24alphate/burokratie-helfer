import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the Bürokratie-Helfer frontend.
 *
 * `npm run test:e2e` auto-starts both servers (reused if already running):
 *   - backend  : FastAPI on :8001 (migrate + seed + uvicorn, from ../backend)
 *   - frontend : Next dev on :3010, pointed at the backend via NEXT_PUBLIC_API_URL
 *
 * Overridable via env:
 *   E2E_BASE_URL          frontend URL under test     (default http://localhost:3010)
 *   E2E_API_URL           backend URL                 (default http://localhost:8001)
 *   E2E_PYTHON            backend interpreter         (default backend/.venv venv python)
 *
 * Jest unit tests (src/**​/__tests__/*.test.ts) are untouched — Playwright only
 * collects specs under ./e2e.
 */
const FRONTEND_PORT = 3010;
const BACKEND_PORT = 8001;
const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${FRONTEND_PORT}`;
const API_URL = process.env.E2E_API_URL || `http://localhost:${BACKEND_PORT}`;

const isWin = process.platform === "win32";
const PYTHON =
  process.env.E2E_PYTHON ||
  (isWin ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");

// Migrate + seed (idempotent) then serve. Skipped entirely when a backend is
// already listening (reuseExistingServer), so local re-runs are fast.
const backendCommand =
  `${PYTHON} -m alembic upgrade head && ` +
  `${PYTHON} -m app.form_templates.seed && ` +
  `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    acceptDownloads: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: backendCommand,
      cwd: "../backend",
      url: `${API_URL}/api/v1/templates`,
      reuseExistingServer: true,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm run dev -- -p ${FRONTEND_PORT}`,
      url: BASE_URL,
      reuseExistingServer: true,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_URL: API_URL },
    },
  ],
});
