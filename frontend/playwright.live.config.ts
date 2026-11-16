import { defineConfig, devices } from "@playwright/test";

/** Read-only live-browser suite config: no webServer; target is supplied via PLAYWRIGHT_BASE_URL. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.live\.spec\.ts/,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  outputDir: "test-results/playwright-live",
  reporter: [["list"]],
  workers: 1,
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
