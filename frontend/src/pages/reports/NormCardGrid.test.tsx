import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import NormCardGrid, { normalizeNormCards } from "./NormCardGrid";

describe("NormCardGrid", () => {
    it("normalizes malformed, blank, and duplicate norm entries", () => {
        expect(
            normalizeNormCards([
                null,
                "",
                " E1 ",
                { norm_class: "E1", description: "duplicate" },
                { norm_class: " E132 ", description: " Conversion " },
                { norm_class: "CUSTOM", description: null },
                { description: "missing class" },
            ]),
        ).toEqual([
            { normClass: "E1", description: "", isConversionNorm: true },
            { normClass: "E132", description: "Conversion", isConversionNorm: true },
            { normClass: "CUSTOM", description: "", isConversionNorm: false },
        ]);

        expect(normalizeNormCards(undefined)).toEqual([]);
    });

    it("renders deduplicated norm buttons and switches active norm", () => {
        const setActiveNormTab = vi.fn();
        const setReportData = vi.fn();

        render(
            <NormCardGrid
                availableNorms={[
                    { norm_class: "E1", description: "Conversion norm" },
                    { norm_class: "E1", description: "Duplicate" },
                    "CUSTOM",
                    null,
                ]}
                activeNormTab="E1"
                setActiveNormTab={setActiveNormTab}
                setReportData={setReportData}
                loading={false}
            />,
        );

        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /e1/i })).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByRole("button", { name: /custom/i })).toHaveAttribute("aria-pressed", "false");

        fireEvent.click(screen.getByRole("button", { name: /custom/i }));

        expect(setReportData).toHaveBeenCalledWith(null);
        expect(setActiveNormTab).toHaveBeenCalledWith("CUSTOM");
    });

    it("does not clear report data when reselecting the active norm", () => {
        const setActiveNormTab = vi.fn();
        const setReportData = vi.fn();

        render(
            <NormCardGrid
                availableNorms={["E5"]}
                activeNormTab="E5"
                setActiveNormTab={setActiveNormTab}
                setReportData={setReportData}
                loading
            />,
        );

        expect(screen.getByLabelText("Loading selected norm")).toBeInTheDocument();

        fireEvent.click(screen.getByRole("button", { name: /e5/i }));

        expect(setReportData).not.toHaveBeenCalled();
        expect(setActiveNormTab).toHaveBeenCalledWith("E5");
    });
});
