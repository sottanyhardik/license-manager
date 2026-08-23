import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { downloadLicenseLedgerExcel, previewLicenseLedgerPdf } from "./licenseLedgerExport";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));

const mockedGet = vi.mocked(api.get);

describe("shared License Ledger export client", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.stubGlobal("URL", {
            createObjectURL: vi.fn(() => "blob:ledger"),
            revokeObjectURL: vi.fn(),
        });
    });

    it("previews PDF in a new tab using the authenticated canonical export endpoint", async () => {
        const replace = vi.fn();
        const preview = { opener: window, document: { title: "" }, location: { replace }, close: vi.fn() };
        vi.spyOn(window, "open").mockReturnValue(preview as unknown as Window);
        mockedGet.mockResolvedValue({ data: new Blob(["%PDF"], { type: "application/pdf" }) });

        await previewLicenseLedgerPdf({ licenseId: 2436, itemId: 766, licenseType: "DFIA" });

        expect(window.open).toHaveBeenCalledWith("", "_blank");
        expect(mockedGet).toHaveBeenCalledWith(
            "license-ledger/export/?file_format=pdf&license_id=2436&item_id=766&license_type=DFIA",
            { responseType: "blob" },
        );
        expect(replace).toHaveBeenCalledWith("blob:ledger#zoom=100");
    });

    it("downloads Excel directly with the route-derived filename", async () => {
        mockedGet.mockResolvedValue({ data: new Blob(["xlsx"]) });
        const click = vi.fn();
        const anchor = document.createElement("a");
        anchor.click = click;
        vi.spyOn(document, "createElement").mockReturnValue(anchor);

        await downloadLicenseLedgerExcel({ licenseId: 2436, itemId: 766 });

        expect(anchor.download).toBe("license-ledger-2436-766.xlsx");
        expect(click).toHaveBeenCalledOnce();
    });

    it("reports popup blocking before making a request", async () => {
        vi.spyOn(window, "open").mockReturnValue(null);
        await expect(previewLicenseLedgerPdf({})).rejects.toThrow(/blocked/i);
        expect(mockedGet).not.toHaveBeenCalled();
    });
});
