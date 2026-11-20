import { expect, test, type Page, type Response } from "@playwright/test";
import ExcelJS from "exceljs";

// Item Pivot — License Numbers filter, against the local dev backend (read-only: GET requests only).
const isPivotReport = (r: Response) => r.url().includes("/reports/item-pivot/") && r.url().includes("format=json") && r.request().method() === "GET";

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
}

const licenceNumbers = (report: any): string[] =>
  (report.groups || []).flatMap((g: any) => (g.licenses || []).map((l: any) => l.license_number));

test("License Numbers filter narrows the pivot to all requested licences and the Excel matches", async ({ page }) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await signIn(page);

  const normsResponse = page.waitForResponse(r => r.url().includes("/item-pivot/available-norms/"));
  await page.goto("/reports/item-pivot", { waitUntil: "domcontentloaded" });
  const norms: any[] = await (await normsResponse).json();
  expect(norms.length).toBeGreaterThan(0);

  // Find a norm whose default report has at least two licences.
  let baseline: any = null;
  let norm = "";
  for (const candidate of norms.slice(0, 8)) {
    const reportResponse = page.waitForResponse(r => isPivotReport(r) && r.url().includes(`sion_norm=${encodeURIComponent(candidate.norm_class)}`), { timeout: 120_000 });
    await page.getByRole("button", { name: new RegExp(`^\\s*${candidate.norm_class}\\b`) }).first().click();
    const report = await (await reportResponse).json();
    if (licenceNumbers(report).length >= 2) { baseline = report; norm = candidate.norm_class; break; }
  }
  test.skip(!baseline, "No norm with ≥ 2 licences in the local DB");

  const all = licenceNumbers(baseline);
  const chosen = all.slice(0, Math.min(3, all.length));
  const bogus = "E2E-NO-SUCH-LICENCE";
  const baselineRows = new Map((baseline.groups as any[]).flatMap(g => g.licenses).map((l: any) => [l.license_number, l]));

  await page.getByRole("button", { name: /Show Filters/ }).click();
  const box = page.getByRole("textbox", { name: "License Numbers" });
  await expect(box).toHaveAttribute("placeholder", "Enter license numbers separated by commas");
  // Spaces, a duplicate and an unmatched number.
  await box.fill(`  ${chosen.join(" ,  ")}, ${chosen[0]}, ${bogus} `);
  await expect(page.getByText(`${chosen.length + 1} licenses entered`)).toBeVisible();

  const filteredResponse = page.waitForResponse(r => isPivotReport(r) && r.url().includes("license_numbers="), { timeout: 120_000 });
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  const filteredRes = await filteredResponse;
  const filtered = await filteredRes.json();
  expect(new URL(filteredRes.url()).searchParams.get("sion_norm")).toBe(norm);

  expect(licenceNumbers(filtered).sort()).toEqual([...chosen].sort());
  expect(filtered.license_number_filter.matched.sort()).toEqual([...chosen].sort());
  expect(filtered.license_number_filter.not_found).toEqual([bogus]);
  // Figures for each licence are unchanged by the filter.
  for (const row of (filtered.groups as any[]).flatMap(g => g.licenses)) {
    const base: any = baselineRows.get(row.license_number);
    for (const key of ["total_cif", "debited_cif", "allotted_cif", "planned_cif", "balance_cif"]) expect(row[key]).toBe(base[key]);
  }
  const notice = page.getByTestId("license-number-filter-notice");
  await expect(notice).toContainText(`${chosen.length} of ${chosen.length + 1} matched`);
  await expect(notice).toContainText(bogus);

  // Excel: every requested licence, numeric CIF cells, totals equal the on-screen totals.
  const downloadPromise = page.waitForEvent("download", { timeout: 120_000 });
  await page.getByRole("button", { name: /excel/i }).first().click();
  const download = await downloadPromise;
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile((await download.path())!);
  const sheets = workbook.worksheets.filter(s => s.name !== "TOTAL_Summary");
  const exported: string[] = [];
  const totalsByLicenceCount: number[] = [];
  for (const sheet of sheets) {
    sheet.eachRow((row, rowNumber) => {
      if (rowNumber < 4) return;
      const first = row.getCell(1).value;
      if (typeof first === "number" && row.getCell(2).value) {
        exported.push(String(row.getCell(2).value));
        expect(typeof row.getCell(5).value).toBe("number");
      } else if (typeof first === "string" && first.startsWith("TOTAL —")) {
        totalsByLicenceCount.push(Number(row.getCell(5).value));
      }
    });
  }
  expect(exported.sort()).toEqual([...chosen].sort());
  const screenTotal = (filtered.groups as any[]).reduce((sum, g) => sum + Number(g.totals.total_cif), 0);
  expect(totalsByLicenceCount.reduce((a, b) => a + b, 0)).toBeCloseTo(screenTotal, 2);

  // Clear restores the unfiltered report.
  const clearedResponse = page.waitForResponse(r => isPivotReport(r) && !r.url().includes("license_numbers="), { timeout: 120_000 });
  await page.getByRole("button", { name: "Clear license numbers" }).click();
  const cleared = await (await clearedResponse).json();
  expect(licenceNumbers(cleared).length).toBe(all.length);
  await expect(page.getByTestId("license-number-filter-notice")).toHaveCount(0);
  expect(errors).toEqual([]);
});
