import { expect, test, type Page } from "@playwright/test";

/**
 * REAL BACKEND — licence Edit inside the expanded licence (no edit page).
 *
 * Opt-in: `scripts/test/run_data_bearing_browser_e2e.sh e2e/licence-edit.real.spec.ts`
 * (fresh `test_*` database, `seed_browser_2509`, superuser). The licence edited is an isolated record this spec
 * creates through the API with the seeded licence's reference data (exporter, port, scheme, notification, status)
 * and no items; only `file_number` (free text, no financial effect) is changed.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const SEED_LICENCE_ID = 2509;
const RUN = Date.now().toString().slice(-6);
const LICENCE = `3499${RUN}`;

async function signIn(page: Page) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL("**/dashboard");
}

async function apiPost(page: Page, path: string, body: unknown): Promise<{ status: number; body: Record<string, unknown> }> {
    return page.evaluate(async ([url, payload]) => {
        const r = await fetch(`/api/${url}`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access")}` },
            body: JSON.stringify(payload),
        });
        return { status: r.status, body: await r.json().catch(() => ({})) };
    }, [path, body] as const);
}

async function apiGet<T>(page: Page, path: string): Promise<T> {
    return page.evaluate(async url => (await fetch(`/api/${url}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
    })).json(), path);
}

test.describe("Licence edit inline (real backend)", () => {
    test.skip(!realBackendEnabled, "Requires the isolated local browser harness; never points at a shared database.");

    test("edit, validation error, cancel and save happen inside the expanded licence; list context kept; audited", async ({ page }, testInfo) => {
        await signIn(page);
        await page.setViewportSize({ width: 1440, height: 900 });
        const fk = (v: unknown) => (v && typeof v === "object" ? (v as { id: number }).id : v);
        const seed = await apiGet<Record<string, unknown>>(page, `licenses/${SEED_LICENCE_ID}/`);
        const created = await apiPost(page, "licenses/", {
            license_number: LICENCE,
            license_date: seed.license_date,
            license_expiry_date: seed.license_expiry_date,
            exporter: fk(seed.exporter),
            port: fk(seed.port),
            scheme_code: fk(seed.scheme_code),
            notification_number: fk(seed.notification_number),
            purchase_status: fk(seed.purchase_status),
        });
        expect(created.status, JSON.stringify(created.body).slice(0, 400)).toBe(201);
        const LICENCE_ID = created.body.id as number;
        await page.goto(`/licenses?search=${LICENCE}&page=1`, { waitUntil: "networkidle" });
        const list = page.getByRole("list", { name: "Licenses" });
        await expect(list).toBeVisible();
        await list.evaluate(el => { (el as HTMLElement & { __kept?: boolean }).__kept = true; });
        const listUrl = page.url();
        const before = await apiGet<{ file_number: string | null; license_number: string }>(page, `licenses/${LICENCE_ID}/`);

        await page.getByRole("button", { name: `Expand license ${LICENCE}` }).click();
        const region = page.getByRole("region", { name: `License ${LICENCE} details` });
        await region.getByRole("button", { name: `Actions for license ${LICENCE}` }).click();
        await page.getByRole("menuitem", { name: "Edit", exact: true }).click();
        await expect(region.getByRole("tab", { name: "Edit", selected: true })).toBeVisible();
        const fileNumber = region.locator("#field-file_number");
        await expect(fileNumber).toBeVisible({ timeout: 15_000 });
        // Populated from the real record.
        await expect(region.locator("#field-license_number")).toHaveValue(before.license_number);
        await page.screenshot({ path: testInfo.outputPath("licence-edit-inline-1440.png") });

        // Server-side validation is shown in place and nothing is saved.
        await region.locator("#field-license_number").fill("");
        await region.getByRole("button", { name: "Update" }).click();
        await expect(region.getByText(/Validation Error|required|may not be blank/i).first()).toBeVisible();
        expect((await apiGet<{ license_number: string }>(page, `licenses/${LICENCE_ID}/`)).license_number).toBe(before.license_number);

        // Cancel discards and returns to Overview.
        await region.getByRole("button", { name: "Cancel" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();

        // Save a real change.
        await region.getByRole("tab", { name: "Edit" }).click();
        const value = `E2E-FN-${RUN}`;
        await region.locator("#field-file_number").fill(value);
        await region.getByRole("button", { name: "Update" }).click();
        await expect(region.getByRole("tab", { name: "Overview", selected: true })).toBeVisible();
        await expect.poll(async () => (await apiGet<{ file_number: string | null }>(page, `licenses/${LICENCE_ID}/`)).file_number).toBe(value);
        expect((await apiGet<{ license_number: string }>(page, `licenses/${LICENCE_ID}/`)).license_number).toBe(before.license_number);

        // Same list, same URL (filters/page), no navigation.
        expect(await list.evaluate(el => (el as HTMLElement & { __kept?: boolean }).__kept === true), "same list node").toBe(true);
        expect(new URL(page.url()).pathname).toBe(new URL(listUrl).pathname);
        expect(new URL(page.url()).searchParams.get("page")).toBe("1");

        // Audit: the PATCH/PUT is in the activity log (written on a background thread).
        await expect.poll(async () => (await apiGet<unknown[]>(page,
            `masters/activity-logs/?changes_only=1&endpoint=${encodeURIComponent(`/api/licenses/${LICENCE_ID}/`)}`)).length).toBeGreaterThan(0);
    });
});
