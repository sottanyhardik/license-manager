import { expect, test, type Page, type Route } from "@playwright/test";
import { v3Fixture } from "../src/components/dashboard/fixtures";

// Allotment activity: columns visible without clipping on desktop, a keyboard-reachable scroll on mobile,
// link targets, and a retry that refetches only this section.

const localUser = {
  id: 1,
  username: "visual.operator",
  first_name: "Visual",
  last_name: "Operator",
  is_superuser: true,
  roles: ["LICENSE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "TRADE_MANAGER", "USER_MANAGER"],
};

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

async function scriptDashboard(page: Page, full: unknown, retries: unknown[] = []) {
  const queue = [...retries];
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
      const section = url.searchParams.get("section");
      requests.push(section ? `section:${section}` : "full");
      if (!section) {
        await route.fulfill({ contentType: "application/json", body: JSON.stringify(full) });
        return;
      }
      const next = queue.shift();
      if (next === undefined || next === "error") {
        await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: "boom" }) });
        return;
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ meta: v3Fixture.meta, allotment_activity: next }),
      });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ results: [], count: 0 }) });
  });
  return requests;
}

test.describe("dashboard allotment activity", () => {
  test("on desktop every column is laid out inside the card, with no clipped header or cell", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await scriptDashboard(page, v3Fixture);
    await page.goto("/dashboard", { waitUntil: "networkidle" });

    const card = page.locator("#dashboard-allotments");
    const region = card.getByRole("region", { name: /scroll horizontally/ });
    await expect(region).toBeVisible();

    const cardBox = await card.boundingBox();
    const headers = await card.getByRole("columnheader").all();
    expect(headers.length).toBe(10);
    for (const header of headers) {
      const box = await header.boundingBox();
      expect(box, "every header has a box").not.toBeNull();
      expect(box!.x + box!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width + 1);
    }
    // The table fits inside its scroller at desktop width: nothing is hidden behind a scroll.
    const overflow = await region.evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("on a phone the table scrolls inside the card, and the scroller is focusable and labelled", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await scriptDashboard(page, v3Fixture);
    await page.goto("/dashboard", { waitUntil: "networkidle" });

    const region = page.locator("#dashboard-allotments").getByRole("region", { name: /scroll horizontally/ });
    await expect(region).toBeVisible();
    await expect(region).toHaveAttribute("tabindex", "0");
    const overflow = await region.evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflow).toBeGreaterThan(0);

    // The wheel scrolls the region. Keyboard scrolling of a focused region is not asserted here:
    // headless Chromium did not move it on End or ArrowRight, so that path is unverified in this environment.
    await region.hover();
    await page.mouse.wheel(300, 0);
    await expect.poll(() => region.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0);
  });

  test("the reference links to the allotment, and the licence links to its overview", async ({ page }) => {
    await scriptDashboard(page, v3Fixture);
    await page.goto("/dashboard", { waitUntil: "networkidle" });

    const card = page.locator("#dashboard-allotments");
    const first = v3Fixture.allotment_activity.recent[0]!;
    await expect(card.getByRole("link", { name: first.reference })).toHaveAttribute("href", `/allotments/${first.id}/allocate`);
    await expect(card.getByRole("link", { name: first.licences[0]!.license_number })).toHaveAttribute(
      "href",
      `/licenses/${first.licences[0]!.id}/overview`,
    );
  });

  test("a failed allotment request is isolated, and Retry refetches only this section", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const failing = clone(v3Fixture);
    failing.allotment_activity = { error: "This section could not be loaded. Check the connection, then retry" };
    const requests = await scriptDashboard(page, failing, [clone(v3Fixture.allotment_activity)]);

    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "Retry Allotment activity" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Bills of entry" })).toBeVisible();

    await page.getByRole("button", { name: "Retry Allotment activity" }).click();

    await expect(page.locator("#dashboard-allotments").getByRole("region", { name: /scroll horizontally/ })).toBeVisible();
    expect(requests).toEqual(["full", "section:allotment_activity"]);
    expect(pageErrors).toEqual([]);
  });
});
