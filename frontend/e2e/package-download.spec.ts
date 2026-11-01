import { expect, test } from "@playwright/test";

/**
 * Ledger package download (current supported workflow).
 *
 * Replaces the obsolete "Download Merged PDF (1)" check (control removed in commit 79a08ac2).
 * The supported path is: select licence -> "Choose destination folder and start package download"
 * -> the server builds a package item per licence. A licence that fails the readiness gate
 * (purchase documents, final-party invoices, sale classification) is blocked and produces no PDF.
 * Positive PDF output requires a seeded licence with complete documents, which the browser seed
 * does not create yet (see the execution log).
 *
 * Native folder selection cannot be driven by Playwright, so the harness replaces
 * window.showDirectoryPicker with an in-memory directory. Nothing touches the host
 * filesystem. The test reads the written bytes back from the page and verifies them.
 */
const realBackendEnabled = process.env.LM_REAL_E2E === "1";
const licence = "3411008090";

test("ledger package blocks a licence whose required documents are missing and writes no PDF", async ({ page }) => {
  test.skip(!realBackendEnabled, "Requires the isolated seeded browser harness.");
  test.setTimeout(240000);
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(`console: ${message.text()}`); });
  page.on("response", async (response) => {
    if (!response.url().includes("license-ledger/download-package")) return;
    const body = await response.text().catch(() => "");
    let summary = body.slice(0, 200);
    try {
      const parsed = JSON.parse(body);
      summary = JSON.stringify({
        status: parsed.status,
        failed: parsed.failed,
        queued: parsed.queued,
        licences: (parsed.licences ?? []).map((l: any) => ({ licence_number: l.licence_number, status: l.status, reason: l.error ?? l.message ?? l.reason ?? l.detail ?? null })),
      });
    } catch { /* keep the raw prefix */ }
    requests.push(`${response.status()} ${response.request().method()} ${summary}`);
  });

  await page.addInitScript(() => {
    const files: Record<string, Uint8Array> = {};
    (window as any).__lmFiles = files;
    const calls: string[] = [];
    (window as any).__lmCalls = calls;
    const directory = (path: string): any => ({
      kind: "directory",
      name: path.split("/").pop(),
      requestPermission: async () => "granted",
      queryPermission: async () => "granted",
      async getDirectoryHandle(name: string) {
        calls.push(`getDirectoryHandle ${path}/${name}`);
        return directory(`${path}/${name}`);
      },
      async getFileHandle(name: string, options?: { create?: boolean }) {
        const key = `${path}/${name}`;
        calls.push(`getFileHandle ${key} create=${Boolean(options?.create)}`);
        if (!options?.create && !(key in files)) throw new DOMException(`${name} not found`, "NotFoundError");
        return {
          kind: "file",
          name,
          async getFile() {
            return new File([files[key] ?? new Uint8Array()], name, { type: "application/pdf" });
          },
          async createWritable() {
            let pending = new Uint8Array();
            return {
              async write(data: Blob | BufferSource) {
                pending = data instanceof Blob ? new Uint8Array(await data.arrayBuffer()) : new Uint8Array(data as ArrayBuffer);
              },
              async close() {
                files[key] = pending;
              },
              async abort() {},
            };
          },
        };
      },
    });
    (window as any).showDirectoryPicker = async () => {
      calls.push("showDirectoryPicker");
      return directory("picked");
    };
  });

  await page.goto("/login");
  await page.locator("#login-username").fill(process.env.LM_USERNAME || "hardik");
  await page.locator("#login-password").fill(process.env.LM_PASSWORD || "admin@123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard");
  await page.goto("/license-ledger", { waitUntil: "networkidle" });
  await page.locator("#ledger-purchase-from").fill("");
  await page.locator("#ledger-purchase-to").fill("");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });
  const numbers = page.getByText("Include License Numbers", { exact: true }).locator("..").locator("input");
  await numbers.fill(licence);
  await numbers.press("Enter");
  await page.getByText("Loading license-wise ledger").waitFor({ state: "hidden", timeout: 15000 });

  await page.getByRole("checkbox", { name: `Select licence ${licence}` }).check();
  const start = page.getByRole("button", { name: "Choose destination folder and start package download" });
  await expect(start).toBeEnabled();
  const jobPromise = page.waitForResponse((r) => r.url().includes("license-ledger/download-package/") && r.request().method() === "POST")
    .then((r) => r.json());
  await start.click();

  // Poll the in-memory folder until the verified PDF for this licence is present.
  // The package item is terminal once it leaves "queued". For this licence the
  // documented readiness gate blocks the PDF (ledger_package_recovery.licence_readiness).
  const jobId: string | undefined = (await jobPromise).job_id;
  expect(jobId, "download-package POST did not return a job_id").toBeTruthy();
  let item: any = null;
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const job = await page.evaluate(async (id) => {
      const response = await fetch(`/api/license-ledger/download-package/${id}/`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("access") ?? ""}` },
      });
      return response.ok ? response.json() : null;
    }, jobId);
    item = (job?.licences ?? []).find((entry: any) => entry.licence_number === licence) ?? null;
    if (item && item.status !== "queued") break;
    await page.waitForTimeout(500);
  }
  expect(item, `licence ${licence} never left the queued state`).not.toBeNull();
  expect(item.status).toBe("blocked_multiple_reasons");
  // The readiness detail is serialized as JSON in the item's "error" field.
  const rawReason = item.error ?? item.reason;
  const reason = typeof rawReason === "string" ? JSON.parse(rawReason) : rawReason;
  // Product rule (ledger_package_recovery.licence_readiness): "blocked_multiple_reasons" means a
  // missing purchase document AND at least one unknown-classification or missing-final-invoice sale.
  const detail = JSON.stringify(reason);
  expect(reason.missing_purchase_trade_ids?.length, detail).toBeGreaterThan(0);
  expect((reason.unknown_sale_ids?.length ?? 0) + (reason.missing_final_sale_ids?.length ?? 0), detail).toBeGreaterThan(0);

  // A blocked licence must never produce a PDF in the destination folder.
  const written = await page.evaluate(() => Object.keys((window as any).__lmFiles));
  expect(written.filter((path) => path.includes(licence))).toEqual([]);
  expect(errors).toEqual([]);
});
