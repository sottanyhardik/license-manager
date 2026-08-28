import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api/axios";
import ItemPivotReport from "./ItemPivotReport";

// Preserve router exports used by the report itself.  The old narrow mock
// hid useSearchParams and made the rendering suite fail before exercising
// the report.
vi.mock("react-router-dom", async (importOriginal) => ({
    ...(await importOriginal<typeof import("react-router-dom")>()),
    useNavigate: () => vi.fn(),
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock("../../api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        dismiss: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
        success: vi.fn(),
    },
}));

const mockedApiGet = vi.mocked(api.get);

// One license, one norm (E1), two item columns:
//   - "FRUIT JUICE - E1": three real import items (same HSN + normalized
//     description, just inconsistent slash-spacing) already merged by the
//     backend into ONE `planned_import_items` entry — the common case.
//   - "PP - E1": two GENUINELY different products (different description)
//     sharing one item-name column — the backend leaves these unmerged, so
//     the UI must render one aligned line per product across every column.
const REPORT_DATA = {
    items: [
        { id: 1, name: "FRUIT JUICE - E1", has_restriction: false },
        { id: 2, name: "PP - E1", has_restriction: false },
    ],
    licenses_by_norm_notification: {
        E1: {
            "Global Exim — NOTIF-1": [
                {
                    id: 100,
                    license_number: "LIC-MERGE-TEST",
                    license_date: "2026-01-01",
                    license_expiry_date: "2026-12-31",
                    ledger_date: null,
                    exporter: "Test Exporter",
                    port: "",
                    notification_number: "NOTIF-1",
                    purchase_status_code: "GE",
                    purchase_status_label: "Global Exim",
                    total_cif: 1000,
                    debited_cif: 0,
                    alloted_cif: 0,
                    balance_cif: 1000,
                    balance_report_notes: "",
                    condition_sheet: "",
                    latest_transfer: "",
                    has_tl: false,
                    has_copy: false,
                    plan_source: "norm",
                    items: {
                        "FRUIT JUICE - E1": {
                            hs_code: "20089991",
                            description: "Fruit/Juice",
                            quantity: 300,
                            allotted_quantity: 0,
                            debited_quantity: 0,
                            available_quantity: 300,
                            planned_import_items: [
                                {
                                    import_item_id: 1,
                                    import_item_ids: [1, 2, 3],
                                    hs_code: "20089991",
                                    description: "Fruit/Juice",
                                    quantity: 300,
                                    allotted_quantity: 0,
                                    debited_quantity: 0,
                                    available_quantity: 300,
                                    planned_quantity: 300,
                                    planned_cif_fc: 750,
                                    unit_price: 2.5,
                                },
                            ],
                            restriction: null,
                            restriction_value: 0,
                            unit_price: 2.5,
                            planned_cif: 750,
                            plan_quantity: 0,
                            plan_cif: 0,
                            // Backend-resolved manual-vs-norm selection (Phase 2B.2A) —
                            // no manual plan here, so this equals planned_cif.
                            effective_planned_cif: 750,
                            splits: [],
                            condition_type: "",
                        },
                        "PP - E1": {
                            hs_code: "",
                            description: "",
                            // HSN/Description are blank (strings can't be merged across
                            // distinct products), but Quantity/Allotted/Debited/Available
                            // ARE already summed across both products by the backend
                            // (see _build_license_row in item_pivot_report.py) — these
                            // match 111+222 / 11+22 / 1+2 / 120+230 from the two
                            // `planned_import_items` entries below (available_quantity
                            // deliberately doesn't total 300, to stay distinguishable
                            // from the "FRUIT JUICE - E1" column's own 300s).
                            quantity: 333,
                            allotted_quantity: 33,
                            debited_quantity: 3,
                            available_quantity: 350,
                            // planned_import_items is the verification breakdown only
                            // (per-product HSN/Description) — Plan Qty/Planned CIF are
                            // NOT read from here; they come from the cell-level
                            // plan_quantity/plan_cif/unit_price/planned_cif fields
                            // below, which the backend already totals across the whole
                            // item-name column independent of how many distinct
                            // products compose it (see row_data['items'][item_name] in
                            // item_pivot_report.py).
                            planned_import_items: [
                                {
                                    import_item_id: 10,
                                    import_item_ids: [10],
                                    hs_code: "39021000",
                                    description: "Packing Material Batch A",
                                    quantity: 111,
                                    allotted_quantity: 11,
                                    debited_quantity: 1,
                                    available_quantity: 120,
                                    planned_quantity: 90,
                                    planned_cif_fc: 108,
                                    unit_price: 1.2,
                                },
                                {
                                    import_item_id: 11,
                                    import_item_ids: [11],
                                    hs_code: "39021000",
                                    description: "Packing Material Batch B",
                                    quantity: 222,
                                    allotted_quantity: 22,
                                    debited_quantity: 2,
                                    available_quantity: 230,
                                    planned_quantity: 180,
                                    planned_cif_fc: 270,
                                    unit_price: 1.5,
                                },
                            ],
                            restriction: null,
                            restriction_value: 0,
                            unit_price: 1.35,
                            planned_cif: 378,
                            plan_quantity: 270,
                            plan_cif: 378,
                            // Backend-resolved manual-vs-norm selection (Phase 2B.2A) —
                            // manually planned, so this equals plan_cif, not planned_cif.
                            effective_planned_cif: 378,
                            splits: [],
                            condition_type: "",
                        },
                    },
                    // License-level Planned CIF total — backend sum of every item
                    // column's own effective_planned_cif (750 + 378).
                    total_effective_planned_cif: 1128,
                },
            ],
        },
    },
    // Backend-computed grand totals for this (norm, notification) group
    // (Phase 2B.2A) — the footer TOTAL row reads these directly.
    notification_totals: {
        E1: {
            "Global Exim — NOTIF-1": {
                total_cif: 1000,
                debited_cif: 0,
                alloted_cif: 0,
                balance_cif: 1000,
                total_effective_planned_cif: 1128,
                items: {
                    "FRUIT JUICE - E1": {
                        quantity: 300, allotted_quantity: 0, debited_quantity: 0,
                        available_quantity: 300, restriction_value: 0,
                        plan_quantity: 0, effective_planned_cif: 750,
                    },
                    "PP - E1": {
                        quantity: 333, allotted_quantity: 33, debited_quantity: 3,
                        available_quantity: 350, restriction_value: 0,
                        plan_quantity: 270, effective_planned_cif: 378,
                    },
                },
            },
        },
    },
    // Backend-owned Notification/Norm Summary (Phase 2B.2B) — deliberately
    // distinct from anything derivable from `licenses` above (which has
    // balance_cif 1000, planned_cif 750/378, etc.) so the render tests below
    // can prove these panels are sourced from these fields, not recomputed
    // locally. "10.0" uses the backend's Python str(float) key format (see
    // design doc §13) to exercise the percentage-key display fix.
    notification_summary: {
        E1: {
            "Global Exim — NOTIF-1": {
                opening_balance: 555.55,
                total_available: 444.44,
                total_planned_cif: 333.33,
                total_planned_qty: 22.22,
                blended_unit_price: 15,
                regular_items: {
                    "FRUIT JUICE - E1": {
                        available: 111.11,
                        planned_cif: 222.22,
                        planned_qty: 10,
                        unit_price: 22.22,
                    },
                },
                restricted_items_by_percentage: {
                    "10.0": {
                        shared_restriction_value: 999.99,
                        items: {
                            "PP - E1": {
                                available: 50,
                                planned_cif: 60,
                                planned_qty: 5,
                                unit_price: 12,
                            },
                        },
                    },
                },
            },
        },
    },
    norm_summary: {
        E1: {
            opening_balance: 777.77,
            total_available: 666.66,
            total_planned_cif: 888.88,
            total_planned_qty: 33.33,
            blended_unit_price: 16.67,
            regular_items: {
                "FRUIT JUICE - E1": {
                    available: 121.21,
                    planned_cif: 232.32,
                    planned_qty: 11,
                    unit_price: 21.12,
                },
            },
            restricted_items_by_percentage: {},
        },
    },
    norm_notes_conditions: { E1: { notes: [], conditions: [] } },
    report_date: "2026-01-08",
};

