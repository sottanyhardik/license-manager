import { expect, test, type Page } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

const localUser = {
  id: 1,
  username: "visual.operator",
  first_name: "Visual",
  last_name: "Operator",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

async function mockAuthenticatedDashboard(page: Page) {
  await page.addInitScript((user) => {
    localStorage.setItem("access", "visual-test-access-token");
    localStorage.setItem("refresh", "visual-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(user));
  }, localUser);

  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/auth/me/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(localUser) });
      return;
    }
    if (pathname.endsWith("/dashboard/")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          license_stats: { total: 42, active: 36, expired: 2, null_dfia: 1, expiring_soon: 3 },
          allotment_stats: { total: 18, recent: [] },
          boe_stats: { total: 27, pending_invoices: 4, recent: [] },
          expiring_licenses: [],
          boe_monthly_trend: [],
        }),
      });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

test.describe("authenticated shell visual mock", () => {
  test("dashboard is contained at mobile portrait and landscape", async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("favicon")) errors.push(message.text());
    });
    await mockAuthenticatedDashboard(page);

    for (const viewport of [
      { name: "mobile-320", width: 320, height: 640 },
      { name: "mobile-390", width: 390, height: 844 },
      { name: "mobile-landscape", width: 667, height: 375 },
      { name: "tablet", width: 768, height: 1024 },
      { name: "laptop", width: 1280, height: 800 },
      { name: "desktop", width: 1440, height: 960 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/dashboard", { waitUntil: "networkidle" });
      await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
      await expectNoBasicSemanticViolations(page);
      if (viewport.name === "mobile-390" || viewport.name === "desktop") {
        await expectNoSeriousOrCriticalAxeViolations(page, "main");
      }
      await expectNoDocumentOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`dashboard-${viewport.name}.png`), fullPage: true });
    }

    expect(errors).toEqual([]);
  });

  test("mobile navigation drawer traps, closes, and restores focus", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockAuthenticatedDashboard(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });

    const trigger = page.getByTestId("mobile-nav-toggle");
    await expect(trigger).toBeVisible();
    await trigger.click();
    const drawer = page.getByTestId("mobile-nav-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Close navigation menu" })).toBeFocused();
    await expectNoDocumentOverflow(page);
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(trigger).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath("dashboard-mobile-drawer.png"), fullPage: true });
  });
});
