import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 1, username: "shell.operator", first_name: "Shell", last_name: "Operator", is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

async function mockApi(page: Page) {
  await page.addInitScript((u) => {
    localStorage.setItem("access", "t");
    localStorage.setItem("refresh", "t");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p.endsWith("/auth/me/")) return route.fulfill({ contentType: "application/json", body: JSON.stringify(user) });
    if (p.endsWith("/dashboard/")) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          license_stats: { total: 42, active: 36, expired: 2, null_dfia: 1, expiring_soon: 3 },
          allotment_stats: { total: 18, recent: [] },
          boe_stats: { total: 27, pending_invoices: 4, recent: [] },
          expiring_licenses: [], boe_monthly_trend: [],
        }),
      });
    }
    return route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

const VIEWPORTS = [
  { w: 1440, h: 900 }, { w: 1366, h: 768 }, { w: 768, h: 1024 }, { w: 390, h: 844 },
];
const PAGES = [
  { name: "dashboard", path: "/dashboard", quick: true, fab: true },
  { name: "licenses", path: "/licenses", quick: false, fab: true },
  { name: "boe", path: "/bill-of-entries", quick: false, fab: true },
  { name: "boe-create", path: "/bill-of-entries/create", quick: false, fab: false },
];

test.describe("ERP shell visual", () => {
  for (const pg of PAGES) {
    test(`${pg.name}: quick bar / FAB / overflow`, async ({ page }, testInfo) => {
      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        const t = m.text();
        if (m.type() === "error" && !t.includes("favicon") && !t.includes("Failed to load resource")) errors.push(t);
      });
      await mockApi(page);
      for (const v of VIEWPORTS) {
        await page.setViewportSize({ width: v.w, height: v.h });
        await page.goto(pg.path, { waitUntil: "networkidle" });
        const quick = page.getByRole("contentinfo", { name: "Quick actions and status" });
        if (pg.quick) await expect(quick).toBeVisible();
        else await expect(quick).toHaveCount(0);
        const fab = page.getByRole("button", { name: "Open tasks" });
        if (pg.fab) {
          await expect(fab).toBeVisible();
          const box = await fab.boundingBox();
          expect(box!.width).toBeLessThanOrEqual(48);
        } else {
          await expect(fab).toHaveCount(0);
        }
        const fixed = await page.evaluate(() => Array.from(document.body.querySelectorAll("*"))
          .filter((el) => getComputedStyle(el).position === "fixed" && el.getBoundingClientRect().width > 0)
          .map((el) => `${el.tagName}.${String(el.className).slice(0, 40)}|${el.getAttribute("aria-label")}`));
        console.log(`${pg.name}@${v.w} fixed:`, JSON.stringify(fixed));
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        expect(overflow, `${pg.name}@${v.w}`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `test-results/erp-shell/${pg.name}-${v.w}.png`, fullPage: false });
        void testInfo;
      }
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.evaluate(() => localStorage.setItem("theme", "dark"));
      await page.goto(pg.path, { waitUntil: "networkidle" });
      await page.screenshot({ path: `test-results/erp-shell/${pg.name}-1440-dark.png` });
      expect(errors).toEqual([]);
    });
  }
});
