import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { openDocument } from "@/utils/documentDownload";
import LicenseOverviewPage from "./LicenseOverviewPage";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("@/utils/documentDownload", () => ({
    openDocument: vi.fn(),
    openAuthedFile: vi.fn(),
}));
vi.mock("@/utils/pdfPreview", () => ({ openPdfPreview: vi.fn() }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@/components/PageHeader", () => ({
    default: ({ title, actions }: { title: string; actions: React.ReactNode }) => <header><h1>{title}</h1>{actions}</header>,
}));
vi.mock("@/components/PermissionGate", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/components/ui/tabs", () => ({
    Tabs: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    TabsList: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    TabsTrigger: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
    TabsContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("./OverviewTab", () => ({ default: () => null }));
vi.mock("./BoesTab", () => ({ default: () => null }));
vi.mock("./AllotmentsTab", () => ({ default: () => null }));
vi.mock("./ItemsTab", () => ({ default: () => null }));
vi.mock("./InvoiceLedgerTab", () => ({ default: () => null }));
vi.mock("./ReplanStatus", () => ({ default: () => null }));
vi.mock("@/components/planning/PlanningEditor", () => ({ default: () => null }));

const mockedGet = vi.mocked(api.get);
const mockedOpenDocument = vi.mocked(openDocument);

type Document = { id: number; type: string; file: string };

const summary = {
    license_number: "5611004566", authorisation_number: null, file_number: null,
    license_date: null, license_expiry_date: null, importer: null, status: "Active" as const,
    purchase_status_id: null, purchase_status_code: null, purchase_status_label: null,
    port_code: null, port_name: null,
    summary: { total_boes: 0, total_allotments: 0, total_planned_cif: 0, total_cif: 0, total_debited_cif: 0, total_allotted_cif: 0, total_balance_cif: 0 },
};

function renderPage(documents: Document[]) {
    mockedGet.mockImplementation((url: string) => {
        if (url === "licenses/2260/overview-summary/") return Promise.resolve({ data: summary });
        if (url === "licenses/2260/") return Promise.resolve({ data: { license_documents: documents } });
        return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={queryClient}>
            <AuthContext.Provider value={{ hasRole: () => true } as never}>
                <MemoryRouter initialEntries={["/licenses/2260/overview"]}>
                    <Routes><Route path="/licenses/:id/overview" element={<LicenseOverviewPage />} /></Routes>
                </MemoryRouter>
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

describe("LicenseOverviewPage stored document actions", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedOpenDocument.mockResolvedValue();
    });

    it("renders structured Licence Copy and TL actions, with distinguishable names for duplicates", async () => {
        renderPage([
            { id: 1, type: "LICENSE COPY", file: "/media/licenses/2260/copy-a.pdf" },
            { id: 2, type: "LICENSE COPY", file: "/media/licenses/2260/copy-b.pdf" },
            { id: 3, type: "TRANSFER LETTER", file: "/media/licenses/2260/tl-a.pdf" },
            { id: 4, type: "OTHER", file: "/media/licenses/2260/ignore.pdf" },
        ]);

        const copyOne = await screen.findByRole("button", { name: "View Licence Copy 1" });
        expect(screen.getByRole("button", { name: "View Licence Copy 2" })).toBeVisible();
        expect(screen.getByRole("button", { name: "View TL" })).toBeVisible();
        expect(screen.queryByRole("button", { name: /ignore/i })).not.toBeInTheDocument();

        await userEvent.click(copyOne);
        expect(mockedOpenDocument).toHaveBeenCalledWith("/media/licenses/2260/copy-a.pdf");
    });

    it("supports keyboard activation and never creates actions for missing structured document types", async () => {
        renderPage([{ id: 7, type: "TRANSFER LETTER", file: "/media/licenses/2260/tl.pdf" }]);
        const tl = await screen.findByRole("button", { name: "View TL" });
        await userEvent.tab();
        // Direct focus remains robust even when surrounding mocked tab controls change.
        tl.focus();
        await userEvent.keyboard("{Enter}");
        expect(mockedOpenDocument).toHaveBeenCalledWith("/media/licenses/2260/tl.pdf");
        expect(screen.queryByRole("button", { name: /licence copy/i })).not.toBeInTheDocument();
    });

    it("does not expose an active document action while the licence detail is loading", async () => {
        let resolveDetails: ((value: { data: { license_documents: Document[] } }) => void) | undefined;
        mockedGet.mockImplementation((url: string) => {
            if (url === "licenses/2260/overview-summary/") return Promise.resolve({ data: summary });
            if (url === "licenses/2260/") return new Promise((resolve) => { resolveDetails = resolve; });
            return Promise.reject(new Error(`Unexpected request: ${url}`));
        });
        const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
        render(<QueryClientProvider client={queryClient}><AuthContext.Provider value={{ hasRole: () => true } as never}><MemoryRouter initialEntries={["/licenses/2260/overview"]}><Routes><Route path="/licenses/:id/overview" element={<LicenseOverviewPage />} /></Routes></MemoryRouter></AuthContext.Provider></QueryClientProvider>);

        expect(screen.queryByRole("button", { name: /view (licence copy|tl)/i })).not.toBeInTheDocument();
        resolveDetails?.({ data: { license_documents: [{ id: 8, type: "LICENSE COPY", file: "/media/copy.pdf" }] } });
        expect(await screen.findByRole("button", { name: "View Licence Copy" })).toBeVisible();
    });

    it("keeps the protected-media failure contained and issues one shared licence-detail request", async () => {
        mockedOpenDocument.mockRejectedValueOnce(new Error("Forbidden"));
        renderPage([{ id: 9, type: "LICENSE COPY", file: "https://untrusted.example/private.pdf" }]);
        await userEvent.click(await screen.findByRole("button", { name: "View Licence Copy" }));
        await waitFor(() => expect(mockedOpenDocument).toHaveBeenCalledWith("https://untrusted.example/private.pdf"));
        expect(mockedGet.mock.calls.filter(([url]) => url === "licenses/2260/")).toHaveLength(1);
    });
});
