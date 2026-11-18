import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("@/utils/documentDownload", () => ({ openAuthedFile: vi.fn(() => Promise.resolve()) }));

import api from "@/api/axios";
import { openAuthedFile } from "@/utils/documentDownload";
import ItemPivotIntelligence, { type IntelReport } from "./ItemPivotIntelligence";

const get = vi.mocked(api.get);
const licence = (id: number, number: string, over: Partial<IntelReport["licences"][number]> = {}) => ({
    license_id: id, license_number: number, sion: "E5", company: `Co ${id}`, expiry_date: "2026-12-31", purchase_status: "GE",
    original_cif: "1000.00", boe_cif: "400.00", allotment_cif: "100.00", billed_cif: "0.00", other_adjustments_cif: "0.00",
    available_cif: "500.00", is_over_utilised: false, components_reconcile: true, planned_cif: "200.00", final_balance_cif: "300.00",
    utilisation_percent: "50.0", products: ["ITEM:1:E5"], ...over,
});
const cell = (lid: number, number: string, key: string, product: string, status: IntelReport["eligibility"][number]["status"], eligible: boolean) => ({
    license_id: lid, license_number: number, product_key: key, product, kind: "MAPPED", sion: "E5", status, reasons: [`${status} reason`],
    entitlement_qty: "100", debited_qty: "40", allotted_qty: "10", billed_qty: "0", balance_qty: "50", planned_qty: "20", planned_cif: "200.00",
    max_unit_price: "4.00", licence_available_cif: "500.00", licence_final_balance_cif: "300.00", planning_eligible: eligible,
    references: { boes: ["B-1"], allotments: ["ALT-9"] },
});
const report: IntelReport = {
    overview: {
        licence_count: 2, original_cif: "2000.00", boe_cif: "800.00", allotment_cif: "200.00", billed_cif: "0.00", available_cif: "1000.00",
        planned_cif: "400.00", final_balance_cif: "600.00", utilisation_percent: "50.0", eligible_product_count: 1, underutilised_licence_count: 1,
        warning_count: 1, attention_product_count: 1, unreconciled_licence_count: 0, status_counts: { UNDERUTILIZED: 1, CORRECT: 1, WARNING: 1 },
        consolidation: { mapped: 1, ambiguous: 0, unmapped: 1, merged_source_records: 2, mapping_review: 0 },
        bases: { licence: "Canonical engine", item: "Item-level raw records" },
    },
    licences: [licence(1, "LIC-A"), licence(2, "LIC-B", { products: ["ITEM:1:E5", "UNMAPPED:x"], final_balance_cif: "-25.00" })],
    products: [
        { key: "ITEM:1:E5", kind: "MAPPED", item_name_id: 1, product: "SUGAR", sion: "E5", mapping_basis: "Master item link", hsn_codes: ["17019990"], aliases: ["Sugar", "SUGAR refined"],
          hsn_chapters: ["17"], mapping_review: null, eligible_licences: 2, source_record_count: 2,
          source_records: [{ license_id: 1, license_number: "LIC-A", import_item_id: 11, serial_number: 1, description: "Sugar", hsn_code: "17019990" }, { license_id: 2, license_number: "LIC-B", import_item_id: 21, serial_number: 1, description: "SUGAR refined", hsn_code: "17019990" }],
          entitlement_qty: "200", allotted_qty: "20", debited_qty: "80", billed_qty: "0", balance_qty: "100", max_unit_price: "4.00", planned_qty: "40", planned_cif: "400.00", utilisation_percent: "50.0", status_counts: { UNDERUTILIZED: 1, CORRECT: 1 } },
        { key: "UNMAPPED:x", kind: "UNMAPPED", item_name_id: null, product: "Misc ingredient", sion: "E5", mapping_basis: "No master item link — kept separate", hsn_codes: [], aliases: ["Misc ingredient"],
          hsn_chapters: [], mapping_review: null, eligible_licences: 1, source_record_count: 1, source_records: [], entitlement_qty: "5", allotted_qty: "0", debited_qty: "0", billed_qty: "0", balance_qty: "5",
          max_unit_price: null, planned_qty: "0", planned_cif: "0.00", utilisation_percent: "0.0", status_counts: { WARNING: 1 } },
    ],
    eligibility: [
        cell(1, "LIC-A", "ITEM:1:E5", "SUGAR", "CORRECT", false),
        cell(2, "LIC-B", "ITEM:1:E5", "SUGAR", "UNDERUTILIZED", true),
        cell(2, "LIC-B", "UNMAPPED:x", "Misc ingredient", "WARNING", false),
    ],
};

function setup() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><ItemPivotIntelligence query="sion_norm=E5&min_balance=200" /></MemoryRouter></QueryClientProvider>);
    return userEvent.setup();
}

