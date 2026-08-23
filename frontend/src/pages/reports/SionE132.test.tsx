import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import SionE132 from "./SionE132";

vi.mock("./SionNormReport", () => ({
    default: ({ sionNorm, title }: { sionNorm: string; title: string }) => (
        <div data-testid="sion-report" data-sion-norm={sionNorm}>
            {title}
        </div>
    ),
}));

describe("SionE132", () => {
    it("renders the shared SION report with the E132 contract", () => {
        render(<SionE132 />);

        expect(screen.getByTestId("sion-report")).toHaveAttribute("data-sion-norm", "E132");
        expect(screen.getByText("SION Norm E132 - Parle Report")).toBeInTheDocument();
    });
});
