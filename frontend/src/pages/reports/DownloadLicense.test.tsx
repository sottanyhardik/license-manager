import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

import api from "../../api/axios";
import DownloadLicense, { normalizeDownloadDays, parseLicenseNumbers } from "./DownloadLicense";

vi.mock("../../api/axios", () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
        success: vi.fn(),
    },
}));

const mockedApiGet = vi.mocked(api.get);
const mockedApiPost = vi.mocked(api.post);
const mockedToast = vi.mocked(toast);

describe("DownloadLicense helpers", () => {
    it("normalizes days to supported report boundaries", () => {
        expect(normalizeDownloadDays("45")).toBe(45);
        expect(normalizeDownloadDays("0")).toBe(1);
        expect(normalizeDownloadDays("-3")).toBe(1);
        expect(normalizeDownloadDays("99999")).toBe(3650);
        expect(normalizeDownloadDays("bad")).toBe(365);
    });

    it("parses, trims, and deduplicates license numbers", () => {
        expect(parseLicenseNumbers(" LIC-1,LIC-2\nLIC-1  LIC-3 ")).toEqual(["LIC-1", "LIC-2", "LIC-3"]);
        expect(parseLicenseNumbers(" , \n\t ")).toEqual([]);
    });
});

describe("DownloadLicense", () => {
    const clickedDownloads: string[] = [];

    beforeEach(() => {
        vi.restoreAllMocks();
        vi.clearAllMocks();
        clickedDownloads.length = 0;
        mockedApiGet.mockResolvedValue({ data: { licenses: [{ license_number: "LIC-A" }] } });
        mockedApiPost.mockResolvedValue({ data: new Blob(["xlsx"]) });

        Object.defineProperty(window.URL, "createObjectURL", {
            value: vi.fn(() => "blob:download"),
            configurable: true,
        });
        Object.defineProperty(window.URL, "revokeObjectURL", {
            value: vi.fn(),
            configurable: true,
        });
        vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function click(this: HTMLAnchorElement) {
            clickedDownloads.push(this.download);
        });
    });

    it("deduplicates manual license numbers before requesting the bulk Excel export", async () => {
        render(<DownloadLicense />);

        fireEvent.change(screen.getByLabelText("License Numbers"), {
            target: { value: " LIC-1, LIC-2\nLIC-1 " },
        });
        fireEvent.click(screen.getByRole("button", { name: /download excel \(2 licenses\)/i }));

        await waitFor(() => {
            expect(mockedApiPost).toHaveBeenCalledWith(
                "licenses/bulk-balance-excel/",
                { license_numbers: ["LIC-1", "LIC-2"] },
                { responseType: "blob" },
            );
        });
        expect(clickedDownloads).toContain("bulk_license_summary_2_licenses.xlsx");
        expect(mockedToast.success).toHaveBeenCalledWith("Downloaded Excel for 2 license(s)");
    });

    it("normalizes status days and filters malformed report rows before bulk export", async () => {
        mockedApiGet.mockResolvedValue({
            data: {
                licenses: [
                    { license_number: " LIC-A " },
                    { license_number: "" },
                    { license_number: null },
                    {},
                ],
            },
        });
        render(<DownloadLicense />);

        fireEvent.change(screen.getByLabelText("Look-back period (days)"), { target: { value: "99999" } });
        fireEvent.click(screen.getByRole("button", { name: /^download excel$/i }));

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("reports/active-licenses/?days=3650");
        });
        expect(mockedApiPost).toHaveBeenCalledWith(
            "licenses/bulk-balance-excel/",
            { license_numbers: ["LIC-A"] },
            { responseType: "blob" },
        );
        expect(clickedDownloads).toContain("licenses_active_3650days.xlsx");
    });

    it("uses the expiring-license report endpoint when expiring status is selected", async () => {
        render(<DownloadLicense />);

        fireEvent.click(screen.getByRole("button", { name: "Expiring Soon" }));
        fireEvent.change(screen.getByLabelText("Expiring within (days)"), { target: { value: "45" } });
        fireEvent.click(screen.getByRole("button", { name: /^download excel$/i }));

        await waitFor(() => {
            expect(mockedApiGet).toHaveBeenCalledWith("reports/expiring-licenses/?days=45");
        });
        expect(clickedDownloads).toContain("licenses_expiring_45days.xlsx");
    });

    it("keeps the manual export action disabled for empty input", () => {
        render(<DownloadLicense />);

        const button = screen.getByRole("button", { name: /download excel \(0 licenses\)/i });

        expect(button).toBeDisabled();
        expect(mockedApiPost).not.toHaveBeenCalled();
        expect(mockedToast.error).not.toHaveBeenCalled();
    });
});
