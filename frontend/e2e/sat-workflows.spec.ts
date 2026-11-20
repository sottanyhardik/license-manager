import { expect, test, type Browser, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const EVID = process.env.SAT_OUT || path.join(os.homedir(), "lm_sat_evidence", "e2e");
fs.mkdirSync(path.join(EVID, "shots"), { recursive: true });

/**
 * SAT Phase 4/5 - integration workflows + UI behaviour on the seeded DISPOSABLE db (seed_browser_2509 via
 * scripts/test/run_data_bearing_browser_e2e.sh). Writes only to the disposable test_* database. Real auth is used
 * throughout (superuser from the seed; a viewer created through the real user API). Network mocks (page.route) are
 * used only for 500 / empty-state probes of the UI.
 * Observations go to ${EVID}/workflows.jsonl.
 */
const real = process.env.LM_REAL_E2E === "1";
const OUT = path.join(EVID, "workflows.jsonl");
const SHOTS = path.join(EVID, "shots");
const RUN = process.env.SAT_RUN || "604001"; // fixed per harness run (fresh DB each run); limits repeated logins (login is rate-limited)
const VIEWER = { username: `sat_viewer_${RUN}`, password: `Vw!${RUN}xQ9pL2` };
const AUTH = path.join(EVID, ".sat-wf-auth.json");
const AUTH_OK = path.join(EVID, ".sat-wf-auth.ok");

const note = (id: string, data: Record<string, unknown>) => fs.appendFileSync(OUT, JSON.stringify({ id, ...data }) + "\n");

async function signIn(page: Page, u = process.env.LM_USERNAME || "hardik", p = process.env.LM_PASSWORD || "admin@123") {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.locator("#login-username").fill(u);
  await page.locator("#login-password").fill(p);
  for (let attempt = 0; attempt < 4; attempt++) {
    await page.getByRole("button", { name: "Sign in" }).click();
    try { await page.waitForURL("**/dashboard", { timeout: 8000 }); return; } catch {
      if (await page.getByText(/throttled/i).count()) await page.waitForTimeout(11_000); else throw new Error("login did not reach dashboard: " + page.url());
    }
  }
  await page.waitForURL("**/dashboard", { timeout: 8000 });
}
async function api<T = any>(page: Page, method: string, path: string, body?: unknown): Promise<{ status: number; body: T }> {
  return page.evaluate(async ([m, url, payload]) => {
    const r = await fetch(`/api/${url}`, {
      method: m as string,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access")}` },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    return { status: r.status, body: await r.json().catch(() => ({})) };
  }, [method, path, body] as const) as Promise<{ status: number; body: T }>;
}
async function viewerPage(browser: Browser): Promise<Page> {
  const ctx = await browser.newContext({ storageState: undefined, viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await signIn(p, VIEWER.username, VIEWER.password);
  return p;
}
const overflow = (page: Page) => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - window.innerWidth));

test.describe("SAT workflows (disposable DB)", () => {
  test.skip(!real, "Requires the isolated data-bearing harness.");
  test.use({ viewport: { width: 1440, height: 900 }, storageState: AUTH });
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const p = await ctx.newPage();
    await signIn(p);
    if (fs.existsSync(AUTH_OK)) { await ctx.close(); return; }
    const made = await api(p, "POST", "auth/users/", {
      username: VIEWER.username, password: VIEWER.password, email: `${VIEWER.username}@example.invalid`,
      is_active: true, roles: ["LICENSE_VIEWER", "INCENTIVE_LICENSE_VIEWER"],
    });
    note("SETUP-viewer", { status: made.status });
    await ctx.storageState({ path: AUTH });
    fs.writeFileSync(AUTH_OK, "1");
    await ctx.close();
  });

  // ---------------- lists: open / search / filter / sort / select / refresh ----------------
  const LISTS = [
    { id: "licences", path: "/licenses", term: "3411008090" },
    { id: "allotments", path: "/allotments", term: "E2E-ALLOTMENT-2509" },
    { id: "boe", path: "/bill-of-entries", term: "E2E" },
    { id: "trades", path: "/trades", term: "E2E" },
    { id: "masters-companies", path: "/masters/companies", term: "E2E Browser" },
    { id: "masters-item-names", path: "/masters/item-names", term: "E2E" },
    { id: "admin-users", path: "/admin/users", term: "hardik" },
  ];
  for (const l of LISTS) {
    test(`list ${l.id}: search, filters, sort, select, refresh`, async ({ page }) => {
      await page.goto(l.path, { waitUntil: "networkidle" });
      const search = page.locator("input[type=search], [role=searchbox], input[placeholder*='Search' i]").first();
      const hasSearch = (await search.count()) > 0;
      const rowSel = "tbody tr, [role=listitem], ul[aria-label] > li";
      const before = await page.locator(rowSel).count();
      let afterSearch = -1, afterMiss = -1, persisted = "";
      if (hasSearch) {
        await search.fill(l.term);
        await page.waitForTimeout(1200);
        await page.waitForLoadState("networkidle");
        afterSearch = await page.locator(rowSel).count();
        await search.fill("zzz-no-such-record-" + RUN);
        await page.waitForTimeout(1200);
        await page.waitForLoadState("networkidle");
        afterMiss = await page.locator(rowSel).count();
        const emptyMsg = await page.getByText(/no (results|records|data|items|licen|allot|trades|bill)/i).first().isVisible().catch(() => false);
        note(`LIST-${l.id}-emptystate`, { afterMiss, emptyMsg });
        await search.fill(l.term);
        await page.waitForTimeout(1200);
        persisted = page.url();
        await page.reload({ waitUntil: "networkidle" });
        const v = await search.inputValue().catch(() => "");
        note(`LIST-${l.id}-refresh`, { urlBefore: persisted, urlAfter: page.url(), searchValueAfterReload: v, searchPersisted: v === l.term });
      }
      const filtersBtn = page.getByRole("button", { name: /^Filters/ });
      let filtersOpens: boolean | null = null;
      if (await filtersBtn.count()) { await filtersBtn.first().click(); filtersOpens = await page.locator("section[aria-label='Filters'], [role=dialog]").first().isVisible().catch(() => false); await page.keyboard.press("Escape"); }
      const sortCtl = await page.locator("th[aria-sort], [aria-label*='Sort' i], button:has-text('Sort')").count();
      const checkboxes = await page.locator("input[type=checkbox], [role=checkbox]").count();
      const pager = await page.getByRole("button", { name: /next|prev|page/i }).count();
      const addNew = await page.getByRole("link", { name: /Add New|New|Create/i }).count() + await page.getByRole("button", { name: /Add New|New|Create/i }).count();
      note(`LIST-${l.id}`, { hasSearch, rowsBefore: before, afterSearch, afterMiss, filtersBtn: await filtersBtn.count(), filtersOpens, sortCtl, checkboxes, pager, addNew, overflow: await overflow(page) });
      await page.screenshot({ path: `${SHOTS}/wf-list-${l.id}.png` });
      expect.soft(hasSearch, `${l.id} has a search box`).toBe(true);
      if (hasSearch && before > 1) expect.soft(afterMiss, `${l.id} no-match search narrows rows`).toBeLessThan(before);
    });
  }

  // ---------------- trade: create (API) -> list search -> edit (UI) -> refresh -> delete ----------------
  test("trade invoice: create, find in list, edit in UI, reload persisted, delete", async ({ page }) => {
    await page.goto("/trades", { waitUntil: "networkidle" });
    const seedTrades = await api(page, "GET", "trades/?page_size=50");
    const rows: any[] = seedTrades.body?.results ?? [];
    note("TRADE-seed", { status: seedTrades.status, count: rows.length, invoices: rows.map((r) => r.invoice_number) });
    expect.soft(rows.length).toBeGreaterThanOrEqual(2);
    const sale = rows.find((r) => r.direction === "SALE");
    const purchase = rows.find((r) => r.direction === "PURCHASE");
    expect.soft(sale && purchase, "seed has one sale and one purchase trade").toBeTruthy();
    const inv = `SAT-INV-${RUN}`;
    const payload = {
      direction: "SALE", from_company: sale?.from_company?.id ?? sale?.from_company, to_company: sale?.to_company?.id ?? sale?.to_company, invoice_number: inv,
      invoice_date: new Date().toISOString().slice(0, 10), license_type: "DFIA", remarks: "SAT create",
    };
    // A trade must carry >=1 line (API rule). Reuse the seeded sale's first line (same licence row) without ids/derived fields.
    const detail = await api(page, "GET", `trades/${sale?.id}/`);
    const strip = (l: Record<string, unknown>) => Object.fromEntries(Object.entries(l).filter(([k]) => !["id", "computed_amount", "source_row_id", "authoritative_available_cif", "warnings", "condition_type", "trade", "trade_id"].includes(k) && !k.endsWith("_label")));
    const srcLines: Record<string, unknown>[] = detail.body?.lines ?? [];
    note("TRADE-seed-line-keys", { n: srcLines.length, keys: Object.keys(srcLines[0] ?? {}) });
    (payload as Record<string, unknown>).lines = srcLines.slice(0, 1).map(strip);
    const created = await api(page, "POST", "trades/", payload);
    note("TRADE-create-api", { status: created.status, keys: Object.keys(created.body || {}).slice(0, 12), err: created.status >= 400 ? JSON.stringify(created.body).slice(0, 300) : "" });
    expect.soft(created.status, "trade create via API").toBeLessThan(300);
    if (created.status >= 300) return;
    const id = created.body.id;
    await page.reload({ waitUntil: "networkidle" });
    const search = page.locator("input[type=search], [role=searchbox], input[placeholder*='Search' i]").first();
    await search.fill(inv);
    await page.waitForTimeout(1500);
    await expect.soft(page.getByText(inv).first()).toBeVisible();
    // edit through UI form
    await page.goto(`/trades/${id}/edit`, { waitUntil: "networkidle" });
    const remarks = page.getByLabel(/Remarks/i).first();
    const hasRemarks = (await remarks.count()) > 0;
    note("TRADE-edit-form", { hasRemarks, buttons: await page.getByRole("button").allInnerTexts() });
    if (hasRemarks) {
      await remarks.fill("SAT edited " + RUN);
      await page.getByRole("button", { name: /^(Save|Update|Submit)/i }).first().click();
      await page.waitForTimeout(1500);
      const got = await api(page, "GET", `trades/${id}/`);
      note("TRADE-edit-persist", { remarks: got.body?.remarks });
      expect.soft(got.body?.remarks).toBe("SAT edited " + RUN);
      await page.goto(`/trades/${id}/edit`, { waitUntil: "networkidle" });
      await expect.soft(page.getByLabel(/Remarks/i).first()).toHaveValue("SAT edited " + RUN);
    }
    // validation: clear invoice number and attempt save
    const invField = page.getByLabel(/Invoice (No|Number)/i).first();
    if (await invField.count()) {
      await invField.fill("");
      await page.getByRole("button", { name: /^(Save|Update|Submit)/i }).first().click();
      await page.waitForTimeout(800);
      const msg = await page.getByText(/required|cannot be blank|may not be blank/i).count();
      note("TRADE-validation-blank-invoice", { validationMessages: msg, url: page.url() });
      expect.soft(msg, "blank invoice number shows a validation message").toBeGreaterThan(0);
      await page.screenshot({ path: `${SHOTS}/wf-trade-validation.png` });
    }
    // cancel
    const cancel = page.getByRole("button", { name: /Cancel/i }).or(page.getByRole("link", { name: /Cancel/i }));
    note("TRADE-cancel-control", { present: (await cancel.count()) > 0 });
    // delete via API (UI delete gated by confirm dialog in list actions)
    await page.goto("/trades", { waitUntil: "networkidle" });
    await page.locator("input[type=search], [role=searchbox], input[placeholder*='Search' i]").first().fill(inv);
    await page.waitForTimeout(1500);
    const actions = page.getByRole("button", { name: new RegExp(`Actions for .*${inv}`) });
    note("TRADE-row-actions", { present: (await actions.count()) > 0 });
    if (await actions.count()) {
      await actions.first().click();
      const del = page.getByRole("menuitem", { name: /Delete/ });
      if (await del.count()) {
        await del.click();
        const dlg = page.getByRole("alertdialog").or(page.getByRole("dialog"));
        note("TRADE-delete-confirm-dialog", { shown: await dlg.first().isVisible().catch(() => false) });
        await page.keyboard.press("Escape");
        const still = await api(page, "GET", `trades/${id}/`);
        expect.soft(still.status, "cancelled delete keeps the record").toBe(200);
        await actions.first().click().catch(() => undefined);
        await page.getByRole("menuitem", { name: /Delete/ }).click().catch(() => undefined);
        await dlg.getByRole("button", { name: /Delete|Confirm|Yes/i }).first().click().catch(() => undefined);
        await page.waitForTimeout(1200);
      }
    }
    let gone = await api(page, "GET", `trades/${id}/`);
    if (gone.status === 200) { await api(page, "DELETE", `trades/${id}/`); gone = await api(page, "GET", `trades/${id}/`); note("TRADE-delete", { viaUi: false }); }
    expect.soft(gone.status, "trade deleted").toBe(404);
  });

  // ---------------- licence page vs API balance (persisted data) ----------------
  test("licence 2509: overview figures match API after reload; tabs open", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    const lic = await api(page, "GET", "licenses/2509/");
    note("LIC-api", { status: lic.status, keys: Object.keys(lic.body || {}).slice(0, 40) });
    await page.goto("/licenses/2509/overview", { waitUntil: "networkidle" });
    const tabs = await page.getByRole("tab").allInnerTexts();
    note("LIC-tabs", { tabs });
    for (const t of tabs) {
      const tab = page.getByRole("tab", { name: t.trim() }).first();
      await tab.click();
      await page.waitForTimeout(500);
      const err = await page.getByText(/something went wrong|failed to load|error/i).count();
      note(`LIC-tab-${t.trim()}`, { selected: await tab.getAttribute("aria-selected"), errText: err, overflow: await overflow(page) });
    }
    await page.reload({ waitUntil: "networkidle" });
    note("LIC-reload", { url: page.url(), selectedTab: await page.getByRole("tab", { selected: true }).allInnerTexts() });
    const bal = lic.body?.balance_cif ?? lic.body?.available_cif ?? lic.body?.total_balance;
    note("LIC-balance-field", { bal, pageHasBal: bal != null ? await page.getByText(String(Number(bal).toLocaleString("en-IN", { maximumFractionDigits: 2 }))).count() : null });
  });

  // ---------------- report exports ----------------
  for (const r of [
    { id: "item-report", path: "/reports/item-report", btn: /Export/i },
    { id: "item-pivot", path: "/reports/item-pivot", btn: /Export|Excel|Download/i },
    { id: "expiring", path: "/reports/expiring-licenses", btn: /Export|Excel|PDF|Download/i },
    { id: "active", path: "/reports/active-licenses", btn: /Export|Excel|PDF|Download/i },
    { id: "purchase-profit", path: "/reports/license-purchase-profit", btn: /Export|Excel|PDF|Download/i },
    { id: "planned", path: "/reports/planned-report", btn: /Export|Excel|PDF|Download/i },
  ]) {
    test(`export from UI: ${r.id}`, async ({ page }) => {
      await page.goto(r.path, { waitUntil: "networkidle" });
      const b = page.getByRole("button", { name: r.btn });
      const n = await b.count();
      note(`EXPORT-${r.id}-controls`, { buttons: await b.allInnerTexts() });
      if (!n) { note(`EXPORT-${r.id}`, { result: "NO_EXPORT_CONTROL" }); test.info().annotations.push({ type: "no-export-control", description: r.id }); return; }
      if (!(await b.first().isEnabled())) { note(`EXPORT-${r.id}`, { result: "CONTROL_DISABLED_NO_DATA" }); return; }
      const dl = page.waitForEvent("download", { timeout: 25_000 }).catch(() => null);
      await b.first().click();
      const d = await dl;
      if (!d) { note(`EXPORT-${r.id}`, { result: "NO_DOWNLOAD_EVENT" }); expect.soft(d, `${r.id} download event`).not.toBeNull(); return; }
      const p = `${EVID}/dl-${r.id}-${d.suggestedFilename()}`;
      await d.saveAs(p);
      const size = fs.statSync(p).size;
      note(`EXPORT-${r.id}`, { result: "DOWNLOADED", file: d.suggestedFilename(), bytes: size });
      expect.soft(size, `${r.id} file non-empty`).toBeGreaterThan(200);
    });
  }

  // ---------------- error / empty states via mocked network ----------------
  for (const e of [
    { id: "trades", path: "/trades", api: "**/api/trades/**" },
    { id: "licences", path: "/licenses", api: "**/api/licenses/**" },
    { id: "allotments", path: "/allotments", api: "**/api/allotments/**" },
    { id: "boe", path: "/bill-of-entries", api: "**/api/bill-of-entries/**" },
    { id: "item-pivot", path: "/reports/item-pivot", api: "**/api/**/item-pivot*/**" },
    { id: "dashboard", path: "/dashboard", api: "**/api/dashboard/**" },
    { id: "masters-companies", path: "/masters/companies", api: "**/api/masters/companies/**" },
  ]) {
    test(`error + empty state: ${e.id}`, async ({ page }) => {
      const errs: string[] = [];
      page.on("pageerror", (x) => errs.push(x.message));
      await page.route(e.api, (route) => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "SAT injected failure" }) }));
      await page.goto(e.path, { waitUntil: "networkidle" });
      // react-query retries a 500 with back-off, so poll up to 25s for any user-visible error text.
      const errRe = /error|failed|couldn.?t|unable|went wrong|try again|retry/i;
      let text = "";
      for (let i = 0; i < 25; i++) { text = (await page.locator("body").innerText()).slice(0, 4000); if (errRe.test(text)) break; await page.waitForTimeout(1000); }
      const showsError = errRe.test(text);
      const retry = await page.getByRole("button", { name: /retry|try again|reload/i }).count();
      note(`ERR-${e.id}`, { showsError, retry, pageErrors: errs, blank: text.trim().length < 40, loginBounce: new URL(page.url()).pathname === "/login" });
      await page.screenshot({ path: `${SHOTS}/wf-err-${e.id}.png` });
      expect.soft(errs, "no unhandled exception on 500").toEqual([]);
      expect.soft(showsError, `${e.id} surfaces the 500 to the user`).toBe(true);
      await page.unroute(e.api);
      await page.route(e.api, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ count: 0, results: [], current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false }) }));
      await page.goto(e.path, { waitUntil: "networkidle" });
      const t2 = (await page.locator("body").innerText()).slice(0, 4000);
      note(`EMPTY-${e.id}`, { emptyMsg: /no (results|records|data|items|licen|allot|trades|bill|matching)|nothing/i.test(t2), pageErrors: errs.length });
    });
  }

  // ---------------- validation + cancel on a create form ----------------
  test("create form validation + cancel (masters companies)", async ({ page }) => {
    await page.goto("/masters/companies/create", { waitUntil: "networkidle" });
    const submit = page.getByRole("button", { name: /^(Create|Save)$/ });
    await submit.click();
    await page.waitForTimeout(700);
    const msgs = await page.getByText(/required|cannot be blank|may not be blank|this field/i).count();
    const invalid = await page.locator("[aria-invalid=true]").count();
    note("FORM-companies-validation", { msgs, ariaInvalid: invalid, url: page.url() });
    expect.soft(msgs + invalid, "empty submit shows validation").toBeGreaterThan(0);
    await page.screenshot({ path: `${SHOTS}/wf-company-validation.png` });
    const cancel = page.getByRole("button", { name: /Cancel/ }).or(page.getByRole("link", { name: /Cancel/ }));
    if (await cancel.count()) {
      await cancel.first().click();
      await page.waitForTimeout(500);
      note("FORM-companies-cancel", { url: page.url() });
      expect.soft(new URL(page.url()).pathname).toBe("/masters/companies");
    } else note("FORM-companies-cancel", { present: false });
  });

  // ---------------- reload-dirty-form guard, deep link + browser back ----------------
  test("navigation: deep link, back/forward, 404, logout then protected route", async ({ page, context }) => {
    await page.goto("/licenses/2509/overview", { waitUntil: "networkidle" });
    await page.goto("/allotments", { waitUntil: "networkidle" });
    await page.goBack({ waitUntil: "networkidle" });
    expect.soft(new URL(page.url()).pathname).toBe("/licenses/2509/overview");
    await page.goForward({ waitUntil: "networkidle" });
    expect.soft(new URL(page.url()).pathname).toBe("/allotments");
    await page.goto("/nope/not/here", { waitUntil: "networkidle" });
    note("NAV-404", { text: (await page.locator("body").innerText()).slice(0, 120) });
    // logout via UI
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    const userMenu = page.getByRole("button", { name: /user|account|profile|hardik|menu/i });
    note("NAV-user-menu", { candidates: await userMenu.allInnerTexts() });
    let loggedOut = false;
    for (const sel of [page.getByRole("button", { name: /log ?out|sign ?out/i }), page.getByRole("menuitem", { name: /log ?out|sign ?out/i }), page.getByRole("link", { name: /log ?out|sign ?out/i })]) {
      if (await sel.count()) { await sel.first().click(); loggedOut = true; break; }
    }
    if (!loggedOut) {
      for (const b of await userMenu.all()) { await b.click().catch(() => undefined); const lo = page.getByRole("menuitem", { name: /log ?out|sign ?out/i }); if (await lo.count()) { await lo.first().click(); loggedOut = true; break; } await page.keyboard.press("Escape"); }
    }
    await page.waitForTimeout(1000);
    note("NAV-logout", { loggedOut, url: page.url() });
    expect.soft(loggedOut, "a Logout control is reachable").toBe(true);
    if (loggedOut) {
      await page.goto("/trades", { waitUntil: "networkidle" });
      expect.soft(new URL(page.url()).pathname, "protected route after logout redirects to login").toBe("/login");
      await page.goBack().catch(() => undefined);
    }
    // wrong password
    const ctx2 = await context.browser()!.newContext({ storageState: undefined });
    const p2 = await ctx2.newPage();
    await p2.goto("/login", { waitUntil: "networkidle" });
    await p2.locator("#login-username").fill("hardik");
    await p2.locator("#login-password").fill("wrong-password-x");
    await p2.getByRole("button", { name: "Sign in" }).click();
    await p2.waitForTimeout(1200);
    const bad = await p2.getByRole("alert").allInnerTexts();
    note("LOGIN-bad-password-visible-text", { text: (await p2.locator("body").innerText()).slice(0, 400).replace(/\s+/g, " "), ariaLive: await p2.locator("[aria-live]").count() });
    note("LOGIN-bad-password", { url: p2.url(), alerts: bad });
    expect.soft(new URL(p2.url()).pathname).toBe("/login");
    expect.soft(bad.join(" ").length, "bad credentials message").toBeGreaterThan(0);
    await ctx2.close();
  });

  // ---------------- viewer role ----------------
  test("viewer role: write routes blocked, no write controls, API 403", async ({ browser }) => {
    const v = await viewerPage(browser);
    const writeRoutes = ["/trades/create", "/licenses/create", "/allotments/create", "/bill-of-entries/create", "/masters/companies/create", "/admin/users", "/admin/users/create", "/admin/activity-log", "/accounting/dashboard", "/mapping", "/planning", "/settings"];
    for (const r of writeRoutes) {
      await v.goto(r, { waitUntil: "networkidle" });
      const path = new URL(v.url()).pathname;
      const body = (await v.locator("body").innerText()).slice(0, 200).replace(/\s+/g, " ");
      note(`VIEWER-route${r}`, { finalPath: path, body });
    }
    for (const r of ["/licenses", "/allotments", "/bill-of-entries", "/trades", "/reports/item-report"]) {
      await v.goto(r, { waitUntil: "networkidle" });
      const adds = await v.getByRole("link", { name: /Add New|Create/ }).count() + await v.getByRole("button", { name: /Add New|Create|Delete/ }).count();
      note(`VIEWER-list${r}`, { finalPath: new URL(v.url()).pathname, writeControls: adds });
      expect.soft(adds, `viewer sees no write controls on ${r}`).toBe(0);
      await v.screenshot({ path: `${SHOTS}/wf-viewer-${r.replace(/\//g, "_")}.png` });
    }
    const w1 = await api(v, "POST", "trades/", { direction: "SALE" });
    const w2 = await api(v, "DELETE", "licenses/2509/");
    const w3 = await api(v, "POST", "masters/companies/", { name: "viewer-should-fail" });
    note("VIEWER-api-writes", { trades_post: w1.status, licence_delete: w2.status, company_post: w3.status });
    expect.soft([w1.status, w2.status, w3.status].every((s) => s === 401 || s === 403), "viewer writes refused").toBe(true);
    await v.context().close();
  });

  // ---------------- keyboard + modal focus ----------------
  test("keyboard: tab order reaches nav, Escape closes row-action menu", async ({ page }) => {
    await page.goto("/licenses", { waitUntil: "networkidle" });
    const seen: string[] = [];
    for (let i = 0; i < 12; i++) { await page.keyboard.press("Tab"); seen.push(await page.evaluate(() => { const a = document.activeElement as HTMLElement; return `${a?.tagName}:${(a?.getAttribute("aria-label") || a?.innerText || "").trim().slice(0, 30)}`; })); }
    note("KB-licences-tab-order", { seen });
    const act = page.getByRole("button", { name: /^Actions for/ }).first();
    if (await act.count()) {
      await act.focus(); await page.keyboard.press("Enter");
      const open = await page.getByRole("menu").isVisible().catch(() => false);
      await page.keyboard.press("Escape");
      const closed = !(await page.getByRole("menu").isVisible().catch(() => false));
      const focusBack = await act.evaluate((el) => el === document.activeElement);
      note("KB-actions-menu", { open, closed, focusReturned: focusBack });
      expect.soft(open && closed).toBe(true);
    }
  });
});
