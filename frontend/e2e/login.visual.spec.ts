import { expect, test } from "@playwright/test";

const sizes = [
  { name: "desktop", width: 1440, height: 960 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "narrow", width: 390, height: 844 },
];

test.describe("local application shell", () => {
  for (const size of sizes) {
    test(`sign in is usable at ${size.name}`, async ({ page }, testInfo) => {
      const errors: string[] = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {
        if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text());
      });

      await page.setViewportSize({ width: size.width, height: size.height });
      await page.goto("/login", { waitUntil: "networkidle" });
      await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
      const username = page.getByLabel("Username");
      await username.focus();
      await username.fill("operator");
      await expect(username).toBeFocused();
      await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow).toBeFalsy();
      expect(errors).toEqual([]);
      await page.screenshot({ path: testInfo.outputPath(`login-${size.name}.png`), fullPage: true });
    });
  }

  test("sign in keeps readable surfaces in dark mode", async ({ page }, testInfo) => {
    await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/login", { waitUntil: "networkidle" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
    await expect(page.getByLabel("Username")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBeFalsy();
    await page.screenshot({ path: testInfo.outputPath("login-dark.png"), fullPage: true });
  });
});
