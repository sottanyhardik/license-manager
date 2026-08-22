import { defineConfig, devices } from "@playwright/test";

/**
 * Local-only browser verification.  It exercises the Vite application on an
 * isolated port and deliberately never talks to a production host.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  outputDir: "test-results/playwright",
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:41731",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 41731 --strictPort",
    url: "http://127.0.0.1:41731/login",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