function mockApi() {
    mockedApiGet.mockImplementation((url: string) => {
        if (url.startsWith("item-pivot/available-norms/")) {
            return Promise.resolve({ data: [{ norm_class: "E1", description: "Confectionery" }] });
        }
        if (url.startsWith("masters/sion-classes/")) {
            return Promise.resolve({ data: { results: [] } });
        }
        if (url.startsWith("masters/purchase-statuses/")) {
            return Promise.resolve({ data: { results: [] } });
        }
        if (url.startsWith("reports/item-pivot/")) {
            return Promise.resolve({ data: REPORT_DATA });
        }
        return Promise.resolve({ data: {} });
    });
}

async function renderAndSelectNorm() {
    render(<ItemPivotReport />);
    const normButtons = await screen.findAllByRole("button", { name: /E1/ });
    fireEvent.click(normButtons[0]);
    return screen.findByText("LIC-MERGE-TEST");
}

describe("ItemPivotReport — merged vs. genuinely-distinct import items", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApi();
    });

    it("renders an already-merged item (single planned_import_items entry) as one flat set of values, no stacking or badge", async () => {
        await renderAndSelectNorm();
        const row = screen.getByText("LIC-MERGE-TEST").closest("tr") as HTMLElement;

        // The merged HSN/description/quantity appear once, plainly.
        expect(within(row).getByText("20089991")).toBeInTheDocument();
        expect(within(row).getByText("750.00")).toBeInTheDocument(); // Planned CIF

        // The row also has a genuinely-ambiguous "PP - E1" column (asserted
        // in the next test) — its merge-count badge must not leak onto the
        // already-merged "FRUIT JUICE - E1" column: exactly one badge in the
        // whole row, not two.
        expect(within(row).getAllByText(/\d+ items/)).toHaveLength(1);
    });

    it("renders license and item Remaining CIF columns after reconciliation", async () => {
        await renderAndSelectNorm();
        const row = screen.getByText("LIC-MERGE-TEST").closest("tr") as HTMLElement;

        expect(screen.getAllByRole("columnheader", { name: "Remaining CIF" }).length).toBeGreaterThanOrEqual(1);

        // FRUIT JUICE - E1 (no manual plan) contributes its norm-derived
        // planned_cif (750); PP - E1 (manually planned) contributes its
        // plan_cif (378) instead of planned_cif — same per-item formula the
        // "Planned CIF" item column and the notification-level total use.
        expect(within(row).getByText("1128.00")).toBeInTheDocument();
    });

    it("renders genuinely distinct products sharing one column as a comma-separated HSN/description with summed totals", async () => {
        await renderAndSelectNorm();
        const row = screen.getByText("LIC-MERGE-TEST").closest("tr") as HTMLElement;

        // Badge communicates why this cell couldn't be merged into one row.
        expect(within(row).getByText("2 items")).toBeInTheDocument();

        // HSN and Description are comma-separated, one per distinct product —
        // never glued together with no separator.
        expect(within(row).getByText("39021000, 39021000")).toBeInTheDocument();
        expect(within(row).getByText("Packing Material Batch A, Packing Material Batch B")).toBeInTheDocument();

        // Total / Allotted / Debited / Available show the backend's already-
        // summed totals as ONE number, not a per-product breakdown.
        expect(within(row).getByText("333.000")).toBeInTheDocument();
        expect(within(row).getByText("33.000")).toBeInTheDocument();
        expect(within(row).getByText("3.000")).toBeInTheDocument();
        expect(within(row).getByText("350.000")).toBeInTheDocument();

        // Plan Qty / Planned CIF are the cell-level totals (already summed by
        // the backend across the whole item-name column), shown as ONE
        // number — not read from the per-product planned_import_items list.
        expect(within(row).getByText("270.000")).toBeInTheDocument();
        expect(within(row).getByText("378.00")).toBeInTheDocument();
    });
});

