import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdvancedFilter from "@/components/AdvancedFilter";
import { boeInvoiceBadge } from "../invoiceStatus";

const FILTER_CONFIG = {
    is_invoice: { type: "exact", label: "Has Invoice No.", choices: [["all", "All"], ["yes", "Yes"], ["no", "No"]] },
    invoice_status: {
        type: "exact", label: "Invoice Status",
        choices: [["invoiced", "Invoiced"], ["invoice_no_recorded", "Invoice no. recorded"], ["not_invoiced", "Not invoiced"], ["hidden", "Hidden"]],
    },
};

describe("BOE invoice status", () => {
    afterEach(() => cleanup());

    it("renders the backend-provided Invoice Status filter and emits its value", async () => {
        const onFilterChange = vi.fn();
        render(<AdvancedFilter filterConfig={FILTER_CONFIG} onFilterChange={onFilterChange} initialFilters={{ invoice_status: "invoiced" }} />);
        expect(screen.getByText("Invoice Status")).toBeInTheDocument();
        expect(screen.getByText("Has Invoice No.")).toBeInTheDocument();
        // Selected value is shown with its label; active count reflects it.
        expect(screen.getByText("Invoiced")).toBeInTheDocument();
        fireEvent.keyDown(screen.getByText("Invoiced"), { key: "ArrowDown" });
        fireEvent.click(await screen.findByText("Not invoiced"));
        await waitFor(() => expect(onFilterChange).toHaveBeenLastCalledWith(expect.objectContaining({ invoice_status: "not_invoiced" })));
    });

    it("badge helper uses the API label, falls back to a static map, never reads invoice_no", () => {
        expect(boeInvoiceBadge({ invoice_status: "invoiced", invoice_status_label: "Custom" })).toMatchObject({ tone: "success", label: "Custom" });
        expect(boeInvoiceBadge({ invoice_status: "invoice_no_recorded" })).toMatchObject({ tone: "info", label: "Invoice no. recorded" });
        expect(boeInvoiceBadge({ invoice_status: "hidden" })).toMatchObject({ muted: true, label: "Hidden" });
        expect(boeInvoiceBadge({ invoice_no: "INV-1" } as never)).toBeNull();
    });
});
