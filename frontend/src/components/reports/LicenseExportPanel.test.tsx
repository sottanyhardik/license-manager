import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LicenseExportPanel, { normalizeExportDays } from "./LicenseExportPanel";
import { openAuthedFile } from "@/utils/documentDownload";

vi.mock("@/utils/documentDownload", () => ({
    openAuthedFile: vi.fn(),
}));

const mockedOpenAuthedFile = vi.mocked(openAuthedFile);

function renderPanel(defaultDays = 30) {
    return render(
        <LicenseExportPanel
            title="Expiring Licenses Report"
            description="Export licenses expiring soon"
            daysLabel="Days from today"
            defaultDays={defaultDays}
            helpText={(days) => `Licenses expiring within ${days} days`}
            endpoint={(days) => `license/reports/expiring-licenses/?format=excel&days=${days}`}
            filename={(days) => `expiring_licenses_${days}_days.xlsx`}
            features={["Separate sheets", "Grouped rows"]}
        />,
    );
}

describe("LicenseExportPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedOpenAuthedFile.mockResolvedValue(undefined);
    });

    it("normalizes export days to supported boundaries", () => {
        expect(normalizeExportDays("14")).toBe(14);
        expect(normalizeExportDays("0")).toBe(1);
        expect(normalizeExportDays("-5")).toBe(1);
        expect(normalizeExportDays("999")).toBe(365);
        expect(normalizeExportDays("abc", 45)).toBe(45);
        expect(normalizeExportDays("abc", 999)).toBe(365);
    });

    it("downloads using the normalized default day count", async () => {
        renderPanel();

        fireEvent.click(screen.getByRole("button", { name: /download excel report/i }));

        await waitFor(() => {
            expect(mockedOpenAuthedFile).toHaveBeenCalledWith(
                "license/reports/expiring-licenses/?format=excel&days=30",
                "expiring_licenses_30_days.xlsx",
            );
        });
    });

    it("clamps out-of-range day input before download", async () => {
        renderPanel();
        const input = screen.getByLabelText("Days from today");

        fireEvent.change(input, { target: { value: "999" } });
        fireEvent.click(screen.getByRole("button", { name: /download excel report/i }));

        await waitFor(() => {
            expect(mockedOpenAuthedFile).toHaveBeenCalledWith(
                "license/reports/expiring-licenses/?format=excel&days=365",
                "expiring_licenses_365_days.xlsx",
            );
        });
        expect(input).toHaveValue(365);
    });
});
