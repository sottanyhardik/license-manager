import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DebouncedAsyncSelect from "./DebouncedAsyncSelect";
import { _fkDetailCache, _fkInFlight } from "./fkDetailCache";

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../api/axios", () => ({ default: { get } }));

describe("DebouncedAsyncSelect selected-label lookups", () => {
    beforeEach(() => {
        get.mockReset();
        _fkDetailCache.clear();
        _fkInFlight.clear();
        get.mockImplementation((url: string) => {
            const id = url.match(/(\d+)\/$/)?.[1];
            return Promise.resolve({ data: { id: Number(id), name: `Co ${id}` } });
        });
    });

    it("fetches each id once, then reuses the shared cache on remount and value change", async () => {
        const props = { endpoint: "/masters/companies/", isMulti: true, onChange: vi.fn() };
        const { rerender, unmount } = render(<DebouncedAsyncSelect {...props} value={[1, 2]} />);
        await waitFor(() => expect(screen.getByText("Co 2")).toBeTruthy());
        expect(get).toHaveBeenCalledTimes(2);

        // adding a third id only fetches the new one
        rerender(<DebouncedAsyncSelect {...props} value={[1, 2, 3]} />);
        await waitFor(() => expect(screen.getByText("Co 3")).toBeTruthy());
        expect(get).toHaveBeenCalledTimes(3);

        unmount();
        render(<DebouncedAsyncSelect {...props} value={[1, 2, 3]} />);
        await waitFor(() => expect(screen.getByText("Co 3")).toBeTruthy());
        expect(get).toHaveBeenCalledTimes(3);
    });
});
