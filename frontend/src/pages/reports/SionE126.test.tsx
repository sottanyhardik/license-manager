import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SionE126 from "./SionE126";

vi.mock("./SionNormReport", () => ({
    default: ({ sionNorm, title }: { sionNorm: string; title: string }) => (
        <div data-testid="sion-report" data-sion-norm={sionNorm}>
            {title}
        </div>
    ),
}));

describe("SionE126", () => {
    it("renders the shared SION report with the E126 contract", () => {
        render(<SionE126 />);

        expect(screen.getByTestId("sion-report")).toHaveAttribute("data-sion-norm", "E126");
        expect(screen.getByText("SION Norm E126 - Parle Report")).toBeInTheDocument();
    });
});
