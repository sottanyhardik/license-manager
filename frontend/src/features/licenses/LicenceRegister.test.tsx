/**
 * Value-equivalence proof for the redesigned licence register card.
 *
 * Replaces the old markup snapshot (LicensesTable.presentation.test.tsx). The
 * BEFORE_* tables below are the values the old card rendered (taken from that
 * snapshot and the old tab tests); every one must still be visible after the
 * redesign, in the same format. Intentional text changes are listed in
 * CHANGED_STRINGS and asserted explicitly.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));
// Inline Edit tab embeds the one licence form (MasterForm, covered by its own tests); the stub exposes its contract.
const { licenceFormProps } = vi.hoisted(() => ({ licenceFormProps: vi.fn() }));
vi.mock("@/pages/masters/MasterForm", () => ({
    default: (props: { entityName: string; recordId: number; embedded?: boolean; onSuccess?: (id: number) => void; onClose?: () => void }) => {
        licenceFormProps(props);
        return (
            <form aria-label="Licence edit form">
                <button type="button" onClick={() => { props.onSuccess?.(props.recordId); props.onClose?.(); }}>Update</button>
                <button type="button" onClick={() => props.onClose?.()}>Cancel</button>
            </form>
        );
    },
}));
vi.mock("@/utils/documentDownload", () => ({ openAuthedFile: vi.fn(() => Promise.resolve()), openDocument: vi.fn() }));

function customs(id: number) {
    if (id === 102) {
        // Negative / over-utilised, mismatched.
        return { opening_balance: 1000, total_boe_cif: 1250.75, remaining_after_boe: -250.75, total_pending_allotment_cif: 0, computed_balance: -250.75, engine_balance: -250.75, difference: 0, mismatched: true, tolerance: 0.01 };
    }
    if (id === 103) {
        // Missing fields: unavailable values are omitted, never invented.
        return { opening_balance: 987654.321, total_boe_cif: 0, remaining_after_boe: null, total_pending_allotment_cif: null, computed_balance: 987654.321, engine_balance: 987654.321, difference: 0, mismatched: false, tolerance: 0.01 };
    }
    return { opening_balance: 5000, total_boe_cif: 3000, remaining_after_boe: 2000, total_pending_allotment_cif: 765.5, computed_balance: 1234.5, engine_balance: 1234.5, difference: 0, mismatched: false, tolerance: 0.01 };
}

function ledger(id: number) {
    return {
        license: {},
        financial_ledger: {
            rows: [],
            summary: { has_trading_activity: true, missing_purchase_warning: { show_warning: false, message: "" } },
        },
        customs_ledger: { rows: [], summary: customs(id) },
        reconciliation: { financial_ledger_balance: 11, customs_ledger_balance: 22, balance_engine: 33, difference: id === 102 ? 4 : 0, tolerance: 0.01, matched: id !== 102 },
        warnings: [],
        timeline: [],
    };
}

vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            const id = Number(url.split("/")[1]);
            const empty = id === 104;
            if (url.endsWith("/balance-ledger/")) return Promise.resolve({ data: ledger(id) });
            if (url.endsWith("/overview-items/")) {
                return Promise.resolve({ data: { rows: empty ? [] : [{ id: 1, description: `Item of ${id}`, hs_code: "1701", unit: "kg", total_qty: 10, total_cif: 100, debited_qty: 1, debited_cif: 10, allotted_qty: 2, allotted_cif: 20, balance_qty: 7, balance_cif: 70 }] } });
            }
            if (url.endsWith("/overview-boes/")) {
                return Promise.resolve({ data: empty ? [] : [{ bill_of_entry_number: `BOE-${id}`, bill_of_entry_date: "2025-01-02", port: "INNSA1", supplier: "S", invoice_no: "I1", invoice_date: null, cif_fc: 10, status: "Pending" }] });
            }
            if (url.endsWith("/overview-allotments/")) {
                return Promise.resolve({ data: empty ? [] : [{ allotment_number: `ALT-${id}`, date: null, customer: "C", product: "P", quantity: 1, cif_fc: 5, status: "Pending" }] });
            }
            if (url.endsWith("/overview-invoice-ledger/")) {
                return Promise.resolve({ data: { purchase: [], sale: [], warning: { show_warning: !empty, message: `Invoice warning for ${id}` } } });
            }
            if (url.startsWith("license-actions/") && url.endsWith("/ownership-data/")) {
                if (id === 105) return Promise.resolve({ data: null });
                return Promise.resolve({ data: { license_number: String(id), last_ownership_fetch: null, file_transfer_status: null, current_owner: empty ? null : { iec: "X", name: `Owner of ${id}`, address: null }, transfers: [] } });
            }
            if (url.endsWith("/balance-pdf/") || url.endsWith("/merged-documents/")) return Promise.resolve({ data: new Blob(["%PDF"]) });
            // Planning bodies stay loading; only their requests matter here.
            return new Promise(() => {});
        }),
        post: vi.fn(() => Promise.resolve({ data: { message: "planned" } })),
        patch: vi.fn(() => new Promise(() => {})),
    },
}));

import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import { LICENSE_FIXTURE, renderLicensesTable, type Role } from "./testUtils";

const get = api.get as unknown as ReturnType<typeof vi.fn>;
const post = api.post as unknown as ReturnType<typeof vi.fn>;
const requested = () => get.mock.calls.map((c) => c[0] as string);

/** Collapsed header values rendered BEFORE (old snapshot), in their exact format. */
const BEFORE_HEADER: Record<number, string[]> = {
    101: ["0310123456", "05-01-2020", "Exp: 04-01-2021", "Ledger: 10-02-2020", "INNSA1", "Alpha Exports", "DFIA", "Expired", "Available CIF", "$1,234.50"],
    102: ["0310654321", "15-08-2024", "Exp: 14-08-2099", "INMAA1", "Beta Foods", "Advance", "Exhausted", "Available CIF", "$-250.75", "Over-utilised"],
    103: ["0310777777", "01-12-2025", "Exp: 30-11-2099", "Ledger: 02-12-2025", "Planned", "Available CIF", "$987,654.32"],
    104: ["0310000004", "INBOM4", "Gamma", "DFIA", "Exhausted", "Available CIF", "$0.00"],
    105: ["—", "29-02-2024", "Exp: 28-02-2099", "Ledger: 01-03-2024", "INNSA1", "Delta", "DFIA", "Exhausted", "Available CIF", "$0.00"],
};
/** Old expanded info strip: label → value ("—" when missing). */
const BEFORE_STRIP: Record<number, [string, string][]> = {
    101: [["Norm Class", "E1"], ["IEC", "0301000001"], ["Transfer Status", "Transferred to Beta"]],
    102: [["Norm Class", "E5"], ["IEC", "0301000002"]],
    103: [["Transfer Status", "Pending"]],
    104: [["Norm Class", "A3"], ["IEC", "0301000004"]],
    105: [["Norm Class", "E1"], ["IEC", "0301000005"]],
};
/** Old unique actions per role (ActionPanel + Edit Options; "Edit licence" was the same handler as "Edit"). */
const BEFORE_ACTIONS: Record<Role, string[]> = {
    LICENSE_MANAGER: ["License Overview", "Auto Plan", "Balance PDF", "Balance Excel", "Fetch from DGFT", "Delete", "Edit", "Recalculate / hide-restore BOE (License Overview)"],
    LICENSE_VIEWER: ["License Overview", "Balance PDF", "Balance Excel"],
};
/** Every intentional visible-text change, asserted below. */
const CHANGED_STRINGS = {
    importTabLabel: { before: "Import Item", after: "Import Items" },
    historyEmptyHint: {
        before: "Click 'Fetch from DGFT' in the action panel to load ownership history.",
        after: "Use 'Fetch from DGFT' in the Actions menu to load ownership history.",
    },
    removedTabs: ["Edit Options"],
    addedTabs: ["Reconciliation", "Edit"], // Edit: inline licence edit (writers), replaces the /licenses/:id/edit page
    duplicateRemoved: "Edit licence", // merged into the single "Edit" action
    /** Owner-approved CIF unification: new financial summary uses the card's `$` en-US formatter. */
    summaryCifFormat: { field: "customs_ledger.summary.opening_balance", value: 5000, rendered: "$5,000.00" },
};

