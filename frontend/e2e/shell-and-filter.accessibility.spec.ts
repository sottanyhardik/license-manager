import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Route-level regression for the shared shell and filter controls (A11Y-001).
 *
 * Runs only through the isolated browser harness (scripts/test/run_data_bearing_browser_e2e.sh)
 * because the routes need an authenticated session and seeded data.
 *
 * Asserts zero violations for exactly the rules fixed in this pass. It does not claim
 * that other axe rules pass; those are measured separately.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";

const ROUTES = [
  "/dashboard",
  "/license-ledger",
  "/incentive-licenses",
  "/reports/item-pivot",
  "/reports/item-report",
  "/reports/planned-report",
];
const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "desktop", width: 1440, height: 900 },
];
const RULES = ["button-name", "link-name", "label", "color-contrast"];

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

test.describe("shell and filter accessibility (guarded)", () => {
  test.skip(!realBackendEnabled, "Requires the isolated seeded harness; never points at a shared database.");

  test("routes have no violations for the fixed rules at mobile and desktop widths", async ({ page }) => {
    test.setTimeout(240000);
    await signIn(page);
    const failures: string[] = [];
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      for (const route of ROUTES) {
        await page.goto(route, { waitUntil: "networkidle" });
        const results = await new AxeBuilder({ page }).withRules(RULES).analyze();
        for (const violation of results.violations) {
          const targets = violation.nodes.map((node) => node.target.join(" ")).join(", ");
          failures.push(`${viewport.name} ${route} ${violation.id}: ${violation.nodes.length} node(s) [${targets}]`);
        }
      }
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
});
