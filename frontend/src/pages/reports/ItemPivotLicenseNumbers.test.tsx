import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api/axios";
import { openAuthedFile } from "../../utils/documentDownload";
import ItemPivotReport, { LicenseNumberFilterNotice } from "./ItemPivotReport";
import { parseLicenseNumbers } from "./itemPivotFilterHelpers";
import { buildItemPivotReportPath } from "./itemPivotReportUtils";

vi.mock("react-router-dom", async (importOriginal) => ({
    ...(await importOriginal<typeof import("react-router-dom")>()),
    useNavigate: () => vi.fn(),
    useSearchParams: () => [new URLSearchParams(""), vi.fn()],
}));
vi.mock("../../api/axios", () => ({ default: { get: vi.fn() } }));
vi.mock("../../utils/documentDownload", () => ({ openAuthedFile: vi.fn(() => Promise.resolve()) }));
vi.mock("sonner", () => ({ toast: { dismiss: vi.fn(), error: vi.fn(), info: vi.fn(), success: vi.fn() } }));

describe("parseLicenseNumbers", () => {
    it.each([
        ["", []],
        [" , ,, ", []],
        ["0510456789", ["0510456789"]],
        ["0510456789, 0510456790,0510456791", ["0510456789", "0510456790", "0510456791"]],
        ["  0510456789  ,   0510456790 ", ["0510456789", "0510456790"]],
        ["0510456789,0510456790,0510456789", ["0510456789", "0510456790"]],
        ["0510456789\n0510456790\r\n0510456791;0510456792\t0510456793", ["0510456789", "0510456790", "0510456791", "0510456792", "0510456793"]],
    ])("parses %j", (raw, expected) => {
        expect(parseLicenseNumbers(raw)).toEqual(expected);
    });

    it("handles a large pasted list", () => {
        const raw = Array.from({ length: 3000 }, (_, i) => `05${String(i).padStart(8, "0")}`).join(", ");
        expect(parseLicenseNumbers(`${raw}, ${raw}`)).toHaveLength(3000);
    });
});

describe("buildItemPivotReportPath license_numbers", () => {
    it("omits the param when empty and sends one comma-joined param otherwise", () => {
        expect(buildItemPivotReportPath({ format: "json", normClass: "E1" })).not.toContain("license_numbers");
        const url = new URL(buildItemPivotReportPath({ format: "excel", normClass: "E1", licenseNumbers: ["0510456789", " 0510456790 ", ""] }), "http://x/");
        expect(url.searchParams.get("license_numbers")).toBe("0510456789,0510456790");
        expect(url.searchParams.get("sion_norm")).toBe("E1");
        expect(url.searchParams.get("min_balance")).toBe("200");
    });
});

describe("LicenseNumberFilterNotice", () => {
    it("renders nothing without a summary", () => {
        const { container } = render(<LicenseNumberFilterNotice summary={null} />);
        expect(container).toBeEmptyDOMElement();
    });

    it("lists unmatched numbers separately from licences outside the other filters", () => {
        render(<LicenseNumberFilterNotice summary={{
            requested_count: 4, matched: ["A1"], not_found: ["NOPE"],
            excluded_by_filters: [{ license_number: "B2", sion_norms: ["E5"] }, { license_number: "C3", sion_norms: [] }],
        }} />);
        expect(screen.getByText(/1 of 4 matched/)).toBeInTheDocument();
        expect(screen.getByText(/B2 \(E5\), C3/)).toBeInTheDocument();
        expect(screen.getByText(/Not found \(1\):/).parentElement).toHaveTextContent("NOPE");
    });
});

describe("ItemPivotReport License Numbers filter", () => {
    const get = vi.mocked(api.get);
    const reportCalls = () => get.mock.calls.map(([u]) => String(u)).filter((u) => u.startsWith("reports/item-pivot/"));

    beforeEach(() => {
        vi.clearAllMocks();
        get.mockImplementation((url: string) => {
            if (url.startsWith("item-pivot/available-norms/")) return Promise.resolve({ data: [{ norm_class: "E1", description: "Confectionery" }] });
            if (url.startsWith("reports/item-pivot/")) {
                const numbers = new URL(url, "http://x/").searchParams.get("license_numbers");
                return Promise.resolve({ data: {
                    items: [], licenses_by_norm_notification: {}, norm_notes_conditions: {},
                    ...(numbers ? { license_number_filter: { requested_count: numbers.split(",").length, matched: [], not_found: numbers.split(","), excluded_by_filters: [] } } : {}),
                } });
            }
            return Promise.resolve({ data: { results: [] } });
        });
    });

    it("counts entered numbers, applies them in one request, exports with them and clears them", async () => {
        render(<ItemPivotReport />);
        fireEvent.click((await screen.findAllByRole("button", { name: /E1/ }))[0]);
        await waitFor(() => expect(reportCalls()).toHaveLength(1));
        expect(reportCalls()[0]).not.toContain("license_numbers");
        fireEvent.click(screen.getByRole("button", { name: /Show Filters/ }));

        const box = screen.getByLabelText("License Numbers");
        expect(box).toHaveAttribute("placeholder", "Enter license numbers separated by commas");
        fireEvent.change(box, { target: { value: " 0510456789, 0510456790,0510456789, ,0510456791 " } });
        expect(screen.getByText(/3 licenses entered/)).toBeInTheDocument();
        // Typing does not refetch; only Apply does.
        await new Promise((r) => setTimeout(r, 50));
        expect(reportCalls()).toHaveLength(1);

        fireEvent.click(screen.getByRole("button", { name: "Apply" }));
        await waitFor(() => expect(reportCalls()).toHaveLength(2));
        const applied = new URL(reportCalls()[1], "http://x/");
        expect(applied.searchParams.get("license_numbers")).toBe("0510456789,0510456790,0510456791");
        expect(applied.searchParams.get("sion_norm")).toBe("E1");
        expect(await screen.findByTestId("license-number-filter-notice")).toHaveTextContent("0 of 3 matched");

        fireEvent.click(screen.getByRole("button", { name: /excel/i }));
        await waitFor(() => expect(vi.mocked(openAuthedFile)).toHaveBeenCalledTimes(1));
        const exported = new URL(String(vi.mocked(openAuthedFile).mock.calls[0][0]), "http://x/");
        expect(exported.searchParams.get("format")).toBe("excel");
        expect(exported.searchParams.get("license_numbers")).toBe("0510456789,0510456790,0510456791");

        fireEvent.click(screen.getByRole("button", { name: "Clear license numbers" }));
        await waitFor(() => expect(reportCalls()).toHaveLength(3));
        expect(reportCalls()[2]).not.toContain("license_numbers");
        expect(screen.getByLabelText("License Numbers")).toHaveValue("");
        expect(screen.queryByTestId("license-number-filter-notice")).not.toBeInTheDocument();
    });
});