const ROLES: Role[] = ["LICENSE_MANAGER", "LICENSE_VIEWER"];

function card(id: number) {
    const item = LICENSE_FIXTURE.find((i) => i.id === id)!;
    return screen.getByRole("article", { name: `License ${item.license_number || id}` });
}
function expandButton(id: number) {
    return within(card(id)).getByRole("button", { name: /^(Expand|Collapse) license/ });
}
async function expand(user: ReturnType<typeof userEvent.setup>, id: number) {
    await user.click(expandButton(id));
    return document.getElementById(`license-content-${id}`) as HTMLElement;
}
async function openMenu(user: ReturnType<typeof userEvent.setup>, id: number) {
    const region = document.getElementById(`license-content-${id}`)!;
    await user.click(within(region).getByRole("button", { name: /^Actions for license/ }));
    return screen.findByRole("menu");
}
function fieldValue(region: HTMLElement, label: string) {
    const dt = within(region).getAllByText(label, { selector: "dt" })[0];
    return dt.nextElementSibling?.textContent;
}

describe("Licence register card — value equivalence", () => {
    beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });
    afterEach(() => cleanup());

    for (const role of ROLES) {
        it(`(1) every header and strip value from before is still visible, same format (${role})`, async () => {
            const user = userEvent.setup();
            renderLicensesTable(role);
            for (const item of LICENSE_FIXTURE) {
                const text = card(item.id).textContent ?? "";
                for (const v of BEFORE_HEADER[item.id]) expect(text, `${item.id} collapsed: ${v}`).toContain(v);
            }
            for (const item of LICENSE_FIXTURE) {
                const region = await expand(user, item.id);
                const cardText = card(item.id).textContent ?? "";
                // Balance CIF stays visible once (header) while expanded — was in the old strip.
                for (const v of BEFORE_HEADER[item.id]) expect(cardText, `${item.id} expanded: ${v}`).toContain(v);
                for (const [label, value] of BEFORE_STRIP[item.id]) expect(fieldValue(region, label), `${item.id} ${label}`).toBe(value);
                // Individual-CIF switch: one instance (was two), same text.
                expect(within(region).getAllByRole("switch", { name: "Individual Item CIF" })).toHaveLength(1);
                expect(region.textContent).toContain(item.individual_item_cif_override ? "Individual item CIF" : "Licence-level CIF");
            }
        });
    }

    it("(1) status text equals the existing deriveStatus result and keeps danger styling for expired / negative", () => {
        renderLicensesTable("LICENSE_MANAGER");
        const statuses = LICENSE_FIXTURE.map((i) => within(card(i.id)).getByText(/^(Expired|Exhausted|Planned|Active)$/).textContent);
        expect(statuses).toEqual(["Expired", "Exhausted", "Planned", "Exhausted", "Exhausted"]);
        expect(within(card(101)).getByText("Exp: 04-01-2021").closest("span")).toHaveClass("text-destructive");
        expect(within(card(102)).getByText("$-250.75")).toHaveClass("text-destructive");
        expect(within(card(102)).getByLabelText("Over-utilised: licence CIF balance is negative")).toBeInTheDocument();
        expect(within(card(101)).queryByText("Over-utilised")).toBeNull();
    });

    it("(1) financial summary maps each figure to customs_ledger.summary, $ en-US, negatives in danger, missing omitted", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_MANAGER");

        let region = await expand(user, 101);
        const summary = await within(region).findByRole("region", { name: "Financial summary" });
        const s = within(summary);
        expect(fieldValue(summary, "Original CIF")).toBe(CHANGED_STRINGS.summaryCifFormat.rendered);
        expect(fieldValue(summary, "BOE CIF")).toBe("$3,000.00");
        expect(fieldValue(summary, "Remaining After BOE")).toBe("$2,000.00");
        expect(fieldValue(summary, "Outstanding Allotment CIF")).toBe("$765.50");
        expect(fieldValue(summary, "Available CIF (customs)")).toBe("$1,234.50");
        expect(fieldValue(summary, "Difference")).toBe("$0.00");
        expect(s.getByText("Reconciled")).toBeInTheDocument();

        region = await expand(user, 102);
        const neg = await within(region).findByRole("region", { name: "Financial summary" });
        expect(within(neg).getAllByText("$-250.75")).toHaveLength(2);
        within(neg).getAllByText("$-250.75").forEach((el) => expect(el).toHaveClass("text-destructive"));
        expect(within(neg).getByText("Reconciliation Failed")).toBeInTheDocument();

        region = await expand(user, 103);
        const missing = await within(region).findByRole("region", { name: "Financial summary" });
        expect(within(missing).queryByText("Remaining After BOE")).toBeNull();
        expect(within(missing).queryByText("Outstanding Allotment CIF")).toBeNull();
        expect(fieldValue(missing, "Available CIF (customs)")).toBe("$987,654.32");
    });

    it("(1) every old tab body still shows its values; changed strings are the listed ones only", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_MANAGER");
        const region = await expand(user, 101);
        const tabs = within(region).getAllByRole("tab").map((t) => t.textContent);
        expect(tabs).toEqual(["Overview", CHANGED_STRINGS.importTabLabel.after, "BOE & Allotment", "Invoices", "Planning", ...CHANGED_STRINGS.addedTabs, "History"]);
        for (const removed of CHANGED_STRINGS.removedTabs) expect(tabs).not.toContain(removed);
        expect(tabs).not.toContain(CHANGED_STRINGS.importTabLabel.before);

        await user.click(within(region).getByRole("tab", { name: "Import Items" }));
        expect(await within(region).findByText("Item of 101")).toBeInTheDocument();
        await user.click(within(region).getByRole("tab", { name: "BOE & Allotment" }));
        expect(await within(region).findByText("BOE-101")).toBeInTheDocument();
        expect(await within(region).findByText("ALT-101")).toBeInTheDocument();
        await user.click(within(region).getByRole("tab", { name: "Invoices" }));
        expect(await within(region).findByText("Invoice warning for 101")).toBeInTheDocument();
        await user.click(within(region).getByRole("tab", { name: "Reconciliation" }));
        expect(await within(region).findByText("Financial Ledger Balance")).toBeInTheDocument();
        await user.click(within(region).getByRole("tab", { name: "History" }));
        expect(await within(region).findByText("Owner of 101")).toBeInTheDocument();
        // Duplicate "Items" body is gone from Overview.
        await user.click(within(region).getByRole("tab", { name: "Overview" }));
        await within(region).findByRole("region", { name: "Financial summary" });
        expect(within(region).queryByText("Item of 101")).toBeNull();
    });

    it("(1) History empty hint is the listed changed string", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_VIEWER");
        const region = await expand(user, 105); // ownership-data returns no data for 105
        await user.click(within(region).getByRole("tab", { name: "History" }));
        expect(await within(region).findByText(CHANGED_STRINGS.historyEmptyHint.after)).toBeInTheDocument();
        expect(within(region).queryByText(CHANGED_STRINGS.historyEmptyHint.before)).toBeNull();
    });
});

