import { expect, test, type Page, type Route } from "@playwright/test";
import { v3Fixture } from "../src/components/dashboard/fixtures";

// BOE and invoice sections: loading, populated, empty, failure, malformed and retry, in a browser.

const localUser = {
  id: 1,
  username: "visual.operator",
  first_name: "Visual",
  last_name: "Operator",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

type Scripted = {
  full: unknown;
  /** Responses for `?section=` retries, in order. `"error"` answers with HTTP 500. */
  retries?: Partial<Record<"boe_activity" | "invoice_activity", unknown[]>>;
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

async function scriptDashboard(page: Page, script: Scripted) {
  const queues: Record<string, unknown[]> = {
    boe_activity: [...(script.retries?.boe_activity ?? [])],
    invoice_activity: [...(script.retries?.invoice_activity ?? [])],
  };
  const requests: string[] = [];

  await page.addInitScript((user) => {
    localStorage.setItem("access", "visual-test-access-token");
    localStorage.setItem("refresh", "visual-test-refresh-token");
    localStorage.setItem("user", JSON.stringify(user));
  }, localUser);

  await page.route((url) => url.pathname.startsWith("/api/"), async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/auth/me/")) {
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(localUser) });
      return;
    }
    if (url.pathname.endsWith("/dashboard/")) {
      const section = url.searchParams.get("section") as keyof typeof queues | null;
      requests.push(section ? `section:${section}` : "full");
      if (!section) {
        await route.fulfill({ contentType: "application/json", body: JSON.stringify(script.full) });
        return;
      }
      const next = queues[section]?.shift();
      if (next === undefined || next === "error") {
        await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: "boom" }) });
        return;
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ meta: v3Fixture.meta, [section as string]: next }),
      });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });

  return requests;
}

const SECTION_FAILED = "This section could not be loaded. Check the connection, then retry";

test.describe("dashboard BOE and invoice sections", () => {
  test("both sections render real rows from one dashboard request", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const requests = await scriptDashboard(page, { full: v3Fixture });

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByRole("table", { name: "Bills of entry" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeVisible();
    expect(requests).toEqual(["full"]);
    expect(pageErrors).toEqual([]);
  });

  test("a BOE failure is isolated, and Retry refetches only the BOE section", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const requests = await scriptDashboard(page, {
      full: { ...clone(v3Fixture), boe_activity: { error: SECTION_FAILED } },
      retries: { boe_activity: [clone(v3Fixture.boe_activity)] },
    });

    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(page.getByText(SECTION_FAILED)).toBeVisible();
    await expect(page.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeVisible();

    await page.getByRole("button", { name: "Retry BOE activity" }).click();

    await expect(page.getByRole("table", { name: "Bills of entry" })).toBeVisible();
    expect(requests).toEqual(["full", "section:boe_activity"]);
    expect(pageErrors).toEqual([]);
  });

  test("a malformed invoice section is a contract error; BOE still renders", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const malformed = clone(v3Fixture);
    malformed.invoice_activity.recent = "not a list";
    await scriptDashboard(page, { full: malformed });

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByText(/did not match the expected format/)).toBeVisible();
    await expect(page.getByRole("table", { name: "Bills of entry" })).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test("an empty invoice list is an empty state, never an error", async ({ page }) => {
    const empty = clone(v3Fixture);
    empty.invoice_activity = { ...empty.invoice_activity, total: 0, recent: [] };
    await scriptDashboard(page, { full: empty });

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByText("No recent invoices")).toBeVisible();
    await expect(page.getByText(/could not be loaded/)).toHaveCount(0);
  });

  test("a failed invoice retry stays in its error state, then recovers on the next retry", async ({ page }) => {
    // The shared API client retries a failed GET twice, with backoff. A retry that keeps failing
    // therefore reaches the server three times before the section shows its error.
    const requests = await scriptDashboard(page, {
      full: { ...clone(v3Fixture), invoice_activity: { error: SECTION_FAILED } },
      retries: { invoice_activity: ["error", "error", "error", clone(v3Fixture.invoice_activity)] },
    });

    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Retry Invoice activity" }).click();
    await expect(page.getByRole("button", { name: "Retry Invoice activity" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("No recent invoices")).toHaveCount(0);

    await page.getByRole("button", { name: "Retry Invoice activity" }).click();
    await expect(page.getByRole("table", { name: "Recent invoices with outstanding amounts" })).toBeVisible();
    expect(requests).toEqual([
      "full",
      "section:invoice_activity",
      "section:invoice_activity",
      "section:invoice_activity",
      "section:invoice_activity",
    ]);
  });
});
