import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("@/api/axios", () => ({ default: { get: (...a: unknown[]) => get(...a) } }));

import { invalidateLicence } from "@/lib/queryKeys";
import {
    licenseTransactionKeys,
    useLicenseOverviewTransactionRecords,
    useLicenseOverviewTransactions,
} from "./useLicenseOverviewTransactions";

function setup() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    return { client, wrapper };
}

const groups = { license_id: 7, license_number: "L7", count: 0, page_size: 25, total_pages: 1, current_page: 1, results: [], totals: {} };

describe("useLicenseOverviewTransactions", () => {
    beforeEach(() => get.mockReset());

    it("fetches groups with non-empty params only", async () => {
        get.mockResolvedValue({ data: groups });
        const { wrapper } = setup();
        const { result } = renderHook(
            () => useLicenseOverviewTransactions(7, { page: 2, search: "", record_type: "BOE" }),
            { wrapper },
        );
        await waitFor(() => expect(result.current.status).toBe("success"));
        expect(get).toHaveBeenCalledWith("licenses/7/overview-transactions/", { params: { page: 2, record_type: "BOE" } });
        expect(result.current.data?.license_number).toBe("L7");
    });

    it("does not fetch without a licence id or when inactive", () => {
        const { wrapper } = setup();
        renderHook(() => useLicenseOverviewTransactions(undefined), { wrapper });
        renderHook(() => useLicenseOverviewTransactions(7, {}, false), { wrapper });
        expect(get).not.toHaveBeenCalled();
    });

    it("sends supplier_id=null for the no-supplier group and waits for a selection", async () => {
        get.mockResolvedValue({ data: { ...groups, product: {}, supplier_id: null } });
        const { wrapper } = setup();
        renderHook(() => useLicenseOverviewTransactionRecords(7, null), { wrapper });
        expect(get).not.toHaveBeenCalled();
        const { result } = renderHook(
            () => useLicenseOverviewTransactionRecords(7, { supplier_id: null, product_key: 3, page: 1 }),
            { wrapper },
        );
        await waitFor(() => expect(result.current.status).toBe("success"));
        expect(get).toHaveBeenCalledWith("licenses/7/overview-transactions/", {
            params: { supplier_id: "null", product_key: 3, page: 1 },
        });
    });

    it("keys sit under the licence detail prefix so invalidateLicence covers them", async () => {
        get.mockResolvedValue({ data: groups });
        const { client, wrapper } = setup();
        const { result } = renderHook(() => useLicenseOverviewTransactions(7), { wrapper });
        await waitFor(() => expect(result.current.status).toBe("success"));
        expect(licenseTransactionKeys.groups(7).slice(0, 3)).toEqual(["licenses", "detail", "7"]);
        await invalidateLicence(client, 7);
        await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    });
});
