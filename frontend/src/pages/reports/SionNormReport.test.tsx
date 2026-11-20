import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api/axios";
import SionNormReport from "./SionNormReport";
import {
    buildSionReportPath,
    formatReportNumber,
    getSionReportGroups,
    normalizeBooleanFilter,
} from "./sionNormReportUtils";

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

        render(<SionNormReport sionNorm="E1" title="SION Norm E1 - Parle Report" />, { wrapper: MemoryRouter });

        await waitFor(() => {
            expect(screen.getByText("No records found for SION Norm E1")).toBeInTheDocument();
        });
        expect(mockedGet).toHaveBeenCalledWith(
            "licenses/active-dfia-report/?is_expired=False&is_null=False&sion_norm=E1",
        );
        // Writing the defaults into the URL must not trigger a second request.
        expect(mockedGet).toHaveBeenCalledTimes(1);
    });

    it("reloads with normalized radio filters", async () => {
        render(<SionNormReport sionNorm="E5" title="SION Norm E5 - Parle Report" />, { wrapper: MemoryRouter });

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

    it("restores the radio filters from the URL (refresh / shared link)", async () => {
        render(
            <MemoryRouter initialEntries={["/reports/parle/sion-e132?is_expired=True&is_null=True"]}>
                <SionNormReport sionNorm="E132" title="SION Norm E132 - Parle Report" />
            </MemoryRouter>,
        );

        await waitFor(() => {
            expect(mockedGet).toHaveBeenCalledWith(
                "licenses/active-dfia-report/?is_expired=True&is_null=True&sion_norm=E132",
            );
        });
        expect(mockedGet).toHaveBeenCalledTimes(1);
        expect(screen.getByLabelText("Expired")).toBeChecked();
        expect(screen.getByLabelText("< 200")).toBeChecked();
    });

    it("shows the group for the page's own norm when the API returns several", async () => {
        mockedGet.mockResolvedValueOnce({
            data: {
                groups: [
                    { sion_norm: "E1", license_count: 7, notifications: [], totals: {} },
                    { sion_norm: "E126", license_count: 3, notifications: [], totals: {} },
                ],
            },
        });

        render(<SionNormReport sionNorm="E126" title="SION Norm E126 - Parle Report" />, { wrapper: MemoryRouter });

        const totalCard = await screen.findByText("Total Licenses");
        expect(totalCard.nextElementSibling).toHaveTextContent("3");
    });
});
