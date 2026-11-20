import { expect, test, type Page, type Request } from "@playwright/test";

/**
 * Reports menu audit (local mock, no backend): every Reports / Licence status /
 * SION norms entry opens its page, applies its default filter, keeps the filter
 * in the URL across refresh/back/forward, sends the right API request, shows its
 * loading / empty state, stays highlighted, and respects the role gates.
 */
const baseUser = { id: 1, username: "reports.audit", first_name: "Reports", last_name: "Audit", is_superuser: false };
const MANAGER = { ...baseUser, roles: ["LICENSE_MANAGER", "REPORT_VIEWER"] };
const REPORT_VIEWER = { ...baseUser, roles: ["REPORT_VIEWER"] };
const LICENCE_VIEWER = { ...baseUser, roles: ["LICENSE_VIEWER"] };

type User = typeof MANAGER;

/** [menu label, path, page heading (null = any h1)] in menu order. */
const ENTRIES: [string, string, string | null][] = [
  ["License Downloads", "/license-ledger/download-requests", "License Download Requests"],
  ["Item Pivot Report", "/reports/item-pivot", "Item Pivot Report"],
  ["Item Report", "/reports/item-report", "Item Report"],
  ["Planned Report", "/reports/planned-report", "Planned Report"],
  ["Purchase & Profit Report", "/reports/license-purchase-profit", null],
  ["Expiring Licenses", "/reports/expiring-licenses", "Expiring Licenses Report"],
  ["Active Licenses", "/reports/active-licenses", "Active Licenses Report"],
  ["Download License", "/reports/download-license", "Download License"],
  ["SION E1 Report", "/reports/parle/sion-e1", "SION Norm E1 - Parle Report"],
  ["SION E5 Report", "/reports/parle/sion-e5", "SION Norm E5 - Parle Report"],
  ["SION E126 Report", "/reports/parle/sion-e126", "SION Norm E126 - Parle Report"],
  ["SION E132 Report", "/reports/parle/sion-e132", "SION Norm E132 - Parle Report"],
];

async function mockShell(page: Page, user: User = MANAGER, { sionDelayMs = 0 } = {}) {
  const requests: string[] = [];
  await page.addInitScript((u) => {
    localStorage.setItem("access", "reports-test-access-token");
    localStorage.setItem("refresh", "reports-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(u));
  }, user);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const url = new URL(route.request().url());
    requests.push(`${url.pathname}${url.search}`);
    if (url.pathname.endsWith("/auth/me/")) return route.fulfill({ json: user });
    if (url.pathname === "/api/licenses/active-dfia-report/") {
      if (sionDelayMs) await new Promise(resolve => setTimeout(resolve, sionDelayMs));
      return route.fulfill({ json: { groups: [] } });
    }
    // Real shape of ItemReportView / planned report (backend/apps/license/api/views/item_report.py).
    if (/^\/api\/reports\/(item|planned)-report\/$/.test(url.pathname)) {
      return route.fulfill({ json: { items: [], total_items: 0 } });
    }
    if (/^\/api\/reports\/(expiring|active)-licenses\/$/.test(url.pathname)) {
      return route.fulfill({
        status: 200,
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        body: Buffer.from("PK-mock-xlsx"),
      });
    }
    return route.fulfill({ json: { results: [], count: 0 } });
  });
  return requests;
}

const nav = (page: Page) => page.getByRole("navigation", { name: "Main navigation" });
const reportsTrigger = (page: Page) => nav(page).getByRole("button", { name: "Reports", exact: true });
const query = (page: Page) => new URL(page.url()).searchParams;
async function menuHrefs(page: Page) {
  await reportsTrigger(page).hover();
  await expect(page.getByRole("menu")).toBeVisible();
  return page.locator('[role="menu"] a[href]').evaluateAll(as => as.map(a => a.getAttribute("href")));
}

test.describe("Reports menu — routes, highlighting, headings", () => {
  test("every remaining entry opens its own page and is highlighted", async ({ page }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockShell(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });

    const pageErrors: string[] = [];
    page.on("pageerror", error => pageErrors.push(`${new URL(page.url()).pathname}: ${error.message}`));
    expect(await menuHrefs(page)).toEqual(ENTRIES.map(([, path]) => path));

    page.on("console", msg => { if (msg.type() === "error") pageErrors.push(`${new URL(page.url()).pathname}: console: ${msg.text()}`); });
    for (const [label, path, heading] of ENTRIES) await test.step(`${label} → ${path}`, async () => {
      await reportsTrigger(page).hover();
      await page.getByRole("menuitem", { name: label, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`${path.replace(/[/-]/g, "\\$&")}(\\?.*)?$`));
      const h1 = page.getByRole("heading", { level: 1 });
      if (heading) await expect(h1).toHaveText(heading);
      else await expect(h1).toBeVisible();
      await expect(reportsTrigger(page)).toHaveClass(/is-active/);
      await reportsTrigger(page).hover();
      await expect(page.getByRole("menuitem", { name: label, exact: true })).toHaveAttribute("aria-current", "page");
      await page.keyboard.press("Escape");
      await page.mouse.move(700, 850); // leave the trigger so the next hover re-opens the menu
      await expect(page.getByRole("menu")).toHaveCount(0);
      expect(pageErrors.filter(e => !e.includes("console:"))).toEqual([]);
    });
    expect(pageErrors.filter(e => !e.includes("console:"))).toEqual([]);
  });
});

