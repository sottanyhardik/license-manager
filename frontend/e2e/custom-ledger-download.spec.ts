import { expect, test } from "@playwright/test";
import { readFileSync, statSync } from "node:fs";
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const licence = "3411008090";

test("Custom Ledger action downloads one deterministic native PDF without navigating away", async ({ page }, testInfo) => {
  test.skip(!realBackendEnabled, "Requires the isolated seeded browser harness.");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text()); });
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger", { waitUntil: "networkidle" });
  const licenceNumbers = page.getByText("Include License Numbers", { exact: true }).locator("..").locator("input");
  await licenceNumbers.fill(licence);
  await licenceNumbers.press("Enter");
  await page.waitForLoadState("networkidle");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  const licenceRow = page.getByText(licence, { exact: true }).first().locator("xpath=ancestor::tr[1]");
  await expect(licenceRow).toBeVisible();
  const action = licenceRow.getByRole("button", { name: `Download custom ledger PDF for ${licence}`, exact: true });
  await expect(action).toBeVisible();
  const requestCount = { value: 0 };
  const pdfResponses: import("@playwright/test").Response[] = [];
  page.on("request", request => { if (request.url().includes("custom-ledger-pdf")) requestCount.value += 1; });
  page.on("response", response => { if (response.url().includes("custom-ledger-pdf")) pdfResponses.push(response); });
  const [download] = await Promise.all([page.waitForEvent("download"), action.click()]);
  expect(requestCount.value).toBe(1);
  expect(pdfResponses).toHaveLength(1);
  expect(pdfResponses[0].headers()["content-type"]).toContain("application/pdf");
  expect(page.url()).toContain("/license-ledger");
  // Filename contract: backend/apps/license/views/ledger.py custom_ledger_pdf -> f'{license_number}.pdf'.
  expect(download.suggestedFilename()).toBe(`${licence}.pdf`);
  // Keep the saved PDF in the per-test output directory (git-ignored test-results/),
  // not in the tracked repository artifacts/ directory.
  const saved = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(saved);
  expect(statSync(saved).size).toBeGreaterThan(0);
  expect(readFileSync(saved).subarray(0, 5).toString()).toBe("%PDF-");
  expect(errors).toEqual([]);
});
