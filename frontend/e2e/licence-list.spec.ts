import { expect, test, type BrowserContext, type Page, type Request } from "@playwright/test";

/**
 * Licence listing — browser verification of the target URL.
 *
 * Opt-in (`LM_REAL_E2E=1`) because it signs in to a real backend.  Every
 * action here is read-only: filter, paginate, reload, navigate back.  Nothing
 * saves, deletes or exports, so it is safe on a local development database.
 *
 * The purchase-status assertions read the authoritative list from
 * `/api/masters/purchase-statuses/` instead of hard-coding labels, because
 * the ids in the target URL are not all present in every database.  An id the
 * backend does not know must render as "Unknown #<id>".
 */
let session: { cookies: Parameters<BrowserContext["addCookies"]>[0]; origins: { origin: string; localStorage: { name: string; value: string }[] }[] } | null = null;

/** Restores the signed-in session captured once in beforeAll (sign-ins are throttled by the API). */
async function restoreSession(page: Page) {
  if (!session) throw new Error("session not captured");
  await page.context().addCookies(session.cookies);
  await page.addInitScript((origins) => {
    const entry = origins.find((o) => o.origin === location.origin);
    for (const item of entry?.localStorage ?? []) localStorage.setItem(item.name, item.value);
  }, session.origins);
}

const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const TARGET_QUERY = "flags__is_null=False&is_expired=False&page=1&purchase_status=11%2C10%2C1%2C2%2C4%2C5%2C7";
const TARGET_IDS = [1, 2, 4, 5, 7, 10, 11];
const BASELINE_QUERY = "flags__is_null=False&is_expired=False&page=1&page_size=25";

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const username = page.locator("#login-username");
  const password = page.locator("#login-password");
  await expect(username).toBeVisible();
  // Wait for hydration: fill can be swallowed by a form that is not yet interactive.
  await expect(async () => {
    await username.fill(process.env.LM_USERNAME || "hardik");
    await password.fill(process.env.LM_PASSWORD || "admin@123");
    await expect(username).toHaveValue(process.env.LM_USERNAME || "hardik");
  }).toPass({ timeout: 10_000 });
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
}

async function authGet<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(async (url) => {
    const access = localStorage.getItem("access");
    const response = await fetch(`/api/${url}`, {
      headers: access ? { Authorization: `Bearer ${access}` } : {},
    });
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    return response.json();
  }, path);
}

type Status = { id: number; label: string; is_active: boolean };

async function loadStatuses(page: Page): Promise<Map<number, Status>> {
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  const body = await authGet<{ results?: Status[] } | Status[]>(page, "masters/purchase-statuses/?page_size=200");
  const rows = Array.isArray(body) ? body : body.results ?? [];
  return new Map(rows.map((row) => [row.id, row]));
}

function listRequests(requests: Request[]) {
  return requests.filter((request) => new URL(request.url()).pathname === "/api/licenses/");
}

/** Records every licence-list request issued while `action` runs. */
async function countListRequests(page: Page, action: () => Promise<void>): Promise<number> {
  const seen: Request[] = [];
  const listener = (request: Request) => seen.push(request);
  page.on("request", listener);
  try {
    await action();
    await page.waitForTimeout(1200);
  } finally {
    page.off("request", listener);
  }
  return listRequests(seen).length;
}

