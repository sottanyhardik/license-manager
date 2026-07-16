import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ActiveLicenses from "./ActiveLicenses";
import { openAuthedFile } from "@/utils/documentDownload";

vi.mock("@/utils/documentDownload", () => ({
    openAuthedFile: vi.fn().mockResolvedValue(undefined),
}));

const mockedOpenAuthedFile = vi.mocked(openAuthedFile);

describe("ActiveLicenses", () => {
    it("renders active-license export copy without stale year-specific language", () => {
        render(<ActiveLicenses />);

        expect(screen.getByRole("heading", { name: "Active Licenses Report" })).toBeInTheDocument();
        expect(
            screen.getByText("Export all active licenses from today minus the selected lookback period onward"),
        ).toBeInTheDocument();
        expect(screen.getByLabelText("Days to look back")).toHaveValue(30);
        expect(screen.getByText("Shows licenses expiring from 30 days ago onward")).toBeInTheDocument();
        expect(screen.getByText("Shows active licenses expiring from today minus the selected lookback period onward")).toBeInTheDocument();
        expect(screen.queryByText(/2026|2027/)).not.toBeInTheDocument();
    });

    it("downloads the active-license report using the normalized lookback period", async () => {
        render(<ActiveLicenses />);

        fireEvent.change(screen.getByLabelText("Days to look back"), { target: { value: "45" } });
        fireEvent.click(screen.getByRole("button", { name: /download excel report/i }));

        await waitFor(() => {
            expect(mockedOpenAuthedFile).toHaveBeenCalledWith(
                "license/reports/active-licenses/?format=excel&days=45",
                "active_licenses_45_days.xlsx",
            );
        });
    });
});
