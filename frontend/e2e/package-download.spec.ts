import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
test("downloads selected ledger package", async ({ page }) => {
  const licence = process.env.LM_LICENSE || "0311051359";
  await page.goto("/login");
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click(); await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger");
  await page.locator("#ledger-purchase-from").fill(""); await page.locator("#ledger-purchase-to").fill("");
  const input = page.getByText("License Numbers", { exact: true }).locator("..").locator("input"); await input.fill(licence); await input.press("Enter");
  const row = page.getByText(licence, { exact: true }).first().locator("xpath=ancestor::tr[1]"); await expect(row).toBeVisible();
  await row.getByRole("checkbox", { name: /select licence/i }).check();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: /Download Merged PDF \(1\)/ }).click()]);
  mkdirSync("../artifacts", { recursive: true }); await download.saveAs(`../artifacts/${licence}.pdf`);
  expect(download.suggestedFilename()).toBe(`${licence}.pdf`);
});
