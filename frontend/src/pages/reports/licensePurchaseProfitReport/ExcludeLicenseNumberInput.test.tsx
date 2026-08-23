import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ExcludeLicenseNumberInput from "./ExcludeLicenseNumberInput";

describe("ExcludeLicenseNumberInput", () => {
    it("renders one chip per value", () => {
        render(<ExcludeLicenseNumberInput value={["0311051359", "0311051360"]} onChange={vi.fn()} />);

        expect(screen.getByText("0311051359")).toBeInTheDocument();
        expect(screen.getByText("0311051360")).toBeInTheDocument();
    });

    it("adds a chip when Enter is pressed after typing", () => {
        const onChange = vi.fn();
        render(<ExcludeLicenseNumberInput value={[]} onChange={onChange} />);

        const input = screen.getByRole("combobox");
        fireEvent.change(input, { target: { value: "0311051945" } });
        fireEvent.keyDown(input, { key: "Enter" });

        expect(onChange).toHaveBeenCalledWith(["0311051945"]);
    });

    it("splits comma-separated pasted text into multiple chips", () => {
        const onChange = vi.fn();
        render(<ExcludeLicenseNumberInput value={["0311050703"]} onChange={onChange} />);

        const input = screen.getByRole("combobox");
        const clipboardData = { getData: () => "0311051359, 0311051360" };
        fireEvent.paste(input, { clipboardData });

        expect(onChange).toHaveBeenCalledWith(["0311050703", "0311051359", "0311051360"]);
    });

    it("removes a chip via its remove button", () => {
        const onChange = vi.fn();
        render(<ExcludeLicenseNumberInput value={["0311050703", "0311051359"]} onChange={onChange} />);

        const removeButtons = document.querySelectorAll(".react-select__multi-value__remove");
        expect(removeButtons.length).toBe(2);
        fireEvent.click(removeButtons[0]);

        expect(onChange).toHaveBeenCalledWith(["0311051359"]);
    });
});
