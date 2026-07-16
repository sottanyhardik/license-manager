import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ExpiringLicenses from "./ExpiringLicenses";
import { openAuthedFile } from "@/utils/documentDownload";

vi.mock("@/utils/documentDownload", () => ({
    openAuthedFile: vi.fn().mockResolvedValue(undefined),
}));

const mockedOpenAuthedFile = vi.mocked(openAuthedFile);

describe("ExpiringLicenses", () => {
    it("renders expiring-license export copy and default lookahead", () => {
        render(<ExpiringLicenses />);

        expect(screen.getByRole("heading", { name: "Expiring Licenses Report" })).toBeInTheDocument();
        expect(screen.getByText("Export licenses expiring within the specified number of days")).toBeInTheDocument();
        expect(screen.getByLabelText("Days from today")).toHaveValue(30);
        expect(screen.getByText("Licenses expiring between today and 30 days from now")).toBeInTheDocument();
        expect(screen.getByText("Excludes licenses with balance < 100")).toBeInTheDocument();
    });

    it("downloads the expiring-license report using the normalized lookahead period", async () => {
        render(<ExpiringLicenses />);

        fireEvent.change(screen.getByLabelText("Days from today"), { target: { value: "60" } });
        fireEvent.click(screen.getByRole("button", { name: /download excel report/i }));

        await waitFor(() => {
            expect(mockedOpenAuthedFile).toHaveBeenCalledWith(
                "license/reports/expiring-licenses/?format=excel&days=60",
                "expiring_licenses_60_days.xlsx",
            );
        });
    });
});