async function waitForResults(page: Page) {
  await expect(page.getByTestId("licence-result-count")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Updating…")).toHaveCount(0, { timeout: 15_000 });
}

function apiUrl(page: Page) {
  return new URL(page.url());
}

test.describe("licence listing — target URL", () => {
  test.skip(!realBackendEnabled, "Requires a local backend; opt in with LM_REAL_E2E=1.");
  test.describe.configure({ mode: "serial" });
  // The API throttles sign-ins, so authenticate once and reuse the saved session.
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    await signIn(await context.newPage());
    session = await context.storageState();
    await context.close();
  });

  test("loads every filter from the URL and shows truthful results", async ({ page }, testInfo) => {
    await restoreSession(page);
    const statuses = await loadStatuses(page);

    const requests: Request[] = [];
    page.on("request", (request) => requests.push(request));
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    // Item 12 — no duplicate or runaway requests for one page load.
    expect(listRequests(requests).length).toBeLessThanOrEqual(2);

    const filters = page.getByTestId("licence-filters");
    await expect(filters.getByRole("radiogroup", { name: "Flags is null" }).getByRole("radio", { name: "No", exact: true })).toBeChecked();
    await expect(filters.getByRole("radiogroup", { name: "Licence status" }).getByRole("radio", { name: "Not expired", exact: true })).toBeChecked();

    // Item 1 — every id in the URL is shown: its label, or "Unknown #id".
    for (const id of TARGET_IDS) {
      const label = statuses.get(id)?.label;
      const expected = label ?? `Unknown #${id}`;
      await expect(page.getByTestId("licence-filter-chip").filter({ hasText: expected })).toHaveCount(1);
    }

    // Item 2 — the API count matches the visible count for the same query.
    const apiCount = await authGet<{ count: number }>(page, `licenses/?${TARGET_QUERY}&page_size=25`);
    await expect(page.getByTestId("licence-result-count")).toContainText(apiCount.count.toLocaleString("en-IN"));

    await page.screenshot({ path: testInfo.outputPath("target-url.png"), fullPage: false });
  });

  test("removing one purchase status keeps the other values and the rest of the filters", async ({ page }) => {
    await restoreSession(page);
    const statuses = await loadStatuses(page);
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    const removed = 11;
    const label = statuses.get(removed)?.label ?? `Unknown #${removed}`;
    await countListRequests(page, async () => {
      await page.getByRole("button", { name: `Remove Purchase status: ${label}` }).click();
      await waitForResults(page);
    });

    const params = apiUrl(page).searchParams;
    expect(params.get("purchase_status")?.split(",").map(Number).sort((a, b) => a - b)).toEqual(
      TARGET_IDS.filter((id) => id !== removed),
    );
    expect(params.get("flags__is_null")).toBe("False");
    expect(params.get("is_expired")).toBe("False");
    expect(params.get("page")).toBe("1");
  });

  test("page change keeps filters; filter change resets to page 1", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    const next = page.getByRole("button", { name: /next page/i });
    if (await next.isEnabled().catch(() => false)) {
      await next.click();
      await waitForResults(page);
      expect(apiUrl(page).searchParams.get("page")).toBe("2");
      expect(apiUrl(page).searchParams.get("flags__is_null")).toBe("False");
      expect(apiUrl(page).searchParams.get("purchase_status")).toBe("1,2,4,5,7,10,11");
    }

    await page.getByRole("radiogroup", { name: "Licence status" }).getByRole("radio", { name: "Expired", exact: true }).click();
    await waitForResults(page);
    expect(apiUrl(page).searchParams.get("page")).toBe("1");
    expect(apiUrl(page).searchParams.get("is_expired")).toBe("True");
  });

  test("reload and browser back restore filter state", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForResults(page);
    expect(apiUrl(page).searchParams.get("purchase_status")).toBe("1,2,4,5,7,10,11");

    // A committed change pushes a history entry; Back must return to the prior filter state.
    await page.getByRole("radiogroup", { name: "Licence status" }).getByRole("radio", { name: "All", exact: true }).click();
    await waitForResults(page);
    expect(apiUrl(page).searchParams.get("is_expired")).toBe("all");

    await page.goBack();
    await waitForResults(page);
    expect(apiUrl(page).searchParams.get("is_expired")).toBe("False");
  });

  test("clear all returns to the baseline view and resets the page", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    await page.getByTestId("licence-filters-clear").click();
    await waitForResults(page);

    const params = apiUrl(page).searchParams;
    expect(params.get("is_expired")).toBe("False");
    expect(params.get("flags__is_null")).toBe("False");
    expect(params.get("purchase_status")).toBeNull();
    expect(params.get("page")).toBe("1");
    expect([...apiUrl(page).searchParams.entries()].sort()).toEqual([...new URLSearchParams(BASELINE_QUERY).entries()].sort());
  });

  test("a single committed change issues exactly one list request", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${BASELINE_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    const count = await countListRequests(page, async () => {
      await page.getByRole("radiogroup", { name: "Flags is null" }).getByRole("radio", { name: "Yes", exact: true }).click();
      await waitForResults(page);
    });
    expect(count).toBe(1);
  });

  test("typing in search does not request on each keystroke", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${BASELINE_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    const search = page.getByLabel("Search licences");
    await search.click();
    await expect(search).toBeFocused();
    const count = await countListRequests(page, async () => {
      await search.pressSequentially("ZZZQQQ", { delay: 60 });
      await waitForResults(page);
    });
    expect(count).toBe(1);
    expect(apiUrl(page).searchParams.get("search")).toBe("ZZZQQQ");
  });

  test("a stale response never overwrites a newer filter result", async ({ page }) => {
    await restoreSession(page);
    await page.goto(`/licenses?${BASELINE_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    // Hold back the first licence request triggered by the next change so it resolves last.
    let delayed = false;
    await page.route("**/api/licenses/**", async (route) => {
      if (!delayed && route.request().url().includes("flags__is_null=True")) {
        delayed = true;
        await new Promise((resolve) => setTimeout(resolve, 2500));
      }
      await route.continue();
    });

    await page.getByRole("radiogroup", { name: "Flags is null" }).getByRole("radio", { name: "Yes", exact: true }).click();
    await page.getByRole("radiogroup", { name: "Flags is null" }).getByRole("radio", { name: "No", exact: true }).click();
    await waitForResults(page);
    await page.waitForTimeout(3000);

    const finalCount = await authGet<{ count: number }>(page, `licenses/?${BASELINE_QUERY}&page_size=25`);
    await expect(page.getByTestId("licence-result-count")).toContainText(finalCount.count.toLocaleString("en-IN"));
    await page.unroute("**/api/licenses/**");
  });

  test("visible filter controls share their column width and the compact control height", async ({ page }, testInfo) => {
    await restoreSession(page);
    await page.goto(`/licenses?${TARGET_QUERY}`, { waitUntil: "domcontentloaded" });
    await waitForResults(page);

    const measurements = await page.evaluate(() => {
      const panel = document.querySelector<HTMLElement>('[data-testid="licence-filters"]');
      if (!panel) return null;
      const controls = [...panel.querySelectorAll<HTMLElement>("input:not([type=hidden]), [role=radiogroup]")];
      return {
        panelWidth: Math.round(panel.getBoundingClientRect().width),
        controls: controls
          .map((el) => {
            // react-select renders a tiny inner <input>: measure its control box.  Radio buttons use their group.
            const box = (el.closest("[class*=control]") ?? el).getBoundingClientRect();
            return { name: el.getAttribute("aria-label") ?? el.tagName, width: Math.round(box.width), height: Math.round(box.height) };
          })
          .filter((control) => control.width > 0),
      };
    });
    expect(measurements).not.toBeNull();
    console.log("licence-list control measurements", JSON.stringify(measurements));
    testInfo.annotations.push({ type: "measurement", description: JSON.stringify(measurements) });
    expect(measurements!.controls.length).toBeGreaterThan(3);
    for (const control of measurements!.controls) {
      expect(control.width, control.name).toBeGreaterThan(120);
      expect(Math.abs(control.height - 34), control.name).toBeLessThanOrEqual(1);
    }
    expect(measurements!.panelWidth).toBeGreaterThan(800);
  });
});
