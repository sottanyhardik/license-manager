import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilterBar, type FilterDef } from "./FilterBar";

const defs: FilterDef[] = [
    { kind: "text", key: "license_number", label: "Licence number" },
    { kind: "select", key: "exporter", label: "Exporter", options: [{ value: "1", label: "Acme" }, { value: "2", label: "Beta" }] },
    { kind: "multiSelect", key: "port", label: "Port", options: [{ value: "A", label: "Alpha" }, { value: "B", label: "Bravo" }] },
    { kind: "status", key: "status", label: "Status", options: [{ value: "active", label: "Active", tone: "success" }, { value: "expired", label: "Expired", tone: "danger" }] },
    { kind: "dateRange", key: "expiry", label: "Expiry" },
    { kind: "numberRange", key: "balance", label: "Balance" },
];

afterEach(() => vi.useRealTimers());

describe("FilterBar", () => {
    it("explicit mode emits nothing until Apply, then an object with preserved param names", async () => {
        const user = userEvent.setup();
        const onApply = vi.fn();
        render(<FilterBar defs={defs} value={{}} onApply={onApply} />);

        await user.type(screen.getByLabelText("Licence number"), "0310");
        await user.selectOptions(screen.getByLabelText("Exporter"), "2");
        await user.click(screen.getByLabelText("Bravo"));
        await user.click(screen.getByRole("button", { name: "Active" }));
        fireEvent.change(screen.getByLabelText("Expiry from"), { target: { value: "2026-01-01" } });
        fireEvent.change(screen.getByLabelText("Expiry to"), { target: { value: "2026-12-31" } });
        await user.type(screen.getByLabelText("Balance min"), "10");
        expect(onApply).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "Apply" }));
        expect(onApply).toHaveBeenCalledTimes(1);
        expect(onApply).toHaveBeenCalledWith({
            license_number: "0310",
            exporter: "2",
            port: ["B"],
            status: "active",
            expiry_from: "2026-01-01",
            expiry_to: "2026-12-31",
            balance_min: "10",
        });
    });

    it("Clear empties a single field in the draft; Reset restores defaults and emits", async () => {
        const user = userEvent.setup();
        const onApply = vi.fn();
        render(
            <FilterBar defs={defs} value={{ license_number: "X", status: "expired" }} defaults={{ status: "active" }} onApply={onApply} />,
        );
        await user.click(screen.getByRole("button", { name: "Clear Licence number" }));
        expect(screen.getByLabelText("Licence number")).toHaveValue("");
        expect(onApply).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "Apply" }));
        expect(onApply).toHaveBeenLastCalledWith({ status: "expired" });

        await user.click(screen.getByRole("button", { name: "Reset" }));
        expect(onApply).toHaveBeenLastCalledWith({ status: "active" });
    });

    it("instant mode emits immediately for selects and debounces text", () => {
        vi.useFakeTimers();
        const onApply = vi.fn();
        render(<FilterBar defs={defs} value={{}} onApply={onApply} applyMode="instant" />);
        expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();

        fireEvent.change(screen.getByLabelText("Exporter"), { target: { value: "1" } });
        expect(onApply).toHaveBeenLastCalledWith({ exporter: "1" });

        fireEvent.change(screen.getByLabelText("Licence number"), { target: { value: "abc" } });
        expect(onApply).toHaveBeenCalledTimes(1);
        act(() => { vi.advanceTimersByTime(300); });
        expect(onApply).toHaveBeenLastCalledWith({ exporter: "1", license_number: "abc" });
    });

    it("exposes a labelled search form", () => {
        render(<FilterBar defs={defs} value={{}} onApply={() => {}} ariaLabel="Licence filters" />);
        expect(screen.getByRole("search", { name: "Licence filters" })).toBeInTheDocument();
    });
});
