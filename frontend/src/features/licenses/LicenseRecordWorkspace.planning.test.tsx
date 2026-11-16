import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LicenseRecordWorkspace from "./LicenseRecordWorkspace";

let triggerSaved: (() => void) | undefined;
vi.mock("@/components/planning/PlanningEditor", () => ({
    default: ({ onSaved }: { onSaved?: () => void }) => {
        triggerSaved = onSaved;
        return <div>planning-editor</div>;
    },
}));
vi.mock("@/api/axios", () => ({
    default: {
        get: vi.fn((url: string) => {
            if (url.endsWith("/balance-ledger/")) {
                return Promise.resolve({ data: { license: {}, financial_ledger: { rows: [], summary: { has_trading_activity: false } }, customs_ledger: { rows: [], summary: {} }, reconciliation: {}, warnings: [], timeline: [] } });
            }
            return Promise.resolve({ data: { rows: [], results: [], license_number: "L1", balance_cif: "5" } });
        }),
        post: vi.fn(),
    },
}));

function setup() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(qc, "invalidateQueries");
    const view = render(
        <QueryClientProvider client={qc}>
            <MemoryRouter>
                <LicenseRecordWorkspace licenseId={7} canWrite activeTab="plan" onTabChange={vi.fn()} renderHistory={() => null} />
            </MemoryRouter>
        </QueryClientProvider>,
    );
    return { spy, view };
}

describe("LicenseRecordWorkspace planning tab (D5)", () => {
    beforeEach(() => { vi.clearAllMocks(); triggerSaved = undefined; });
    afterEach(() => vi.useRealTimers());

    it("invalidates the licence detail prefix once after a burst of saves", async () => {
        const { spy } = setup();
        expect(await screen.findByText("planning-editor")).toBeInTheDocument();
        vi.useFakeTimers();
        act(() => { triggerSaved?.(); triggerSaved?.(); triggerSaved?.(); });
        expect(spy).not.toHaveBeenCalled();
        act(() => { vi.advanceTimersByTime(400); });
        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy).toHaveBeenCalledWith({ queryKey: ["licenses", "detail", "7"] });
    });

    it("flushes a pending invalidation on unmount", async () => {
        const { spy, view } = setup();
        await screen.findByText("planning-editor");
        act(() => { triggerSaved?.(); });
        view.unmount();
        expect(spy).toHaveBeenCalledTimes(1);
    });
});
