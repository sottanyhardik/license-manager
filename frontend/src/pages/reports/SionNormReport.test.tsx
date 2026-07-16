import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api/axios";
import SionNormReport, {
    buildSionReportPath,
    formatReportNumber,
    getSionReportGroups,
    normalizeBooleanFilter,
} from "./SionNormReport";

vi.mock("../../api/axios", () => ({
    default: {
        get: vi.fn(),
    },
}));

vi.mock("sonner", () => ({
    toast: {
        error: vi.fn(),
    },
}));

const mockedGet = vi.mocked(api.get);

describe("SionNormReport helpers", () => {
    it("normalizes filters and builds encoded report paths", () => {
        expect(normalizeBooleanFilter(" True ")).toBe("True");
        expect(normalizeBooleanFilter("bad", "False")).toBe("False");
        expect(
            buildSionReportPath({
                is_expired: "bad",
                is_null: "True",
                sion_norm: " E 132 ",
            }),
        ).toBe("licenses/active-dfia-report/?is_expired=False&is_null=True&sion_norm=E+132");
    });

    it("formats finite numbers and rejects malformed values", () => {
        expect(formatReportNumber("1234.5", 2)).toBe("1,234.50");
        expect(formatReportNumber(Number.NaN)).toBe("—");
        expect(formatReportNumber(Number.POSITIVE_INFINITY)).toBe("—");
        expect(formatReportNumber(null)).toBe("—");
    });

    it("returns an empty group list for malformed API payloads", () => {
        expect(getSionReportGroups(null)).toEqual([]);
        expect(getSionReportGroups({ groups: null })).toEqual([]);
        expect(getSionReportGroups({ groups: [{ license_count: 1 }] })).toEqual([{ license_count: 1 }]);
    });
});

describe("SionNormReport", () => {
    beforeEach(() => {
        mockedGet.mockReset();
        mockedGet.mockResolvedValue({ data: { groups: [] } });
    });

    it("renders an empty state for malformed report groups", async () => {
        mockedGet.mockResolvedValueOnce({ data: { groups: null } });

        render(<SionNormReport sionNorm="E1" title="SION Norm E1 - Parle Report" />);

        await waitFor(() => {
            expect(screen.getByText("No records found for SION Norm E1")).toBeInTheDocument();
        });
        expect(mockedGet).toHaveBeenCalledWith(
            "licenses/active-dfia-report/?is_expired=False&is_null=False&sion_norm=E1",
        );
    });

    it("reloads with normalized radio filters", async () => {
        render(<SionNormReport sionNorm="E5" title="SION Norm E5 - Parle Report" />);

        await waitFor(() => {
            expect(mockedGet).toHaveBeenCalledWith(
                "licenses/active-dfia-report/?is_expired=False&is_null=False&sion_norm=E5",
            );
        });

        fireEvent.click(screen.getByLabelText("Expired"));

        await waitFor(() => {
            expect(mockedGet).toHaveBeenCalledWith(
                "licenses/active-dfia-report/?is_expired=True&is_null=False&sion_norm=E5",
            );
        });
    });
});