describe("ItemPivotReport — Compact Scroll Mode", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApi();
    });

    it("removes Exporter/Total/Debited/Alloted/Planned CIF from the table entirely while scrolled (no reserved space), and restores them once scrolled back to the left — without touching the frozen or item-panel columns", async () => {
        await renderAndSelectNorm();

        const scrollContainer = screen.getByTestId("pivot-scroll-container");

        // Resting position (scrollLeft 0): every column is rendered.
        expect(screen.getAllByRole("columnheader", { name: "Exporter" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "Total CIF" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "Debited CIF" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "Alloted CIF" }).length).toBeGreaterThan(0);

        // User scrolls right — the mid-table columns are removed from the
        // table entirely (not styled to zero size — actually absent from
        // the DOM, so they can't reserve layout space). The frozen columns
        // (Sr No, Balance CIF) and the item-panel columns (HSN Code) are
        // untouched either way, since they were never part of the hideable
        // set.
        Object.defineProperty(scrollContainer, "scrollLeft", { value: 120, configurable: true });
        fireEvent.scroll(scrollContainer);
        expect(screen.queryByRole("columnheader", { name: "Exporter" })).not.toBeInTheDocument();
        expect(screen.queryByRole("columnheader", { name: "Total CIF" })).not.toBeInTheDocument();
        expect(screen.queryByRole("columnheader", { name: "Debited CIF" })).not.toBeInTheDocument();
        expect(screen.queryByRole("columnheader", { name: "Alloted CIF" })).not.toBeInTheDocument();
        expect(screen.getAllByRole("columnheader", { name: "Sr No" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "Balance CIF" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "HSN Code" }).length).toBeGreaterThan(0);

        // User scrolls back to the resting position — automatic restore,
        // no refresh, no lingering state.
        Object.defineProperty(scrollContainer, "scrollLeft", { value: 0, configurable: true });
        fireEvent.scroll(scrollContainer);
        expect(screen.getAllByRole("columnheader", { name: "Exporter" }).length).toBeGreaterThan(0);
        expect(screen.getAllByRole("columnheader", { name: "Total CIF" }).length).toBeGreaterThan(0);
    });

    it("keeps the entire two-row header (license-identity columns + per-item sub-columns) inside one sticky-top thead, so it stays fixed on vertical scroll", async () => {
        await renderAndSelectNorm();

        const srNoHeader = screen.getAllByRole("columnheader", { name: "Sr No" })[0];
        const hsnHeader = screen.getAllByRole("columnheader", { name: "HSN Code" })[0];
        const totalQtyHeader = screen.getAllByRole("columnheader", { name: "Total QTY" })[0];
        const planQtyHeader = screen.getAllByRole("columnheader", { name: "Plan Qty" })[0];

        const thead = srNoHeader.closest("thead") as HTMLElement;
        expect(thead).not.toBeNull();
        // The notification header is frozen at the viewport top, so the
        // matrix header remains sticky directly below it rather than covering
        // the notification context.
        expect(thead).toHaveStyle({ position: "sticky", top: "74px" });

        // Both header rows — the license-identity row AND the per-item
        // sub-column row (HSN/Description/Qty/.../Plan Qty) — must live
        // inside that SAME sticky thead, not a second, non-sticky one.
        expect(hsnHeader.closest("thead")).toBe(thead);
        expect(totalQtyHeader.closest("thead")).toBe(thead);
        expect(planQtyHeader.closest("thead")).toBe(thead);
    });

    it("gives DFIA No, Expiry Dt, and Balance CIF a non-negative, numeric sticky `left` derived from measured widths rather than a hard-coded guess", async () => {
        await renderAndSelectNorm();

        const dfiaHeader = screen.getAllByRole("columnheader", { name: "DFIA No" })[0];
        const expiryHeader = screen.getAllByRole("columnheader", { name: "Expiry Dt" })[0];
        const balanceHeader = screen.getAllByRole("columnheader", { name: "Balance CIF" })[0];

        for (const el of [dfiaHeader, expiryHeader, balanceHeader]) {
            expect(el.style.position).toBe("sticky");
            // Left is a computed pixel value (possibly "0px" in jsdom, which
            // never lays out real content) — never left unset, and never a
            // literal leftover like "NaNpx".
            expect(el.style.left).toMatch(/^-?\d+(\.\d+)?px$/);
        }
    });
});

