import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/api/axios", () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import { describeBoeMerge, extractBoeError } from "@/api/boeApi";
import BoeMergeModal from "@/pages/masters/BoeMergeModal";

describe("describeBoeMerge", () => {
    it("plain success keeps the server message", () => {
        expect(describeBoeMerge({ message: "Merged", target_boe_id: 5 }, 5)).toBe("Merged");
    });
    it("swapped merge names the surviving BOE", () => {
        expect(describeBoeMerge({ message: "Merged", target_boe_id: 9, swapped: true }, 5)).toContain("#9");
    });
    it("falls back when the server sends nothing", () => {
        expect(describeBoeMerge(undefined, 5)).toBe("BOE merged successfully");
    });
});

describe("merge rejection", () => {
    it("extracts the server {error} and the modal shows it", () => {
        const err = { response: { data: { error: "BOE has trade links" } } };
        const msg = extractBoeError(err, "Failed");
        expect(msg).toBe("BOE has trade links");
        render(
            <BoeMergeModal
                mergeBoeTarget={{ id: 1, bill_of_entry_number: "7" }} closeMergeModal={() => {}}
                mergeCandidatesLoading={false} mergeCandidates={[]} mergeBoeSource={null}
                setMergeBoeSource={() => {}} mergeBoeLoading={false} mergeError={msg} doMerge={() => {}}
            />,
        );
        expect(screen.getByRole("alert")).toHaveTextContent("BOE has trade links");
    });
});
