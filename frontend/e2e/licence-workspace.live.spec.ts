import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

/**
 * LIVE, READ-ONLY regression suite for the Licence register.
 *
 * Needs a session saved by `npx playwright codegen --save-storage=/tmp/lm_auth/state.json <url>`.
 * Every non-GET /api request is aborted and recorded; the suite asserts none was attempted.
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 npx playwright test -c playwright.live.config.ts
 * (HEAD baseline: PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174)
 * Override expected filter labels with LM_EXPECTED_FILTERS="Label A,Label B".
 */
const STATE = process.env.LM_AUTH_STATE || "/tmp/lm_auth/state.json";
const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173";
const ARTIFACT = process.env.LM_LIVE_ARTIFACT || "/tmp/lm_browser/out/live-spec-requests.json";
const TARGET = "/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=1%2C2%2C3%2C4%2C5%2C6%2C7%2C8";
const EXPECTED_FILTERS = (process.env.LM_EXPECTED_FILTERS || "Purchase Status,Is Null,Is Planned,Balance CIF,Scheme Code")
  .split(",").map(s => s.trim()).filter(Boolean);
const EXPECTED_ACTIONS = ["License Overview", "Balance PDF", "Balance Excel"];

const haveState = fs.existsSync(STATE);
const state = haveState ? JSON.parse(fs.readFileSync(STATE, "utf8")) : { cookies: [], origins: [] };
const storage: { name: string; value: string }[] = (state.origins || []).flatMap((o: { localStorage?: { name: string; value: string }[] }) => o.localStorage || []);

test.skip(!haveState, `Auth state missing: create ${STATE} with "npx playwright codegen --save-storage=${STATE} ${BASE}/login"`);
test.use({ viewport: { width: 1440, height: 900 } });

interface Probe {
  api: { t: number; m: string; u: string }[];
  blocked: string[];
  errors: string[];
  steps: Record<string, number>;
}

async function setup(page: Page): Promise<Probe> {
  const probe: Probe = { api: [], blocked: [], errors: [], steps: {} };
  await page.context().addCookies(state.cookies || []);
  await page.addInitScript((entries: { name: string; value: string }[]) => {
    for (const { name, value } of entries) localStorage.setItem(name, value);
  }, storage);
  await page.route("**/api/**", route => {
    const req = route.request();
    if (req.method() !== "GET") { probe.blocked.push(`${req.method()} ${req.url()}`); return route.abort(); }
    return route.continue();
  });
  page.on("request", r => {
    if (r.url().includes("/api/")) probe.api.push({ t: Date.now(), m: r.method(), u: r.url().replace(/^https?:\/\/[^/]+/, "") });
  });
  page.on("console", m => { if (m.type() === "error" && !/favicon/.test(m.text())) probe.errors.push(`console: ${m.text().slice(0, 200)}`); });
  page.on("pageerror", e => probe.errors.push(`pageerror: ${String(e).slice(0, 200)}`));
  return probe;
}

const listCalls = (p: Probe) => p.api.filter(r => r.m === "GET" && /\/licenses\/(\?|$)/.test(r.u));
async function step(page: Page, probe: Probe, name: string, fn: () => Promise<void>) {
  const before = probe.api.length;
  await fn();
  await page.waitForLoadState("networkidle").catch(() => undefined);
  probe.steps[name] = probe.api.length - before;
}

