import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { AuthContext } from "@/context/AuthContext";
import LicensesTable, { type LicensesTableProps } from "@/pages/masters/tables/LicensesTable";

/** ~5 licences: expired, negative balance, over-utilised, planned, no docs, missing dates. */
export const LICENSE_FIXTURE: LicensesTableProps["data"] = [
    {
        id: 101, license_number: "0310123456", license_date: "05-01-2020", license_expiry_date: "04-01-2021",
        ledger_date: "10-02-2020", port_name: "INNSA1", exporter_name: "Alpha Exports", exporter_iec: "0301000001",
        get_norm_class: "E1", get_balance_cif: "1234.5", is_over_utilised: false, individual_item_cif_override: null,
        latest_transfer: "Transferred to Beta", purchase_status_label: "DFIA", purchase_status_code: "GE",
        is_manually_planned: false, has_tl: true, has_copy: true, has_condition_sheet: false,
    },
    {
        id: 102, license_number: "0310654321", license_date: "15-08-2024", license_expiry_date: "14-08-2099",
        ledger_date: null, port_name: "INMAA1", exporter_name: "Beta Foods", exporter_iec: "0301000002",
        get_norm_class: "E5", get_balance_cif: -250.75, is_over_utilised: true, individual_item_cif_override: true,
        latest_transfer: null, purchase_status_label: "Advance", purchase_status_code: "MI",
        is_manually_planned: false, has_tl: false, has_copy: false, has_condition_sheet: false,
    },
    {
        id: 103, license_number: "0310777777", license_date: "01-12-2025", license_expiry_date: "30-11-2099",
        ledger_date: "02-12-2025", port_name: null, exporter_name: null, exporter_iec: null,
        get_norm_class: null, get_balance_cif: "987654.321", is_over_utilised: null, individual_item_cif_override: false,
        latest_transfer: "Pending", purchase_status_label: null, purchase_status_code: null,
        is_manually_planned: true, has_tl: false, has_copy: true, has_condition_sheet: true,
    },
    {
        id: 104, license_number: "0310000004", license_date: null, license_expiry_date: null,
        ledger_date: null, port_name: "INBOM4", exporter_name: "Gamma", exporter_iec: "0301000004",
        get_norm_class: "A3", get_balance_cif: 0, is_over_utilised: false,
        latest_transfer: null, purchase_status_label: "DFIA", purchase_status_code: "GE",
        is_manually_planned: false, has_tl: true, has_copy: false, has_condition_sheet: false,
    },
    {
        id: 105, license_number: "", license_date: "29-02-2024", license_expiry_date: "28-02-2099",
        ledger_date: "01-03-2024", port_name: "INNSA1", exporter_name: "Delta", exporter_iec: "0301000005",
        get_norm_class: "E1", get_balance_cif: null, is_over_utilised: false,
        latest_transfer: null, purchase_status_label: "DFIA", purchase_status_code: "GE",
        is_manually_planned: false, has_tl: false, has_copy: false, has_condition_sheet: false,
    },
];

export type Role = "LICENSE_MANAGER" | "LICENSE_VIEWER";

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

export function renderLicensesTable(role: Role, overrides: Partial<LicensesTableProps> = {}) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } }); // staleTime mirrors api/queryClient.ts
    const props: LicensesTableProps = {
        loading: false,
        data: LICENSE_FIXTURE,
        canWrite: role === "LICENSE_MANAGER",
        entityName: "licenses",
        filterParams: {},
        currentPage: 1,
        pageSize: 25,
        navigate: vi.fn(),
        onDelete: vi.fn(),
        fetchingOwnershipIds: new Set<number>(),
        onFetchOwnership: vi.fn(),
        invalidateList: vi.fn(),
        ...overrides,
    };
    const utils = render(
        <QueryClientProvider client={queryClient}>
            <AuthContext.Provider value={authFor(role) as never}>
                <MemoryRouter>
                    <LicensesTable {...props} />
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
    return { ...utils, props, queryClient };
}
