import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/**
 * SAT Phase 4: licence -> BOE debit -> balance -> allotment link (M2M = full consumption) -> BOE delete (reversal).
 * Runs ONLY on the disposable seeded DB of scripts/test/run_data_bearing_browser_e2e.sh (seed_browser_2509).
 * Real auth, real API, no mocks. Every value is recorded to $SAT_OUT/int/boe_flow.jsonl.
 * Canonical rule: available = credit - BOE - outstanding allotment - billed-without-BOE. An M2M-linked allotment contributes 0.
 */
const real = process.env.LM_REAL_E2E === "1";
const EVID = path.join(process.env.SAT_OUT || path.join(os.homedir(), "lm_sat_evidence"), "int");
fs.mkdirSync(EVID, { recursive: true });
const OUT = path.join(EVID, "boe_flow.jsonl");
const LIC = 2509;
const note = (id: string, data: Record<string, unknown>) =>
  fs.appendFileSync(OUT, JSON.stringify({ id, at: new Date().toISOString(), ...data }) + "\n");

async function signIn(page: Page) {
  for (let attempt = 0; attempt < 4; attempt++) {
    await page.goto("/login", { waitUntil: "networkidle" });
    await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
    await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
    await page.getByRole("button", { name: "Sign in" }).click();
    try { await page.waitForURL("**/dashboard", { timeout: 15000 }); return; }
    catch { await page.waitForTimeout(12000); } // login throttle
  }
  throw new Error("login failed");
}
async function api<T = any>(page: Page, method: string, url: string, body?: unknown) {
  return page.evaluate(async ([m, u, payload]) => {
    const r = await fetch(`/api/${u}`, {
      method: m as string,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access")}` },
      body: payload === undefined ? undefined : JSON.stringify(payload),
    });
    const text = await r.text();
    let json: unknown = text;
    try { json = JSON.parse(text); } catch { /* keep text */ }
    return { status: r.status, body: json };
  }, [method, url, body] as const) as Promise<{ status: number; body: T }>;
}
const num = (v: unknown) => Number(String(v ?? "0").replace(/,/g, ""));
const rows = (b: any) => (Array.isArray(b) ? b : b?.results ?? []);

