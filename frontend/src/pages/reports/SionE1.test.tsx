import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SionE1 from "./SionE1";

vi.mock("./SionNormReport", () => ({
    default: ({ sionNorm, title }: { sionNorm: string; title: string }) => (
        <div data-testid="sion-report" data-sion-norm={sionNorm}>
            {title}
        </div>
    ),
}));

describe("SionE1", () => {
    it("renders the shared SION report with the E1 contract", () => {
        render(<SionE1 />);

        expect(screen.getByTestId("sion-report")).toHaveAttribute("data-sion-norm", "E1");
        expect(screen.getByText("SION Norm E1 - Parle Report")).toBeInTheDocument();
    });
});