describe("Licence register card — actions per role", () => {
    beforeEach(() => vi.clearAllMocks());
    afterEach(() => cleanup());

    for (const role of ROLES) {
        it(`(2) one ActionMenu with the same unique action set as before (${role})`, async () => {
            const user = userEvent.setup();
            renderLicensesTable(role);
            const region = await expand(user, 101);
            expect(within(region).getAllByRole("button", { name: /^Actions for license/ })).toHaveLength(1);
            // No stray action buttons outside the menu (old panel / Edit Options removed).
            expect(within(region).queryByRole("button", { name: /^(Edit|Edit licence|Delete|Balance PDF)$/ })).toBeNull();
            const menu = await openMenu(user, 101);
            const labels = within(menu).getAllByRole("menuitem").map((m) => m.textContent?.trim());
            expect([...labels].sort()).toEqual([...BEFORE_ACTIONS[role]].sort());
            expect(labels).not.toContain(CHANGED_STRINGS.duplicateRemoved);
            // Grouping: primary first, destructive last.
            expect(labels[0]).toBe("License Overview");
            if (role === "LICENSE_MANAGER") expect(labels[labels.length - 1]).toBe("Delete");
        });
    }

    it("(2) handlers call the same endpoints / navigation as before", async () => {
        const user = userEvent.setup();
        const { props } = renderLicensesTable("LICENSE_MANAGER");
        await expand(user, 101);
        const pick = async (name: string) => {
            const menu = await openMenu(user, 101);
            await user.click(within(menu).getByRole("menuitem", { name }));
        };

        await pick("License Overview");
        expect(props.navigate).toHaveBeenLastCalledWith("/licenses/101/overview");
        await pick("Recalculate / hide-restore BOE (License Overview)");
        expect(props.navigate).toHaveBeenLastCalledWith("/licenses/101/overview");
        await pick("Edit");
        // Edit now opens the licence's Edit tab inline; it never navigates to the old edit page.
        expect(props.navigate).not.toHaveBeenCalledWith("/licenses/101/edit");
        expect(await screen.findByRole("tab", { name: "Edit", selected: true })).toBeInTheDocument();
        await pick("Balance PDF");
        await waitFor(() => expect(get).toHaveBeenCalledWith("licenses/101/balance-pdf/", { responseType: "blob" }));
        await pick("Balance Excel");
        await waitFor(() => expect(openAuthedFile).toHaveBeenCalledWith("licenses/101/balance-excel/", "0310123456-balance.xlsx"));
        await pick("Auto Plan");
        await waitFor(() => expect(post).toHaveBeenCalledWith("licenses/101/auto-plan/", { force: true }));
        await pick("Fetch from DGFT");
        expect(props.onFetchOwnership).toHaveBeenCalledWith(expect.objectContaining({ id: 101 }));
        await pick("Delete");
        // Existing confirmation flow lives in the caller's onDelete (MasterList.handleDelete).
        expect(props.onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: 101 }));

        // Licence number still opens the merged documents, without toggling the card.
        await user.click(within(card(103)).getByRole("button", { name: "View documents for license 0310777777" }));
        await waitFor(() => expect(get).toHaveBeenCalledWith("licenses/103/merged-documents/", expect.objectContaining({ responseType: "blob" })));
        expect(expandButton(103)).toHaveAttribute("aria-expanded", "false");
    });
});

