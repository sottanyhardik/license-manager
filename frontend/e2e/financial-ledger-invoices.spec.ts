import { expect, test } from "@playwright/test";

test("0311055282 browser download preserves the canonical PDF filename", async ({ page }) => {
  await page.goto("/login");
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click(); await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger");
  await page.locator("#ledger-purchase-from").fill(""); await page.locator("#ledger-purchase-to").fill("");
  const numbers = page.getByText("License Numbers", { exact: true }).locator("..").locator("input");
  await numbers.fill("0311055282"); await numbers.press("Enter");
  const selector = page.getByRole("checkbox", { name: "Select licence 0311055282" });
  await selector.check();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Download Merged PDF \(1\)/ }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("0311055282.pdf");
  await download.saveAs("../artifacts/0311055282.pdf");
  const body = await download.createReadStream();
  expect(body).not.toBeNull();
});
