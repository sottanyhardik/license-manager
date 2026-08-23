import { expect, test, type Page } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

/**
 * Isolated browser coverage for the licence overview/balance entry point.
 *
 * This suite intentionally routes every API request to deterministic local
 * fixtures. It is safe to run without PostgreSQL and never contacts a shared
 * environment. The data-bearing suite remains the separate opt-in check in
 * `data-bearing.real.spec.ts`.
 */
const localUser = {
  id: 1,
  username: "balance.qa",
  first_name: "Balance",
  last_name: "QA",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "LICENSE_VIEWER", "BOE_MANAGER", "BOE_VIEWER", "TRADE_MANAGER", "TRADE_VIEWER"],
};

const overviewSummary = {
  license_number: "QA-3411008090",
  authorisation_number: "AUTH-QA-01",
  file_number: "QA-FILE-01",
  license_date: "2026-01-01",
  license_expiry_date: "2026-12-31",
  importer: "QA Importer Pvt Ltd",
  status: "Active",
  purchase_status_id: null,
  purchase_status_code: null,
  purchase_status_label: null,
  port_code: "INNSA",
  port_name: "Nhava Sheva",
  balance_cif: "400.50",
  summary: {
    total_boes: 0,
    total_allotments: 0,
    total_planned_cif: 0,
    total_cif: 1000.5,
    total_debited_cif: 0,
    total_allotted_cif: 0,
    total_balance_cif: 1000.5,
  },
};

const emptyBalanceLedger = {
  license: {
    id: 2509,
    license_number: "QA-3411008090",
    license_date: "2026-01-01",
    license_expiry_date: "2026-12-31",
    exporter: "QA Exporter Pvt Ltd",
    original_cif: 1000.5,
    original_qty: 100,
    current_balance_cif: 1000.5,
    current_balance_qty: 100,
    financial_integrity_score: 100,
    difference: 0,
  },
  financial_ledger: {
    rows: [],
    summary: {
      opening_balance: 1000.5,
      total_boe_debit: 0,
      total_allotment_debit: 0,
      total_purchase_credit: 0,
      total_trade_debit: 0,
      computed_balance: 1000.5,
      engine_balance: 1000.5,
      difference: 0,
      mismatched: false,
      tolerance: 0.01,
      has_trading_activity: false,
      has_purchase: false,
      has_sale: false,
      missing_purchase_warning: { show_warning: false, message: "" },
    },
  },
  customs_ledger: {
    rows: [],
    summary: {
      opening_balance: 1000.5,
      total_boe_cif: 0,
      remaining_after_boe: 1000.5,
      total_pending_allotment_cif: 0,
      computed_balance: 1000.5,
      engine_balance: 1000.5,
      difference: 0,
      mismatched: false,
      tolerance: 0.01,
    },
  },
  reconciliation: {
    financial_ledger_balance: 1000.5,
    customs_ledger_balance: 1000.5,
    balance_engine: 1000.5,
    difference: 0,
    tolerance: 0.01,
    matched: true,
  },
  warnings: [],
  timeline: [],
};

async function mockAuthenticatedOverview(page: Page) {
  await page.addInitScript((user) => {
    localStorage.setItem("access", "overview-qa-access-token");
    localStorage.setItem("refresh", "overview-qa-refresh-token");
    localStorage.setItem("user", JSON.stringify(user));
  }, localUser);

  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/auth/me/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(localUser) });
      return;
    }
    if (pathname.endsWith("/overview-summary/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(overviewSummary) });
      return;
    }
    if (pathname.endsWith("/balance-ledger/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(emptyBalanceLedger) });
      return;
    }
    if (pathname.endsWith("/overview-boes/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify([]) });
      return;
    }
    if (pathname.endsWith("/licenses/2509/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ export_license: [], import_license: [] }) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

async function expectNoPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
}

test.describe("licence overview balance route accessibility mock", () => {
  test("legacy balance URL redirects to the canonical overview without losing the licence id", async ({ page }) => {
    await mockAuthenticatedOverview(page);
    await page.goto("/licenses/2509/balance", { waitUntil: "networkidle" });

    await expect(page).toHaveURL(/\/licenses\/2509\/overview$/);
    await expect(page.getByRole("heading", { name: /License Overview/i })).toBeVisible();
  });

  test("overview keeps its tab navigation keyboard-accessible and contained at required viewports", async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("favicon")) {
        errors.push(message.text());
      }
    });
    await mockAuthenticatedOverview(page);

    for (const viewport of [
      { name: "desktop-1440", width: 1440, height: 900 },
      { name: "desktop-1280", width: 1280, height: 720 },
      { name: "tablet-landscape", width: 1024, height: 768 },
      { name: "tablet-portrait", width: 768, height: 1024 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto("/licenses/2509/overview", { waitUntil: "networkidle" });

      await expect(page.getByRole("heading", { name: /License Overview/i })).toBeVisible();
      const tabs = page.getByRole("tablist");
      await expect(tabs).toBeVisible();
      await expect(page.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
      await expect(page.getByText("QA-3411008090", { exact: true }).first()).toBeVisible();
      await expectNoBasicSemanticViolations(page);
      if (viewport.name === "desktop-1440" || viewport.name === "mobile") {
        await expectNoSeriousOrCriticalAxeViolations(page, "main");
      }
      await expectNoPageOverflow(page);
      await page.screenshot({ path: testInfo.outputPath(`licence-overview-${viewport.name}.png`), fullPage: true });
    }

    const overviewTab = page.getByRole("tab", { name: "Overview" });
    await overviewTab.focus();
    await expect(overviewTab).toBeFocused();
    // Use the tab's native keyboard activation rather than relying on a
    // particular roving-focus implementation detail of the tabs primitive.
    const boesTab = page.getByRole("tab", { name: "BOEs" });
    await boesTab.focus();
    await expect(boesTab).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\?tab=boes$/);
    await expectNoPageOverflow(page);
    expect(errors).toEqual([]);
  });
});
