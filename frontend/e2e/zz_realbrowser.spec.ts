import { test } from "@playwright/test";
import { readFileSync } from "node:fs";
const tokens = JSON.parse(readFileSync("/tmp/live_tokens.json", "utf8"));
test("real browser dashboard at 5173", async ({ page }) => {
  const consoleErrors: string[] = []; const pageErrors: string[] = []; const requests: string[] = []; const failed: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") consoleErrors.push(`${m.type()}: ${m.text().slice(0, 300)}`); });
  page.on("pageerror", (e) => pageErrors.push(e.message));
  page.on("request", (r) => { if (r.url().includes("/api/")) requests.push(r.url().replace(/^https?:\/\/[^/]+/, "")); });
  page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.url()}`); });
  await page.addInitScript((t) => { localStorage.setItem("access", t.access); localStorage.setItem("refresh", t.refresh); }, tokens);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("http://localhost:5173/dashboard", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(1500);
  console.log("RB_TITLE", await page.locator("h1").first().innerText().catch(() => "none"));
  console.log("RB_REQUESTS", JSON.stringify(requests));
  console.log("RB_FAILED", JSON.stringify(failed));
  console.log("RB_PAGE_ERRORS", JSON.stringify(pageErrors));
  console.log("RB_CONSOLE", JSON.stringify(consoleErrors.slice(0, 12), null, 1));
  for (const id of ["dashboard-boe", "dashboard-invoices", "dashboard-allotments"]) {
    const loc = page.locator(`#${id}`);
    console.log("RB_SECTION", id, await loc.count() ? (await loc.innerText()).replace(/\n+/g, " | ").slice(0, 160) : "ABSENT");
  }
  await page.screenshot({ path: "/tmp/rb_full.png", fullPage: true });
});
