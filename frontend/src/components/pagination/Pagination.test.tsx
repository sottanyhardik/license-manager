import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";

const props = { page: 2, totalPages: 5, count: 120, pageSize: 25, hasPrevious: true, hasNext: true };

describe("Pagination", () => {
    it("has nav landmark, live count, aria-current", () => {
        render(<Pagination {...props} onPageChange={() => {}} />);
        expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
        expect(screen.getByText("Rows 26-50 of 120")).toHaveAttribute("aria-live", "polite");
        expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
    });

    it("emits page changes and clamps to range", async () => {
        const onPageChange = vi.fn();
        render(<Pagination {...props} onPageChange={onPageChange} />);
        await userEvent.click(screen.getByRole("button", { name: "Next page" }));
        await userEvent.click(screen.getByRole("button", { name: "First page" }));
        await userEvent.click(screen.getByRole("button", { name: "Last page" }));
        expect(onPageChange.mock.calls.map((c) => c[0])).toEqual([3, 1, 5]);
    });

    it("disables prev/next at the edges", () => {
        render(<Pagination {...props} page={1} hasPrevious={false} onPageChange={() => {}} />);
        expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    });

    it("emits page size and never offers more than 200", async () => {
        const onPageSizeChange = vi.fn();
        render(<Pagination {...props} pageSizes={[25, 200, 500, 1000]} onPageChange={() => {}} onPageSizeChange={onPageSizeChange} />);
        const select = screen.getByLabelText("Rows per page");
        const values = Array.from(select.querySelectorAll("option")).map((o) => Number(o.value));
        expect(Math.max(...values)).toBe(200);
        await userEvent.selectOptions(select, "200");
        expect(onPageSizeChange).toHaveBeenCalledWith(200);
    });
});
