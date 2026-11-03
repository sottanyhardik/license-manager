import { expect, test, type Page } from "@playwright/test";
import { v3Fixture } from "../src/components/dashboard/fixtures";

// Regression: a BOE payload without `pending_mapping` crashed the page with
// "Cannot read properties of undefined (reading 'filter')". The page must now
// render, show the BOE card's contract error, and throw no uncaught exception.

const localUser = {
  id: 1,
  username: "visual.operator",
  first_name: "Visual",
  last_name: "Operator",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

async function mockDashboard(page: Page, payload: unknown) {
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
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(payload) });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
}

function withBoe(mutate: (boe: Record<string, unknown>) => void) {
  const payload = JSON.parse(JSON.stringify(v3Fixture));
  mutate(payload.boe_activity);
  return payload;
}

test.describe("dashboard BOE activity contract", () => {
  test("renders the BOE table for a valid payload without an uncaught exception", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await mockDashboard(page, v3Fixture);

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Bills of entry" })).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test("keeps the page alive when the pending list is missing and reports the BOE card as a contract error", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await mockDashboard(
      page,
      withBoe((boe) => {
        delete boe.pending_mapping;
      }),
    );

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("BOE activity")).toBeVisible();
    await expect(page.getByText(/did not match the expected format/)).toBeVisible();
    await expect(page.getByText("Attention required")).toBeVisible();
    expect(pageErrors).toEqual([]);
  });

  test("shows the empty states when every BOE list is empty", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await mockDashboard(
      page,
      withBoe((boe) => {
        boe.recent = [];
        boe.pending_mapping = [];
        boe.recently_modified = [];
      }),
    );

    await page.goto("/dashboard", { waitUntil: "networkidle" });

    await expect(page.getByText("No recent BOE records.")).toBeVisible();
    expect(pageErrors).toEqual([]);
  });
});
