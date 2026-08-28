import { expect, test } from "@playwright/test";

async function signInAndOpenPivot(page: import("@playwright/test").Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  await page.goto("/reports/item-pivot", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "A3627 Glass Vials / Phials /" }).click();
  await page.getByRole("button", { name: /Notification 025\/2023/ }).click();
  await expect(page.locator("[data-item-pivot-sticky-stack]")).toBeVisible();
}

test("Item Pivot keeps its measured sticky stack aligned while scrolling and horizontally scrolling", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInAndOpenPivot(page);
  const stack = page.locator("[data-item-pivot-sticky-stack]");
  const banner = stack.locator("[data-item-pivot-notification]");
  const headers = stack.locator("[data-item-pivot-header-tier] th");
  const scroller = stack.locator("[data-item-pivot-scroll-container]");

  for (const [name, y] of [["top", 0], ["middle", 900], ["bottom", 1300]] as const) {
    await page.evaluate(scrollY => window.scrollTo(0, scrollY), y);
    await expect(banner).toBeVisible();
    const geometry = await page.evaluate(() => {
      const rect = (e: Element) => e.getBoundingClientRect();
      const nav = document.querySelector(".top-nav")!;
      const stack = document.querySelector("[data-item-pivot-sticky-stack]")!;
      const banner = stack.querySelector("[data-item-pivot-notification]")!;
      const rows = Array.from(stack.querySelectorAll("[data-item-pivot-header-tier]"));
      const first = rows[0].querySelector("th")!;
      const second = rows[1].querySelector("th:not([rowspan])")!;
      const visibleBody = Array.from(stack.querySelectorAll("tbody tr td")).find(cell => rect(cell).top >= rect(second).bottom - 1)!;
      return { nav: rect(nav), banner: rect(banner), first: rect(first), second: rect(second), body: rect(visibleBody), backgrounds: [getComputedStyle(first).backgroundColor, getComputedStyle(second).backgroundColor] };
    });
    if (y > 0) {
      expect(Math.abs(geometry.banner.top - geometry.nav.bottom)).toBeLessThanOrEqual(2);
      expect(Math.abs(geometry.first.top - geometry.banner.bottom)).toBeLessThanOrEqual(2);
      expect(Math.abs(geometry.second.top - (geometry.first.top + geometry.second.height))).toBeLessThanOrEqual(2);
      expect(geometry.body.top).toBeGreaterThanOrEqual(geometry.second.bottom - 1);
    }
    expect(geometry.backgrounds.every(background => background !== "rgba(0, 0, 0, 0)")).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`item-pivot-${name}.png`) });
  }
  await scroller.evaluate(element => { element.scrollLeft = 500; element.dispatchEvent(new Event("scroll")); });
  expect(await scroller.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  await expect(headers.first()).toBeVisible();
  expect(errors).toEqual([]);
});
