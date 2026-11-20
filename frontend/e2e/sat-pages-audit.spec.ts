import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const EVID = process.env.SAT_OUT || path.join(os.homedir(), "lm_sat_evidence", "e2e");
fs.mkdirSync(path.join(EVID, "shots"), { recursive: true });

/**
 * SAT Phase 5/7 - page x viewport control audit on the seeded disposable DB.
 * READ-ONLY: only navigates and inspects (plus mocked-500 error-state probes via page.route).
 * Findings are collected to ${EVID}/pages-audit.jsonl for the audit report; hard failures are limited to
 * a crashed/blank page, an unhandled page error, or an auth bounce.
 */
const real = process.env.LM_REAL_E2E === "1";
const OUT = path.join(EVID, "pages-audit.jsonl");
const SHOTS = path.join(EVID, "shots");
const VIEWPORTS = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "820x1180", width: 820, height: 1180 },
  { name: "390x844", width: 390, height: 844 },
] as const;

const PAGES: { id: string; path: string }[] = [
  { id: "dashboard", path: "/dashboard" },
  { id: "licences-list", path: "/licenses" },
  { id: "licence-overview", path: "/licenses/2509/overview" },
  { id: "licence-detail", path: "/licenses/2509" },
  { id: "licence-edit", path: "/licenses/2509/edit" },
  { id: "licence-create", path: "/licenses/create" },
  { id: "allotments", path: "/allotments" },
  { id: "allotment-create", path: "/allotments/create" },
  { id: "allotment-edit", path: "/allotments/1/edit" },
  { id: "allotment-allocate", path: "/allotments/1/allocate" },
  { id: "boe-list", path: "/bill-of-entries" },
  { id: "boe-create", path: "/bill-of-entries/create" },
  { id: "trades", path: "/trades" },
  { id: "trade-create", path: "/trades/create" },
  { id: "reconciliation", path: "/reconciliation" },
  { id: "reconciliation-issues", path: "/reconciliation-issues" },
  { id: "item-pivot", path: "/reports/item-pivot" },
  { id: "item-report", path: "/reports/item-report" },
  { id: "planned-report", path: "/reports/planned-report" },
  { id: "purchase-profit", path: "/reports/license-purchase-profit" },
  { id: "expiring", path: "/reports/expiring-licenses" },
  { id: "active", path: "/reports/active-licenses" },
  { id: "download-license", path: "/reports/download-license" },
  { id: "sion-e1", path: "/reports/parle/sion-e1" },
  { id: "sion-e5", path: "/reports/parle/sion-e5" },
  { id: "sion-e126", path: "/reports/parle/sion-e126" },
  { id: "sion-e132", path: "/reports/parle/sion-e132" },
  { id: "mapping", path: "/mapping" },
  { id: "planning", path: "/planning" },
  { id: "incentive", path: "/incentive-licenses" },
  { id: "ledger-upload", path: "/ledger-upload" },
  { id: "license-ledger", path: "/license-ledger" },
  { id: "ledger-downloads", path: "/license-ledger/download-requests" },
  { id: "masters-hub", path: "/masters" },
  { id: "masters-companies", path: "/masters/companies" },
  { id: "masters-item-names", path: "/masters/item-names" },
  { id: "masters-companies-create", path: "/masters/companies/create" },
  { id: "admin-users", path: "/admin/users" },
  { id: "admin-user-create", path: "/admin/users/create" },
  { id: "activity-log", path: "/admin/activity-log" },
  { id: "settings", path: "/settings" },
  { id: "profile", path: "/profile" },
  { id: "acct-setup", path: "/accounting/setup" },
  { id: "acct-dashboard", path: "/accounting/dashboard" },
  { id: "not-found", path: "/this-route-does-not-exist" },
];

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

function log(rec: Record<string, unknown>) {
  fs.appendFileSync(OUT, JSON.stringify(rec) + "\n");
}

