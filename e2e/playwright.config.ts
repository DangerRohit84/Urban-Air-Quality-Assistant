import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const ROOT = path.resolve(__dirname, "..");
const BASE_URL = "http://127.0.0.1:8901";
const DB_FILE = `e2e/.tmp/e2e-${process.pid}-${Date.now()}.db`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: process.env.CI ? 2 : undefined,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command:
      ".\\.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --port 8901 --no-proxy-headers",
    cwd: ROOT,
    url: `${BASE_URL}/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      AUTH_SECRET: "e2e-secret-not-for-production",
      DATABASE_URL: `sqlite:///${DB_FILE}`,
      LLM_PROVIDER: "local_synth",
      AQI_API_KEY: "e2e-offline-key",
      HTTP_PROXY: "http://127.0.0.1:9",
      HTTPS_PROXY: "http://127.0.0.1:9",
      NO_PROXY: "127.0.0.1,localhost",
      RATE_LIMIT_PER_MIN: "100000",
      FRONTEND_ORIGIN: BASE_URL,
    },
  },
  globalTeardown: "./global-teardown.ts",
});
