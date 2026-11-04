import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReplanBatchPanel } from "./ReplanBatchPanel";
import { retryableRequestIds } from "./planningOperationsModel";
import type { ReplanBatchStatus } from "@/services/api/planningRuleApi";

const base: ReplanBatchStatus = {
    state: "SUCCEEDED", requested: 2, processed: 2, succeeded: 2, failed: 0, skipped: 0, active: 0, partial_failures: 0,
    unknown_request_ids: [], initiated_by: "ops", started_at: "2026-11-03T10:00:00Z", completed_at: "2026-11-03T10:01:00Z",
    errors: [], request_ids: [1, 2],
};

describe("ReplanBatchPanel", () => {
    it("reports a clean batch as planned and offers no retry", () => {
        render(<ReplanBatchPanel label="E5 new eligible data" status={base} onRetry={vi.fn()} />);

        expect(screen.getByRole("heading", { name: /All licences planned/ })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Retry/ })).not.toBeInTheDocument();
    });

    it("never says all licences planned when some failed, and lists each failure", async () => {
        const onRetry = vi.fn();
        const status: ReplanBatchStatus = {
            ...base, state: "PARTIAL_FAILURE", succeeded: 1, failed: 2, partial_failures: 1,
            errors: [
                { request_id: 11, license_id: 5, license_number: "LIC-5", sion_id: 7, error_code: "OperationalError", error_message: "deadlock", attempts: 3 },
                { request_id: 12, license_id: 6, license_number: "LIC-6", sion_id: 7, error_code: "PlanningError", error_message: "no rule", attempts: 1 },
            ],
        };
        render(<ReplanBatchPanel label="E5 new" status={status} onRetry={onRetry} />);

        expect(screen.queryByText(/All licences planned/)).not.toBeInTheDocument();
        expect(screen.getByRole("heading", { name: /Some licences failed/ })).toBeInTheDocument();
        expect(screen.getByText("LIC-5")).toBeInTheDocument();
        expect(screen.getByText("deadlock")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "Retry 2 failed licences" }));
        expect(onRetry).toHaveBeenCalledWith([11, 12]);
    });

    it("does not offer retry while the batch is still running", () => {
        const status: ReplanBatchStatus = {
            ...base, state: "RUNNING", active: 1, succeeded: 0, errors: [
                { request_id: 11, license_id: 5, license_number: "LIC-5", sion_id: null, error_code: "X", error_message: "y", attempts: 1 },
            ],
        };
        render(<ReplanBatchPanel label="E5" status={status} onRetry={vi.fn()} />);

        expect(screen.getByRole("heading", { name: /Planning in progress/ })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Retry/ })).not.toBeInTheDocument();
    });

    it("de-duplicates retry ids when one licence has several failing norms", () => {
        const ids = retryableRequestIds({
            ...base, state: "PARTIAL_FAILURE", errors: [
                { request_id: 4, license_id: 1, license_number: "A", sion_id: 1, error_code: "E", error_message: "", attempts: 1 },
                { request_id: 4, license_id: 1, license_number: "A", sion_id: 2, error_code: "E", error_message: "", attempts: 1 },
            ],
        });
        expect(ids).toEqual([4]);
    });

    it("flags requests the server could not find", () => {
        render(<ReplanBatchPanel label="E1" status={{ ...base, state: "FAILED", unknown_request_ids: [999] }} onRetry={vi.fn()} />);

        expect(screen.getByRole("alert")).toHaveTextContent("1 request(s) could not be found");
    });
});