test.describe("SAT page x viewport audit", () => {
  test.skip(!real, "Requires the isolated data-bearing harness.");
  test.describe.configure({ mode: "serial" });
  const AUTH = path.join(EVID, ".sat-auth.json");
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext({ storageState: undefined });
    const p = await ctx.newPage();
    await signIn(p);
    await ctx.storageState({ path: AUTH });
    await ctx.close();
  });
  test.use({ storageState: AUTH });

  for (const vp of VIEWPORTS) {
    for (const pg of PAGES) {
      test(`${pg.id} @ ${vp.name}`, async ({ page }) => {
        test.setTimeout(60_000);
        await page.setViewportSize({ width: vp.width, height: vp.height });
        const pageErrors: string[] = [];
        const consoleErrors: string[] = [];
        const badResponses: string[] = [];
        page.on("pageerror", (e) => pageErrors.push(e.message));
        page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("favicon")) consoleErrors.push(m.text().slice(0, 200)); });
        page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) badResponses.push(`${r.status()} ${r.request().method()} ${r.url().replace(/^.*\/api\//, "/api/")}`); });

        await page.goto(pg.path, { waitUntil: "networkidle" }).catch(() => undefined);
        await page.waitForTimeout(400);
        const finalPath = new URL(page.url()).pathname;
        const info = await page.evaluate(() => {
          const vis = (el: Element) => { const r = (el as HTMLElement).getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
          const name = (el: Element) => (el.getAttribute("aria-label") || el.getAttribute("title") || (el as HTMLElement).innerText || el.getAttribute("aria-labelledby") || "").trim();
          const btns = [...document.querySelectorAll("button, [role=button]")].filter(vis);
          const unnamedBtns = btns.filter((b) => !name(b) && !b.querySelector("img[alt]:not([alt=''])")).length;
          const inputs = [...document.querySelectorAll("input:not([type=hidden]), select, textarea")].filter(vis);
          const unlabeled = inputs.filter((i) => {
            const id = i.getAttribute("id");
            return !i.getAttribute("aria-label") && !i.getAttribute("aria-labelledby") && !i.getAttribute("title") && !(id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) && !i.closest("label");
          }).length;
          const sw = document.documentElement.scrollWidth, iw = window.innerWidth;
          // clipped/overflowing tables: a visible table wider than its nearest scroll container that is not scrollable
          let clippedTables = 0;
          document.querySelectorAll("table").forEach((t) => {
            if (!vis(t)) return;
            let p: HTMLElement | null = t.parentElement; let ok = false;
            while (p && p !== document.body) { const ox = getComputedStyle(p).overflowX; if ((ox === "auto" || ox === "scroll") ) { ok = true; break; } p = p.parentElement; }
            if (!ok && t.getBoundingClientRect().right > window.innerWidth + 1) clippedTables++;
          });
          const text = document.body.innerText || "";
          return {
            h1: document.querySelector("h1")?.textContent?.trim() ?? null,
            buttons: btns.length, links: [...document.querySelectorAll("a[href]")].filter(vis).length,
            tabs: [...document.querySelectorAll("[role=tab]")].filter(vis).length,
            inputs: inputs.length, selects: [...document.querySelectorAll("select,[role=combobox]")].filter(vis).length,
            tables: [...document.querySelectorAll("table")].filter(vis).length, rows: document.querySelectorAll("tbody tr").length,
            checkboxes: [...document.querySelectorAll("input[type=checkbox],[role=checkbox]")].filter(vis).length,
            unnamedBtns, unlabeled, overflowPx: Math.max(0, sw - iw), clippedTables,
            textLen: text.trim().length, errorBanner: /something went wrong|unexpected error|failed to load/i.test(text),
          };
        });
        let axe: { id: string; impact: string | null | undefined; nodes: number }[] = [];
        try {
          const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
          axe = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
        } catch (e) { axe = [{ id: "axe-error:" + String(e).slice(0, 60), impact: "n/a", nodes: 0 }]; }
        // keyboard: first Tab lands on something visible and focus ring exists
        await page.keyboard.press("Tab");
        const focus = await page.evaluate(() => { const a = document.activeElement as HTMLElement | null; if (!a || a === document.body) return { ok: false, tag: "BODY", outline: "" }; const s = getComputedStyle(a); return { ok: true, tag: a.tagName, outline: `${s.outlineStyle}/${s.outlineWidth}/${s.boxShadow !== "none"}` }; });
        const shot = `${SHOTS}/${pg.id}-${vp.name}.png`;
        await page.screenshot({ path: shot, fullPage: false });
        log({ id: pg.id, path: pg.path, finalPath, vp: vp.name, ...info, axe, focus, pageErrors, consoleErrors: consoleErrors.slice(0, 5), badResponses: badResponses.slice(0, 8), shot });

        expect(pageErrors, "unhandled page errors").toEqual([]);
        if (pg.id !== "not-found") expect(info.textLen, "page not blank").toBeGreaterThan(20);
        expect(finalPath, "not bounced to login").not.toBe("/login");
      });
    }
  }
});