test("licence register workspace (read-only, live)", async ({ page }, testInfo) => {
  const probe = await setup(page);

  await step(page, probe, "load", async () => {
    const t0 = Date.now();
    await page.goto(BASE + TARGET, { waitUntil: "domcontentloaded" });
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole("button", { expanded: false, name: /^Expand license/ }).first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(Math.max(0, 5000 - (Date.now() - t0)));
  });

  // No render loop: bounded list requests, params preserved.
  expect(listCalls(probe).length, `licenses/ list requests: ${JSON.stringify(listCalls(probe).map(r => r.u))}`).toBeLessThanOrEqual(4);
  const url = new URL(page.url());
  expect(url.searchParams.get("page")).toBe("1");
  expect(url.searchParams.get("purchase_status")).toBe("1,2,3,4,5,6,7,8");
  expect(url.searchParams.get("is_expired")).toBe("False");
  expect(url.searchParams.get("flags__is_null")).toBe("False");

  // Filters panel toggles and labels present.
  await step(page, probe, "filters", async () => {
    const toggle = page.getByRole("button", { name: /^Filters/ }).first();
    await expect(toggle).toBeVisible();
    const open = async () => (await toggle.getAttribute("aria-expanded")) === "true";
    if (!(await open())) await toggle.click();
    for (const label of EXPECTED_FILTERS) {
      await expect(page.getByText(label, { exact: true }).first(), `filter label ${label}`).toBeVisible();
    }
    const was = await open();
    await toggle.click();
    if ((await toggle.getAttribute("aria-expanded")) !== null) expect(await open()).toBe(!was);
    if ((await toggle.getAttribute("aria-expanded")) === "true") await toggle.click();
  });

  // Expand first card -> Overview default.
  const expanders = page.getByRole("button", { name: /^Expand license/ });
  const firstName = (await expanders.first().getAttribute("aria-label")) || "";
  const firstNo = firstName.replace(/^Expand license\s*/, "");
  await step(page, probe, "expand-first", async () => { await expanders.first().click(); });
  const region = page.getByRole("region", { name: `License ${firstNo} details` });
  await expect(region).toBeVisible();
  await expect(region.getByRole("tab", { name: /Overview/ })).toHaveAttribute("aria-selected", "true");

  // Every tab renders content or proper empty state.
  const tabNames = (await region.getByRole("tab").allInnerTexts()).map(s => s.trim()).filter(Boolean);
  for (const must of ["Overview", "Import Items", "BOE & Allotment", "Invoices", "History"]) {
    expect(tabNames.some(n => n.startsWith(must)), `tab ${must} in ${tabNames}`).toBeTruthy();
  }
  const tabReport: Record<string, { height: number | null; chars: number }> = {};
  for (const name of tabNames) {
    await step(page, probe, `tab:${name}`, async () => { await region.getByRole("tab", { name, exact: true }).click(); });
    const panel = region.getByRole("tabpanel").first();
    await expect(panel).toBeVisible();
    const text = (await panel.innerText()).trim();
    const box = await panel.boundingBox();
    tabReport[name] = { height: box ? Math.round(box.height) : null, chars: text.length };
    expect(text.length > 0, `tab ${name} empty`).toBeTruthy();
    expect(box && box.height > 120 && text.length < 20, `tab ${name} tall+blank (${JSON.stringify(tabReport[name])})`).toBeFalsy();
  }
  await region.getByRole("tab", { name: /Overview/ }).click();

  // Action menu: open, list, never click.
  await step(page, probe, "actions", async () => {
    await page.getByRole("button", { name: `Actions for license ${firstNo}` }).click();
    const items = (await page.getByRole("menuitem").allInnerTexts()).map(s => s.trim());
    for (const e of EXPECTED_ACTIONS) expect(items, `menu items ${items}`).toContain(e);
    expect(items[0]).toBe("License Overview");
    await page.keyboard.press("Escape");
  });

  // Second card shows only its own data.
  if ((await expanders.count()) > 0) {
    const secondName = (await expanders.first().getAttribute("aria-label")) || "";
    const secondNo = secondName.replace(/^Expand license\s*/, "");
    await step(page, probe, "expand-second", async () => { await expanders.first().click(); });
    const region2 = page.getByRole("region", { name: `License ${secondNo} details` });
    await expect(region2).toBeVisible();
    await expect(region2.getByRole("tab", { name: /Overview/ })).toHaveAttribute("aria-selected", "true");
    if (secondNo !== firstNo) {
      const text2 = await region2.innerText();
      expect(text2).not.toContain(`License ${firstNo}`);
    }
  } else test.info().annotations.push({ type: "note", description: "only one card; second-card check skipped" });

  // Tablet width: no horizontal page overflow.
  await step(page, probe, "tablet", async () => {
    await page.setViewportSize({ width: 820, height: 900 });
    await page.waitForTimeout(400);
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "horizontal overflow at 820px").toBeTruthy();

  fs.mkdirSync(ARTIFACT.replace(/\/[^/]+$/, ""), { recursive: true });
  fs.writeFileSync(ARTIFACT, JSON.stringify({ base: BASE, steps: probe.steps, total: probe.api.length, listCalls: listCalls(probe).length, tabs: tabReport, blockedWrites: probe.blocked, errors: probe.errors }, null, 2));
  await testInfo.attach("request-counts", { body: JSON.stringify(probe.steps, null, 2), contentType: "application/json" });

  expect(probe.blocked, "non-GET /api requests attempted").toEqual([]);
  expect(probe.errors, "console/page errors").toEqual([]);
});