// Phase 2B.2B (frontend cutover) — the per-notification "Summary" panel and
// the "Norms Total Summary" card must be pure rendering of the backend's
// notification_summary/norm_summary objects, with zero local aggregation.
// REPORT_DATA's notification_summary/norm_summary fixtures above are
// deliberately different from anything derivable from `licenses` (which has
// its own balance_cif/planned_cif numbers) so these tests fail loudly if the
// panel ever goes back to recomputing from `licenses` instead of reading the
// backend fields directly.
describe("ItemPivotReport — Notification/Norm Summary panel (Phase 2B.2B backend cutover)", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockApi();
    });

    it("renders the per-notification Summary panel from reportData.notification_summary, not from `licenses`", async () => {
        await renderAndSelectNorm();

        const panel = screen.getByText("Summary").closest("div.mt-4") as HTMLElement;
        expect(panel).not.toBeNull();

        // Opening balance comes straight from notification_summary.opening_balance
        // (555.55), not the license's own balance_cif (1000).
        const openingRow = within(panel).getByText("OPENING BALANCE").closest("tr") as HTMLElement;
        expect(within(openingRow).getByText("555.55")).toBeInTheDocument();

        // Regular item row: available/planned_qty/unit_price/planned_cif all
        // read from notification_summary.regular_items["FRUIT JUICE - E1"].
        const fruitRow = within(panel).getByText("FRUIT JUICE - E1").closest("tr") as HTMLElement;
        expect(within(fruitRow).getByText("111.11")).toBeInTheDocument();
        expect(within(fruitRow).getByText("10.00")).toBeInTheDocument();
        expect(within(fruitRow).getByText("22.22")).toBeInTheDocument();
        expect(within(fruitRow).getByText("222.22")).toBeInTheDocument();

        // Restricted-items group header: backend key is "10.0" (Python
        // str(float)) — display must still read "10%", matching today's UI,
        // not the raw "10.0%" backend key string.
        expect(within(panel).getByText("RESTRICTED ITEMS - 10%")).toBeInTheDocument();
        expect(within(panel).queryByText(/RESTRICTED ITEMS - 10\.0%/)).not.toBeInTheDocument();
        expect(within(panel).getByText("Balance 10%")).toBeInTheDocument();

        const restrictedRow = within(panel).getByText("PP - E1").closest("tr") as HTMLElement;
        expect(within(restrictedRow).getByText("50.00")).toBeInTheDocument();
        expect(within(restrictedRow).getByText("5.00")).toBeInTheDocument();
        expect(within(restrictedRow).getByText("12.00")).toBeInTheDocument();
        expect(within(restrictedRow).getByText("60.00")).toBeInTheDocument();
        expect(within(panel).getByText("999.99")).toBeInTheDocument();

        // Grand-total row: total_available/total_planned_qty/blended_unit_price/
        // total_planned_cif, all read directly (blended_unit_price is not
        // recomputed client-side as planned/qty).
        const totalRow = within(panel).getByText("TOTAL REMAINING CIF ($)").closest("tr") as HTMLElement;
        expect(within(totalRow).getByText("444.44")).toBeInTheDocument();
        expect(within(totalRow).getByText("22.22")).toBeInTheDocument();
        expect(within(totalRow).getByText("15.00")).toBeInTheDocument();
        expect(within(totalRow).getByText("333.33")).toBeInTheDocument();
    });

    it("renders the Norms Total Summary card from reportData.norm_summary, not a client-side flatten+reduce of `licenses`", async () => {
        await renderAndSelectNorm();

        const heading = screen.getByText(/Norms Total Summary/);
        const card = heading.closest('[data-slot="card"]') as HTMLElement;
        expect(card).not.toBeNull();

        // Opening balance comes from norm_summary.opening_balance (777.77),
        // not a `licenses.reduce((s, l) => s + l.balance_cif, 0)` (1000).
        const openingRow = within(card).getByText("OPENING BALANCE").closest("tr") as HTMLElement;
        expect(within(openingRow).getByText("777.77")).toBeInTheDocument();

        const fruitRow = within(card).getByText("FRUIT JUICE - E1").closest("tr") as HTMLElement;
        expect(within(fruitRow).getByText("121.21")).toBeInTheDocument();
        expect(within(fruitRow).getByText("11.00")).toBeInTheDocument();
        expect(within(fruitRow).getByText("21.12")).toBeInTheDocument();
        expect(within(fruitRow).getByText("232.32")).toBeInTheDocument();

        const totalRow = within(card).getByText("TOTAL REMAINING CIF ($)").closest("tr") as HTMLElement;
        expect(within(totalRow).getByText("666.66")).toBeInTheDocument();
        expect(within(totalRow).getByText("33.33")).toBeInTheDocument();
        expect(within(totalRow).getByText("16.67")).toBeInTheDocument();
        expect(within(totalRow).getByText("888.88")).toBeInTheDocument();
    });

    // No separate "calculateNotificationSummary is gone" test: the two
    // render tests above only pass if both panels render entirely from the
    // mocked notification_summary/norm_summary fixtures (which deliberately
    // diverge from what `licenses` would produce) — a local aggregation
    // engine reading `licenses` instead would fail these assertions.
});