test.describe("Licence status reports — default filters in the URL", () => {
  for (const [path, kind, label] of [
    ["/reports/expiring-licenses", "expiring", "Days from today"],
    ["/reports/active-licenses", "active", "Days to look back"],
  ] as const) {
    test(`${kind}: default days in URL, survives refresh, exports from the live endpoint`, async ({ page }) => {
      const requests = await mockShell(page);
      await page.goto(path, { waitUntil: "networkidle" });
      await expect.poll(() => query(page).get("days")).toBe("30");
      await expect(page.getByLabel(label)).toHaveValue("30");

      await page.getByLabel(label).fill("60");
      await expect.poll(() => query(page).get("days")).toBe("60");
      await page.reload({ waitUntil: "networkidle" });
      await expect(page.getByLabel(label)).toHaveValue("60");

      const exportRequest = page.waitForRequest((r: Request) => new URL(r.url()).pathname === `/api/reports/${kind}-licenses/`);
      await page.getByRole("button", { name: /download excel report/i }).click();
      const req = new URL((await exportRequest).url());
      expect(req.searchParams.get("format")).toBe("excel");
      expect(req.searchParams.get("days")).toBe("60");
      expect(requests.some(r => r.startsWith("/api/license/reports/"))).toBe(false);
    });
  }

  test("download-license: status + days in URL and back/forward restore them", async ({ page }) => {
    await mockShell(page);
    await page.goto("/reports/download-license", { waitUntil: "networkidle" });
    await expect.poll(() => `${query(page).get("status")}|${query(page).get("days")}`).toBe("active|365");
    const active = page.getByRole("button", { name: "Active Licenses", exact: true });
    const expiring = page.getByRole("button", { name: "Expiring Soon", exact: true });
    await expect(active).toHaveAttribute("aria-pressed", "true");

    await expiring.click();
    await expect.poll(() => query(page).get("status")).toBe("expiring");
    await expect(expiring).toHaveAttribute("aria-pressed", "true");

    await page.goBack();
    await expect.poll(() => query(page).get("status")).toBe("active");
    await expect(active).toHaveAttribute("aria-pressed", "true");
    await page.goForward();
    await expect.poll(() => query(page).get("status")).toBe("expiring");
    await expect(expiring).toHaveAttribute("aria-pressed", "true");

    await page.reload({ waitUntil: "networkidle" });
    await expect(expiring).toHaveAttribute("aria-pressed", "true");
  });
});

test.describe("SION norm reports — exact norm, URL filters, states", () => {
  for (const norm of ["E1", "E5", "E126", "E132"]) {
    test(`${norm}: requests exactly sion_norm=${norm} with default filters and shows the empty state`, async ({ page }) => {
      const requests = await mockShell(page);
      await page.goto(`/reports/parle/sion-${norm.toLowerCase()}`, { waitUntil: "networkidle" });
      await expect(page.getByText(`No records found for SION Norm ${norm}`)).toBeVisible();
      await expect.poll(() => `${query(page).get("is_expired")}|${query(page).get("is_null")}`).toBe("False|False");
      const sion = requests.filter(r => r.startsWith("/api/licenses/active-dfia-report/"));
      expect(sion).toHaveLength(1);
      const params = new URLSearchParams(sion[0].split("?")[1]);
      expect(params.get("sion_norm")).toBe(norm);
      expect(params.get("is_expired")).toBe("False");
      expect(params.get("is_null")).toBe("False");
    });
  }

  test("filters survive refresh and follow back/forward; loading state is shown", async ({ page }) => {
    const requests = await mockShell(page, MANAGER, { sionDelayMs: 600 });
    await page.goto("/reports/parle/sion-e126");
    await expect(page.getByText("Loading…")).toBeVisible();
    await expect(page.getByText("No records found for SION Norm E126")).toBeVisible();

    // The page swaps the filter card for its loading view while fetching, so click (not check) and re-query.
    await page.getByLabel("Expired").click();
    await expect.poll(() => query(page).get("is_expired")).toBe("True");
    await expect(page.getByText("No records found for SION Norm E126")).toBeVisible();
    await expect.poll(() => requests.filter(r => r.startsWith("/api/licenses/active-dfia-report/")).at(-1))
      .toBe("/api/licenses/active-dfia-report/?is_expired=True&is_null=False&sion_norm=E126");

    await page.reload();
    await expect(page.getByLabel("Expired")).toBeChecked();

    await page.goBack();
    await expect.poll(() => query(page).get("is_expired")).toBe("False");
    await expect(page.getByLabel("Active")).toBeChecked();
    await page.goForward();
    await expect.poll(() => query(page).get("is_expired")).toBe("True");
    await expect(page.getByLabel("Expired")).toBeChecked();
  });
});

test.describe("Reports menu — permissions", () => {
  test("REPORT_VIEWER sees the reports but not License Downloads (its route needs ledger roles)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockShell(page, REPORT_VIEWER);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    const hrefs = await menuHrefs(page);
    expect(hrefs).not.toContain("/license-ledger/download-requests");
    expect(hrefs).toEqual(ENTRIES.slice(1).map(([, path]) => path));
    await page.goto("/license-ledger/download-requests");
    await expect(page).toHaveURL(/\/403$/);
  });

  test("a user without report roles has no Reports menu and is sent to 403", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockShell(page, LICENCE_VIEWER);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(reportsTrigger(page)).toHaveCount(0);
    for (const path of ["/reports/expiring-licenses", "/reports/parle/sion-e1"]) {
      await page.goto(path);
      await expect(page).toHaveURL(/\/403$/);
    }
  });
});
