import { expect, test } from "@playwright/test";
import { readFileSync, statSync } from "node:fs";

/**
 * Ledger Excel export (current supported workflow).
 *
 * Replaces the obsolete "Download Merged PDF (n)" check. That toolbar control was
 * removed in commit 79a08ac2, which replaced it with the Download Package workflow.
 * This spec covers the still-supported Excel export: its filename contract comes from
 * frontend/src/services/licenseLedgerExport.ts (filename()), and an .xlsx file is a
 * zip archive, so its first two bytes are "PK".
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const licence = "3411008090";

test("ledger Excel export downloads an xlsx with the service filename contract", async ({ page }, testInfo) => {
  test.skip(!realBackendEnabled, "Requires the isolated seeded browser harness.");
  await page.goto("/login");
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger", { waitUntil: "networkidle" });
  await page.locator("#ledger-purchase-from").fill("");
  await page.locator("#ledger-purchase-to").fill("");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  const numbers = page.getByText("Include License Numbers", { exact: true }).locator("..").locator("input");
  await numbers.fill(licence);
  await numbers.press("Enter");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  await expect(page.getByRole("checkbox", { name: `Select licence ${licence}` })).toBeVisible();

  const excel = page.getByRole("button", { name: "Download license ledger as Excel" });
  await expect(excel).toBeEnabled();
  const [download] = await Promise.all([page.waitForEvent("download"), excel.click()]);

  // Filename contract: license-ledger[-licenseId][-itemId].xlsx (licenseLedgerExport.ts).
  expect(download.suggestedFilename()).toMatch(/^license-ledger(-[A-Za-z0-9_-]+)*\.xlsx$/);
  const saved = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(saved);
  expect(statSync(saved).size).toBeGreaterThan(0);
  expect(readFileSync(saved).subarray(0, 2).toString("latin1")).toBe("PK");
});