beforeEach(() => {
    vi.clearAllMocks();
    get.mockImplementation(async (url: string) => {
        if (url.startsWith("item-pivot/intelligence/")) return { data: report };
        if (url === "item-pivot/recommendations/") return { data: { read_only: true, errors: [], recommendations: [{ rank: 1, license_id: 2, license_number: "LIC-B", expiry_date: "2026-12-31", sion: "E5", product: "SUGAR", rule_priority: 1, unit_price: "4.00", recommended_qty: "50", recommended_cif: "200.00", existing_qty: "20", existing_cif: "80.00", additional_qty: "30", additional_cif: "120.00", licence_available_cif: "500.00", remaining_licence_cif_after: "300.00", cif_status: "FULLY_FUNDED", reason: "Auto Plan engine", alternatives: ["LIC-A"] }] } };
        throw new Error(`unexpected ${url}`);
    });
});

describe("Item pivot intelligence", () => {
    it("shows the overview with backend figures and the actual vs planned distinction", async () => {
        setup();
        expect(await screen.findByRole("region", { name: "Utilization waterfall" })).toBeInTheDocument();
        expect(get).toHaveBeenCalledWith("item-pivot/intelligence/?sion_norm=E5&min_balance=200", expect.anything());
        expect(screen.getByText("Planned CIF is a proposal and is never counted as an actual debit.")).toBeInTheDocument();
        const audit = screen.getByRole("region", { name: "Product consolidation audit" });
        expect(within(audit).getByText("Unmapped (kept separate)")).toBeInTheDocument();
    });

    it("selecting a product highlights matching licences; planning mode narrows to eligible ones", async () => {
        const user = setup();
        await screen.findByRole("region", { name: "Utilization waterfall" });
        await user.click(screen.getByRole("tab", { name: /Product Analysis/ }));
        await user.click(screen.getByRole("button", { name: "SUGAR" }));
        expect(screen.getByRole("tab", { name: /Licence Analysis/ })).toHaveAttribute("aria-selected", "true");
        expect(screen.getByText(/Highlighting licences for/)).toHaveTextContent("SUGAR");
        expect(screen.getByRole("article", { name: "Licence LIC-A" })).not.toHaveClass("opacity-45");
        await user.click(screen.getByRole("button", { name: "Planning" }));
        expect(screen.getByRole("article", { name: "Licence LIC-A" })).toHaveClass("opacity-45");
        expect(screen.getByRole("article", { name: "Licence LIC-B" })).toHaveTextContent("Eligible for more planning");
        await user.click(screen.getByLabelText("Only matching"));
        expect(screen.queryByRole("article", { name: "Licence LIC-A" })).toBeNull();
    });

    it("expands a licence inline with its products, statuses and source references", async () => {
        const user = setup();
        await screen.findByRole("region", { name: "Utilization waterfall" });
        await user.click(screen.getByRole("tab", { name: /Licence Analysis/ }));
        await user.click(screen.getByRole("button", { name: "Expand licence LIC-B" }));
        const region = screen.getByRole("region", { name: "Licence LIC-B products" });
        expect(within(region).getByText("Underutilized")).toBeInTheDocument();
        expect(within(region).getByText("WARNING reason")).toBeInTheDocument();
        expect(within(region).getAllByText(/BOE B-1/)).toHaveLength(2);
        await user.click(within(region).getByRole("button", { name: "Highlight this licence's products" }));
        expect(screen.getByRole("tab", { name: /Product Analysis/ })).toHaveAttribute("aria-selected", "true");
    });

    it("keeps unmapped products separate and shows merged source records", async () => {
        const user = setup();
        await screen.findByRole("region", { name: "Utilization waterfall" });
        await user.click(screen.getByRole("tab", { name: /Product Analysis/ }));
        expect(within(screen.getByRole("table", { name: "Products" })).getByText("Unmapped", { selector: "div" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Expand SUGAR" }));
        expect(within(screen.getByRole("table", { name: "Source records of SUGAR" })).getAllByRole("row")).toHaveLength(3);
    });

    it("simulates recommendations read-only and links to the existing planning workflow", async () => {
        const user = setup();
        await screen.findByRole("region", { name: "Utilization waterfall" });
        await user.click(screen.getByRole("tab", { name: "Planning & Optimization" }));
        await user.click(screen.getByLabelText("Select licence LIC-B"));
        await user.click(screen.getByRole("button", { name: /Simulate recommendations \(1\)/ }));
        const table = await screen.findByRole("table", { name: "Recommended plan" });
        expect(get).toHaveBeenCalledWith("item-pivot/recommendations/", expect.objectContaining({ params: { license_ids: "2" } }));
        expect(within(table).getByText("$120")).toBeInTheDocument();
        expect(within(table).getByRole("link", { name: "Review & save" })).toHaveAttribute("href", "/licenses/2/overview?tab=planning");
        expect(api.post).not.toHaveBeenCalled();
    });

    it("exports the same filtered data to Excel", async () => {
        const user = setup();
        await screen.findByRole("region", { name: "Utilization waterfall" });
        await user.click(screen.getByRole("button", { name: /Excel \(products/ }));
        await waitFor(() => expect(openAuthedFile).toHaveBeenCalledWith("item-pivot/intelligence/?sion_norm=E5&min_balance=200&format=excel", "item_pivot_intelligence.xlsx"));
    });
});
