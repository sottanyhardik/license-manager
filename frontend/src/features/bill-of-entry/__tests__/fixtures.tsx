import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { AuthContext } from "@/context/AuthContext";
import MasterList from "@/pages/masters/MasterList";

/** List-level fields as returned by `bill-of-entries/` (BillOfEntrySerializer). */
export const BOE_FIXTURE = [
    {
        id: 201, bill_of_entry_number: "7012345", bill_of_entry_date: "05-01-2025", port_name: "INNSA1", company_name: "Alpha Imports",
        product_name: "Crude Palm Oil", invoice_no: "INV-201", invoice_date: "06-01-2025", licenses: "0310123456",
        total_inr: "1234567.89", total_fc: "15000.5", total_quantity: "12.3456", unit_price: "1215.03",
        exchange_rate: "82.30", appraisement: "Yes", ooc_date: "07-01-2025", cha: "Beta CHA", comments: null,
        allotment: [301], boe_pdf_copy: "/media/boe/7012345.pdf",
        item_details: [
            { id: 1, license_id: 11, license_number: "0310123456", item_description: "Palm oil", hs_code: "15119000", qty: "12.3456", cif_fc: "15000.5", cif_inr: "1234567.89", is_dispute: false, item_serial_number: 3, condition_type: "E", purchase_status: "GE" },
        ],
    },
    {
        id: 202, bill_of_entry_number: "7012346", bill_of_entry_date: "15-08-2025", port_name: "INMAA1", company_name: null,
        product_name: "", invoice_no: "", licenses: "0310654321, 0310777777",
        total_inr: "0", total_fc: null, total_quantity: "5", unit_price: null,
        allotment: [], boe_pdf_copy: null,
        item_details: [
            { id: 2, license_id: 12, license_number: "0310654321", item_description: "Cashew", hs_code: "08013100", qty: "2", cif_fc: "100", cif_inr: "8200", is_dispute: true },
            { id: 3, license_id: null, license_number: "0310777777", item_description: "Cashew", hs_code: null, qty: "3", cif_fc: null, cif_inr: null, is_dispute: false },
        ],
    },
    {
        id: 203, bill_of_entry_number: "", bill_of_entry_date: null, port_name: null, company_name: "Gamma",
        product_name: "Almonds", invoice_no: null, licenses: null,
        total_inr: null, total_fc: "0.333", total_quantity: null, unit_price: "77",
        allotment: [302, 303], item_details: [],
    },
    {
        id: 204, bill_of_entry_number: "7012348", bill_of_entry_date: "29-02-2024", port_name: "INBOM4", company_name: "Delta",
        product_name: null, invoice_no: "INV-204", licenses: "0310000004",
        total_inr: "98765", total_fc: "1200", total_quantity: "1.5", unit_price: "800",
        allotment: [304],
        item_details: [
            { id: 4, license_id: 14, license_number: "0310000004", item_description: "Pepper", hs_code: "09041100", qty: "1.5", cif_fc: "1200", cif_inr: "98765", is_dispute: true },
        ],
    },
];

export const LIST_RESPONSE = {
    results: BOE_FIXTURE, count: BOE_FIXTURE.length, list_display: [], form_fields: [], search_fields: [], filter_fields: [],
    filter_config: {}, ordering_fields: [], nested_field_defs: {}, nested_list_display: {}, field_meta: {}, default_filters: {},
    inline_editable: [], current_page: 1, total_pages: 1, page_size: 25, has_next: false, has_previous: false,
};

export type Role = "BOE_MANAGER" | "BOE_VIEWER" | "ACCOUNT_ACCESS" | "TL_GENERATE";

export function authFor(role: Role) {
    const roles = [role];
    return {
        user: { id: 1, username: "t", is_superuser: false, roles },
        loading: false,
        loginSuccess: vi.fn(),
        logout: vi.fn(),
        hasRole: (r: string) => roles.includes(r as Role),
        hasAnyRole: (rs: string[]) => rs.some((r) => roles.includes(r as Role)),
        isSuperAdmin: () => false,
        canManageUsers: () => false,
    };
}

/** Renders the real MasterList at /bill-of-entries (the BOE table register). */
export function renderBoeList(role: Role) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <AuthContext.Provider value={authFor(role) as never}>
                <MemoryRouter initialEntries={["/bill-of-entries"]}>
                    <Routes>
                        <Route path="/bill-of-entries" element={<MasterList />} />
                        <Route path="/bill-of-entries/201/edit" element={<div data-testid="edit-page">edit 201</div>} />
                    </Routes>
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

/** useId output is position-derived and not part of the presentation contract. */
export const normaliseIds = (html: string) => html.replace(/«[^»]*»|:r[0-9a-z]+:|_r_[0-9a-z]+_/g, "«id»");

/** Register data rows (the ones carrying the expand toggle), in render order. */
export function boeCards(): HTMLElement[] {
    return Array.from(document.querySelectorAll<HTMLElement>("tbody tr")).filter((tr) => tr.querySelector("button[aria-expanded]"));
}
