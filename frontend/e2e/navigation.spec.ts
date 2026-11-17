import { expect, test, type Page } from "@playwright/test";

/**
 * Browser regression for the primary navigation (local mock, no backend).
 * Covers real hover geometry, viewport containment, overlap, touch and the
 * route of every menu item — things jsdom cannot see.
 */
const user = {
  id: 1,
  username: "nav.operator",
  first_name: "Nav",
  last_name: "Operator",
  is_superuser: true,
  roles: [
    "LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER",
    "REPORT_VIEWER", "LEDGER_MANAGER", "INCENTIVE_LICENSE_MANAGER",
  ],
};

const MENUS: Record<string, string[]> = {
  Licenses: ["/licenses", "/planning", "/incentive-licenses", "/license-ledger", "/ledger-upload"],
  Operations: ["/allotments", "/bill-of-entries", "/trades", "/reconciliation", "/reconciliation-issues"],
  Reports: [
    "/license-ledger/download-requests", "/reports/item-pivot", "/reports/item-report", "/reports/planned-report",
    "/reports/license-purchase-profit", "/reports/expiring-licenses", "/reports/active-licenses",
    "/reports/download-license", "/reports/parle/sion-e1", "/reports/parle/sion-e5", "/reports/parle/sion-e126",
    "/reports/parle/sion-e132",
  ],
  Masters: [
    "/masters/companies", "/masters/ports", "/masters/hs-codes", "/masters/head-norms", "/masters/sion-classes",
    "/masters/groups", "/masters/item-names", "/masters/exchange-rates",
  ],
};

async function mockShell(page: Page) {
  await page.addInitScript((u) => {
    localStorage.setItem("access", "nav-test-access-token");
    localStorage.setItem("refresh", "nav-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const body = pathname.endsWith("/auth/me/") ? user : { results: [], count: 0 };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
}

const trigger = (page: Page, name: string) =>
  page.getByRole("navigation", { name: "Main navigation" }).getByRole("button", { name, exact: true });

async function expectInsideViewport(page: Page) {
  const box = await page.getByRole("menu").boundingBox();
  const vw = page.viewportSize()!.width;
  const vh = page.viewportSize()!.height;
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(vw);
  expect(box!.y + box!.height).toBeLessThanOrEqual(vh);
}

test.describe("primary navigation — desktop hover", () => {
  for (const width of [1024, 1280, 1440]) {
    test(`hover opens, switches and stays inside the viewport at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await mockShell(page);
      await page.goto("/dashboard", { waitUntil: "networkidle" });

      // Top-level row: one line, no overlap between sections and utilities, no page overflow.
      const scroller = await page.locator(".tb-nav-scroller").boundingBox();
      const utilities = await page.locator(".tb-nav__utilities").boundingBox();
      expect(scroller!.x + scroller!.width).toBeLessThanOrEqual(utilities!.x + 1);
      const lastTrigger = await trigger(page, "Masters").boundingBox();
      expect(lastTrigger!.x + lastTrigger!.width).toBeLessThanOrEqual(utilities!.x + 1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

      for (const name of Object.keys(MENUS)) {
        await trigger(page, name).hover();
        await expect(page.getByRole("menu")).toHaveCount(1);
        await expect(trigger(page, name)).toHaveAttribute("aria-expanded", "true");
        await expectInsideViewport(page);
      }

      // Travel from the trigger down into the dropdown: it must stay open.
      await trigger(page, "Reports").hover();
      const item = page.getByRole("menuitem", { name: "SION E132 Report" });
      const t = (await trigger(page, "Reports").boundingBox())!;
      const i = (await item.boundingBox())!;
      await page.mouse.move(t.x + t.width / 2, t.y + t.height - 2);
      await page.mouse.move(i.x + 20, i.y + i.height / 2, { steps: 12 });
      await expect(item).toBeVisible();

      // Leaving closes after the grace period.
      await page.mouse.move(width / 2, 700);
      await expect(page.getByRole("menu")).toHaveCount(0);
    });
  }

  test("every menu item navigates to its existing route and highlights it", async ({ page }) => {
    test.setTimeout(60_000); // 30 real route loads on a possibly cold dev server
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockShell(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    for (const [menu, paths] of Object.entries(MENUS)) {
      for (const path of paths) {
        // Deliberately no settle wait: hovering while the previous page is still
        // loading must work (regression for the late route-change close).
        await trigger(page, menu).hover();
        await page.locator(`[role="menu"] a[href="${path}"]`).click();
        await expect(page).toHaveURL(new RegExp(`${path.replace(/[/-]/g, "\\$&")}(\\?.*)?$`));
        await expect(page.getByRole("menu")).toHaveCount(0);
        await expect(trigger(page, menu)).toHaveClass(/is-active/);
      }
    }
  });

  test("keyboard: open, rove, switch and escape", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockShell(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await trigger(page, "Licenses").focus();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitem", { name: "Licenses", exact: true })).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitem", { name: "Auto Plan" })).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("menuitem", { name: "Allotments" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toHaveCount(0);
    await expect(trigger(page, "Operations")).toBeFocused();
  });
});

test.describe("primary navigation — touch tablet", () => {
  test.use({ hasTouch: true, viewport: { width: 1024, height: 768 } });

  test("tap toggles a menu without hover dependency", async ({ page }) => {
    await mockShell(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await trigger(page, "Reports").tap();
    await expect(page.getByRole("menu")).toBeVisible();
    await expectInsideViewport(page);
    await trigger(page, "Masters").tap();
    await expect(page.getByRole("menu")).toHaveCount(1);
    await expect(trigger(page, "Masters")).toHaveAttribute("aria-expanded", "true");
    await trigger(page, "Masters").tap();
    await expect(page.getByRole("menu")).toHaveCount(0);
    await trigger(page, "Operations").tap();
    await page.getByRole("menuitem", { name: "Trade In & Out" }).tap();
    await expect(page).toHaveURL(/\/trades$/);
  });
});

test.describe("primary navigation — mobile drawer", () => {
  for (const width of [390, 768]) {
    test(`drawer lists every destination at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await mockShell(page);
      await page.goto("/dashboard", { waitUntil: "networkidle" });
      await expect(page.locator(".tb-nav-scroller")).toBeHidden();
      await page.getByTestId("mobile-nav-toggle").click();
      const drawer = page.getByTestId("mobile-nav-drawer");
      const hrefs = await drawer.locator("a[href]").evaluateAll(as => as.map(a => a.getAttribute("href")));
      for (const path of Object.values(MENUS).flat()) expect(hrefs).toContain(path);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await drawer.getByRole("link", { name: "Bill of Entry" }).click();
      await expect(page).toHaveURL(/\/bill-of-entries$/);
      await expect(drawer).toBeHidden();
    });
  }
});