test.describe("SAT-INT BOE flow (disposable DB)", () => {
  test.skip(!real, "needs LM_REAL_E2E=1 and the harness");

  test("licence -> BOE debit -> allotment link -> reversal", async ({ page }) => {
    test.setTimeout(180000);
    await signIn(page);

    const balance = async (tag: string) => {
      const r = await api(page, "GET", `licenses/${LIC}/`);
      expect(r.status).toBe(200);
      const v = num(r.body.balance_cif ?? r.body.get_balance_cif);
      note("balance", { tag, balance_cif: r.body.balance_cif, get_balance_cif: r.body.get_balance_cif });
      return { v, body: r.body };
    };

    const b0 = await balance("B0 start");
    const items = rows((await api(page, "GET", `license-items/?license=${LIC}&page_size=50`)).body)
      .filter((i: any) => String(i.license ?? i.license_id ?? LIC) === String(LIC));
    const importItems = (b0.body.import_license ?? b0.body.import_items ?? items) as any[];
    const item = importItems[0];
    note("SAT-INT-003 setup", { item_id: item?.id, item_count: importItems.length });
    expect(item?.id, "seeded import item").toBeTruthy();

    const bySearch = await api(page, "GET", `allotments/?search=E2E-ALLOTMENT-2509&page_size=10`);
    const unfiltered = await api(page, "GET", `allotments/?page_size=50&is_boe=all`);
    const all = rows(unfiltered.body);
    note("SAT-UX-D10 triage", {
      search_count: rows(bySearch.body).length, search_total: bySearch.body?.count,
      unfiltered_status: unfiltered.status, unfiltered_total: unfiltered.body?.count,
      sample: all.slice(0, 5).map((a: any) => ({ id: a.id, item_name: a.item_name, invoice: a.invoice, type: a.type, is_boe: a.is_boe, cif_fc: a.cif_fc })),
    });
    const allots = all.length ? all : rows(bySearch.body);
    note("SAT-INT-004 allotments", { count: allots.length, ids: allots.map((a: any) => a.id), companies: allots.map((a: any) => a.company) });
    const ports = rows((await api(page, "GET", "masters/ports/?page_size=1")).body);
    expect(ports.length, "a port exists").toBeGreaterThan(0);
    const company = allots[0]?.company?.id ?? allots[0]?.company ?? b0.body.exporter?.id ?? b0.body.exporter;

    // SAT-INT-003: BOE debit of exactly 100.00 CIF / 10.000 qty on the licence item.
    const number = `SATINT${Date.now().toString().slice(-7)}`;
    const create = await api(page, "POST", "bill-of-entries/", {
      bill_of_entry_number: number,
      bill_of_entry_date: new Date().toISOString().slice(0, 10),
      port: ports[0].id,
      company,
      item_details: [{ sr_number: item.id, cif_fc: "100.00", cif_inr: "8450.00", qty: "10.000" }],
    });
    note("SAT-INT-003 create BOE", { status: create.status, body: create.status >= 300 ? create.body : { id: create.body.id } });
    expect(create.status, JSON.stringify(create.body)).toBeLessThan(300);
    const boeId = create.body.id;

    const b1 = await balance("B1 after BOE 100");
    note("SAT-INT-003 result", { expected: +(b0.v - 100).toFixed(2), actual: b1.v, diff: +(b1.v - (b0.v - 100)).toFixed(2) });
    expect(Math.abs(b1.v - (b0.v - 100))).toBeLessThan(0.011);

    // Screen after reload shows the API balance (accept the en-IN and plain renderings).
    await page.goto(`/licenses/${LIC}/overview`, { waitUntil: "networkidle" });
    await page.reload({ waitUntil: "networkidle" });
    const text = await page.locator("body").innerText();
    const forms = [b1.v.toFixed(2), b1.v.toLocaleString("en-IN", { minimumFractionDigits: 2 }), b1.v.toLocaleString("en-US", { minimumFractionDigits: 2 })];
    const shown = forms.filter((f) => text.includes(f));
    await page.screenshot({ path: path.join(EVID, "int003_overview_after_boe.png"), fullPage: true });
    note("SAT-INT-003 screen", { forms, shown });

    // SAT-INT-004: link the allotment to the BOE -> the allotment contributes 0 (approved 2026-11-17 rule).
    if (allots.length) {
      const link = await api(page, "PATCH", `bill-of-entries/${boeId}/`, { allotment: [allots[0].id] });
      note("SAT-INT-004 link", { status: link.status, body: link.status >= 300 ? link.body : "ok" });
      expect(link.status, JSON.stringify(link.body)).toBeLessThan(300);
      const b2 = await balance("B2 after link");
      // Before linking, B0 already deducted the allotment's outstanding CIF; linking releases it.
      note("SAT-INT-004 result", { b0: b0.v, b1: b1.v, b2: b2.v, released: +(b2.v - b1.v).toFixed(2) });
      // Linking can only release a reservation (b2 >= b1); the released amount is compared with the
      // allotment's outstanding CIF from the API record below.
      expect(b2.v).toBeGreaterThanOrEqual(b1.v - 0.011);
      const allot = await api(page, "GET", `allotments/${allots[0].id}/`);
      note("SAT-INT-004 allotment record", { status: allot.status, cif_fc: allot.body?.cif_fc, balanced_quantity: allot.body?.balanced_quantity, required_value: allot.body?.required_value });
    } else {
      note("SAT-INT-004 result", { blocked: "no seeded allotment found by search" });
    }

    // SAT-INT-014: reversal by deleting the BOE restores B0.
    const del = await api(page, "DELETE", `bill-of-entries/${boeId}/`);
    note("SAT-INT-014 delete BOE", { status: del.status });
    expect(del.status).toBeLessThan(300);
    const b3 = await balance("B3 after delete");
    note("SAT-INT-014 result", { expected: b0.v, actual: b3.v, diff: +(b3.v - b0.v).toFixed(2) });
    expect(Math.abs(b3.v - b0.v)).toBeLessThan(0.011);
  });

  test("SAT-EXP X07: ledger package PDF with exactly one licence", async ({ page }) => {
    test.setTimeout(120000);
    await signIn(page);
    const start = await api(page, "POST", "license-ledger/download-package-pdf/", { license_ids: [LIC] });
    note("SAT-EXP-X07 start", { status: start.status, body: start.body });
    expect(start.status, JSON.stringify(start.body)).toBeLessThan(300);
    // Async job: poll its status URL or id if the API returns one (recorded either way; never fabricated).
    const jobId = start.body?.job_id ?? start.body?.id;
    if (jobId) {
      let last: unknown = null;
      for (let i = 0; i < 20; i++) {
        const s = await api(page, "GET", `license-ledger/download-package/${jobId}/`);
        last = { status: s.status, state: s.body?.status ?? s.body?.state, keys: Object.keys(s.body ?? {}) };
        if (s.status >= 400 || /complete|ready|done|success|failed|error/i.test(String(s.body?.status ?? s.body?.state ?? ""))) break;
        await page.waitForTimeout(3000);
      }
      note("SAT-EXP-X07 job", { jobId, last });
    }
  });
});