describe("Licence register card — requests, panels, isolation, a11y", () => {
    beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });
    afterEach(() => cleanup());

    it("(3) expanding makes 1 request (before: 1, overview-items/); summary-backed tabs add 0", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_MANAGER");
        expect(get).not.toHaveBeenCalled();
        const region = await expand(user, 101);
        await within(region).findByRole("region", { name: "Financial summary" });
        expect(requested()).toEqual(["licenses/101/balance-ledger/"]);
        expect(requested().filter((u) => u === "licenses/101/")).toHaveLength(0);

        get.mockClear();
        await user.click(within(region).getByRole("button", { name: "Financial ledger" }));
        await user.click(within(region).getByRole("tab", { name: "Reconciliation" }));
        await within(region).findByText("Financial Ledger Balance");
        expect(requested()).toEqual([]);

        const step = async (tab: string, expected: string[]) => {
            get.mockClear();
            await user.click(within(region).getByRole("tab", { name: tab }));
            await waitFor(() => expect([...requested()].sort()).toEqual([...expected].sort()));
        };
        await step("Import Items", ["licenses/101/overview-items/"]);
        await step("BOE & Allotment", ["licenses/101/overview-boes/", "licenses/101/overview-allotments/"]);
        await step("Invoices", ["licenses/101/overview-invoice-ledger/"]);
        await step("History", ["license-actions/101/ownership-data/"]);
    });

    it("(4) no tab renders an empty panel (zero-record licence)", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_MANAGER");
        const region = await expand(user, 104);
        for (const tab of ["Overview", "Import Items", "BOE & Allotment", "Invoices", "Planning", "Reconciliation", "Edit", "History"]) {
            await user.click(within(region).getByRole("tab", { name: tab }));
            const panel = within(region).getByRole("tabpanel");
            // Content = visible text, or a loading skeleton while a reused body (Planning) fetches.
            await waitFor(() => expect(!!panel.textContent?.trim() || !!panel.querySelector('[data-slot="skeleton"]'), tab).toBe(true));
            expect(panel.className).not.toMatch(/min-h-/);
        }
        await user.click(within(region).getByRole("tab", { name: "History" }));
        expect(await within(region).findByText("No transfer history")).toBeInTheDocument();
    });

    it("(4b) licence Edit is inline: the record's own form, save refreshes in place, cancel returns to Overview", async () => {
        const user = userEvent.setup();
        const { props } = renderLicensesTable("LICENSE_MANAGER");
        const region = await expand(user, 101);
        const menu = await openMenu(user, 101);
        await user.click(within(menu).getByRole("menuitem", { name: "Edit" }));
        expect(await within(region).findByRole("form", { name: "Licence edit form" })).toBeInTheDocument();
        expect(licenceFormProps).toHaveBeenLastCalledWith(expect.objectContaining({ entityName: "licenses", recordId: 101, embedded: true }));

        await user.click(within(region).getByRole("button", { name: "Update" }));
        expect(await within(region).findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
        await user.click(within(region).getByRole("tab", { name: "Edit" }));
        await user.click(within(region).getByRole("button", { name: "Cancel" }));
        expect(within(region).getByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();
        // The list was never left (no navigation to an edit page).
        expect(props.navigate).not.toHaveBeenCalled();
    });

    it("(4c) viewers get no Edit tab and no Edit action", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_VIEWER");
        const region = await expand(user, 101);
        expect(within(region).queryByRole("tab", { name: "Edit" })).not.toBeInTheDocument();
        const menu = await openMenu(user, 101);
        expect(within(menu).queryByRole("menuitem", { name: "Edit" })).not.toBeInTheDocument();
    });

    it("(5) cross-record isolation: one open card, B never shows A's data", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_MANAGER");
        const a = await expand(user, 101);
        await user.click(within(a).getByRole("tab", { name: "Invoices" }));
        expect(await within(a).findByText("Invoice warning for 101")).toBeInTheDocument();

        const b = await expand(user, 102);
        expect(document.getElementById("license-content-101")).toBeNull();
        expect(expandButton(101)).toHaveAttribute("aria-expanded", "false");
        expect(within(b).getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
        await user.click(within(b).getByRole("tab", { name: "Invoices" }));
        expect(await within(b).findByText("Invoice warning for 102")).toBeInTheDocument();
        expect(screen.queryByText("Invoice warning for 101")).toBeNull();
        await user.click(within(b).getByRole("tab", { name: "History" }));
        expect(await within(b).findByText("Owner of 102")).toBeInTheDocument();
        expect(screen.queryByText("Owner of 101")).toBeNull();
    });

    it("(6) keyboard and aria: expand button, region, tabs, menu", async () => {
        const user = userEvent.setup();
        renderLicensesTable("LICENSE_VIEWER");
        const btn = expandButton(101);
        expect(btn).toHaveAttribute("aria-controls", "license-content-101");
        expect(btn).toHaveAttribute("aria-expanded", "false");
        act(() => btn.focus());
        await user.keyboard("{Enter}");
        expect(expandButton(101)).toHaveAttribute("aria-expanded", "true");
        const region = screen.getByRole("region", { name: "License 0310123456 details" });
        expect(region.id).toBe("license-content-101");
        expect(within(region).getByRole("tablist", { name: "License 0310123456 sections" })).toBeInTheDocument();

        const overview = within(region).getByRole("tab", { name: "Overview" });
        act(() => overview.focus());
        await user.keyboard("{ArrowRight}");
        const items = within(region).getByRole("tab", { name: "Import Items" });
        expect(items).toHaveFocus();
        expect(items).toHaveAttribute("aria-selected", "true");

        const trigger = within(region).getByRole("button", { name: "Actions for license 0310123456" });
        act(() => trigger.focus());
        await user.keyboard("{Enter}");
        expect(await screen.findByRole("menu")).toBeInTheDocument();
        await user.keyboard("{Escape}");
        await waitFor(() => expect(screen.queryByRole("menu")).toBeNull());

        act(() => expandButton(101).focus());
        await user.keyboard(" ");
        expect(document.getElementById("license-content-101")).toBeNull();
    });
});
