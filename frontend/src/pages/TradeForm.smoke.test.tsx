import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TradeForm from "./TradeForm";
import api from "../api/axios";

vi.mock("../api/axios", () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        loading: vi.fn(() => "toast-id"),
        success: vi.fn(),
        warning: vi.fn(),
    },
}));

vi.mock("../components/TransferLetterModal", () => ({
    default: () => null,
}));

vi.mock("../components/HybridSelect", () => ({
    default: ({ fieldMeta, onChange, placeholder }: any) => {
        const endpoint = fieldMeta?.endpoint || "";
        const selectValue = () => {
            if (endpoint.includes("license-items")) {
                onChange({
                    id: 501,
                    label: "LIC-001 / SR 1",
                    quantity: 100,
                });
                return;
            }

            if (endpoint.includes("companies")) {
                onChange(101);
                return;
            }

            onChange(301);
        };

        return (
            <button type="button" onClick={selectValue}>
                {placeholder || "Select..."}
            </button>
        );
    },
}));

function renderAt(path: string) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });

    return render(
        <QueryClientProvider client={queryClient}>
            <MemoryRouter initialEntries={[path]}>
                <Routes>
                    <Route path="/trades/create" element={<TradeForm />} />
                    <Route path="/trades/:id/edit" element={<TradeForm />} />
                    <Route path="/trades" element={<div>Trades list</div>} />
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>,
    );
}

function fieldControl(label: string) {
    const labelNode = screen.getByText(label);
    let wrapper: Element | null = labelNode.closest("div");
    let control: Element | null | undefined = null;

    for (let depth = 0; depth < 4 && wrapper && !control; depth += 1) {
        control = wrapper.querySelector("input, textarea");
        wrapper = wrapper.parentElement;
    }

    if (!control) {
        throw new Error(`No form control found for ${label}`);
    }

    return control as HTMLInputElement | HTMLTextAreaElement;
}

function mockGet(url: string) {
    if (url === "trades/42/") {
        return Promise.resolve({
            data: {
                id: 42,
                direction: "PURCHASE",
                license_type: "DFIA",
                from_company: 101,
                to_company: 202,
                boe: null,
                invoice_number: "TRD-42",
                invoice_date: "01-07-2026",
                remarks: "Existing trade",
                purchase_invoice_copy: null,
                from_pan: "ABCDE1234F",
                from_gst: "24ABCDE1234F1Z5",
                from_addr_line_1: "From address",
                from_addr_line_2: "",
                to_pan: "",
                to_gst: "",
                to_addr_line_1: "",
                to_addr_line_2: "",
                lines: [
                    {
                        id: 9,
                        sr_number: 501,
                        description: "Trade line",
                        hsn_code: "49070000",
                        mode: "CIF_INR",
                        qty_kg: 100,
                        rate_inr_per_kg: 0,
                        cif_fc: 100,
                        exc_rate: 83,
                        cif_inr: 8300,
                        fob_inr: 0,
                        pct: 7.9,
                        amount_inr: 656,
                    },
                ],
                payments: [],
                incentive_lines: [],
            },
        });
    }

    if (url === "masters/companies/101/") {
        return Promise.resolve({
            data: {
                pan: "ABCDE1234F",
                gst_number: "24ABCDE1234F1Z5",
                address_line_1: "From address",
                address_line_2: "",
            },
        });
    }

    return Promise.resolve({ data: {} });
}

describe("TradeForm smoke", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        (api.get as ReturnType<typeof vi.fn>).mockImplementation(mockGet);
        (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { id: 77 } });
        (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { id: 42 } });
        sessionStorage.clear();
    });

    it("creates a purchase trade with a DFIA line", async () => {
        const user = userEvent.setup();
        renderAt("/trades/create");

        expect(await screen.findByText("New Trade")).toBeInTheDocument();
        expect(screen.getByText("Create a new trade transaction")).toBeInTheDocument();

        await user.click(screen.getAllByRole("button", { name: "Search and select company..." })[0]);
        await user.type(fieldControl("Invoice Number (optional)"), "TRD-NEW");
        await user.click(screen.getByRole("button", { name: /add row/i }));
        await user.click(await screen.findByRole("button", { name: "Select License SR..." }));
        await user.type(screen.getByPlaceholderText("0.00"), "1200");
        await user.click(screen.getByRole("button", { name: /save trade/i }));

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith(
                "trades/",
                expect.objectContaining({
                    direction: "PURCHASE",
                    license_type: "DFIA",
                    from_company: 101,
                    invoice_number: "TRD-NEW",
                    lines: [
                        expect.objectContaining({
                            sr_number: 501,
                            hsn_code: "49070000",
                            amount_inr: "1200",
                        }),
                    ],
                    auto_create_paired: false,
                }),
                { headers: {} },
            );
        });
        expect(await screen.findByText("Trades list")).toBeInTheDocument();
    });

    it("loads and updates an existing purchase trade", async () => {
        const user = userEvent.setup();
        renderAt("/trades/42/edit");

        expect(await screen.findByText("Edit Trade")).toBeInTheDocument();
        expect(screen.getByText("Update trade details")).toBeInTheDocument();
        expect(await screen.findByDisplayValue("TRD-42")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: /save trade/i }));

        await waitFor(() => {
            expect(api.patch).toHaveBeenCalledWith(
                "trades/42/",
                expect.objectContaining({
                    direction: "PURCHASE",
                    license_type: "DFIA",
                    from_company: 101,
                    invoice_number: "TRD-42",
                    lines: [
                        expect.objectContaining({
                            id: 9,
                            sr_number: 501,
                            hsn_code: "49070000",
                            amount_inr: 656,
                        }),
                    ],
                }),
                { headers: {} },
            );
        });
        expect(await screen.findByText("Trades list")).toBeInTheDocument();
    });
});
