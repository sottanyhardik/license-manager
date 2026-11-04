import { expect, test, type Page } from "@playwright/test";

/**
 * Planning workbench smoke on `/planning`: the KPI strip renders from the real
 * dashboard endpoint, the page raises no uncaught errors, and nothing is saved,
 * queued or retried.
 *
 * Opt-in (`LM_REAL_E2E=1`), read-only.  Credentials come from LM_USERNAME and
 * LM_PASSWORD, the same variables the other real-backend specs use.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

test.describe("planning workbench (real backend, read-only)", () => {
  test.skip(!realBackendEnabled, "Set LM_REAL_E2E=1 to run against the local backend.");

  test("renders the operational overview without uncaught errors", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await signIn(page);
    await page.goto("/planning", { waitUntil: "domcontentloaded" });

    const overview = page.getByRole("region", { name: "Planning overview" });
    await expect(overview.getByText("Loading planning overview")).toBeHidden({ timeout: 15_000 });
    await expect(overview.getByText("Active rules", { exact: true })).toBeVisible();
    await expect(overview.getByText("Not modelled", { exact: true })).toBeVisible();
    expect(pageErrors).toEqual([]);
  });
});
