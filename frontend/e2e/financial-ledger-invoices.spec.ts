import { expect, test } from "@playwright/test";
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const licence = "3411008090";

test("deterministic browser download preserves the canonical PDF filename", async ({ page }) => {
  test.skip(!realBackendEnabled, "Requires the isolated seeded browser harness.");
  await page.goto("/login");
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click(); await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger", { waitUntil: "networkidle" });
  await page.locator("#ledger-purchase-from").fill(""); await page.locator("#ledger-purchase-to").fill("");
  await page.waitForLoadState("networkidle");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  const numbers = page.getByText("License Numbers", { exact: true }).locator("..").locator("input");
  await numbers.fill(licence); await numbers.press("Enter");
  await page.waitForLoadState("networkidle");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  const selector = page.getByRole("checkbox", { name: `Select licence ${licence}` });
  await selector.check();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Download Merged PDF \(1\)/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`${licence}.pdf`);
  await download.saveAs(`../artifacts/${licence}.pdf`);
  const body = await download.createReadStream();
  expect(body).not.toBeNull();
});
