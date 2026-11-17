import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DetailTabs } from "./DetailTabs";
import { ModuleAccordion } from "./ModuleAccordion";
import { LicenceCopiesSection } from "./LicenceCopiesSection";

vi.mock("@/utils/licenseCopyPdf", () => ({ openLicenseCopyPdf: vi.fn(() => Promise.resolve()) }));
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";

function Probe({ label, onMount }: { label: string; onMount?: () => void }) {
    onMount?.();
    return <div>{label}</div>;
}

describe("DetailTabs", () => {
    it("mounts only the active tab lazily and hides tabs with visible=false", async () => {
        const mounts: string[] = [];
        const tabs = [
            { id: "a", label: "A", render: () => <Probe label="body-a" onMount={() => mounts.push("a")} /> },
            { id: "b", label: "B", render: () => <Probe label="body-b" onMount={() => mounts.push("b")} /> },
            { id: "c", label: "C", visible: false, render: () => <div>body-c</div> },
        ];
        render(<DetailTabs recordKey="license:1" tabs={tabs} />);
        expect(screen.getByText("body-a")).toBeInTheDocument();
        expect(screen.queryByText("body-b")).not.toBeInTheDocument();
        expect(mounts).not.toContain("b");
        expect(screen.queryByRole("tab", { name: "C" })).not.toBeInTheDocument();

        await userEvent.click(screen.getByRole("tab", { name: "B" }));
        expect(screen.getByText("body-b")).toBeInTheDocument();
        expect(screen.queryByText("body-a")).not.toBeInTheDocument();
    });

    it("resets active tab and unmounts content when recordKey changes", async () => {
        const tabs = [
            { id: "a", label: "A", render: () => <div>body-a</div> },
            { id: "b", label: "B", render: () => <Probe label="body-b" /> },
        ];
        const { rerender } = render(<DetailTabs recordKey="license:1" tabs={tabs} />);
        await userEvent.click(screen.getByRole("tab", { name: "B" }));
        expect(screen.getByText("body-b")).toBeInTheDocument();
        rerender(<DetailTabs recordKey="license:2" tabs={tabs} />);
        expect(screen.queryByText("body-b")).not.toBeInTheDocument();
        expect(screen.getByText("body-a")).toBeInTheDocument();
    });

    it("supports controlled value and reports changes", async () => {
        const seen: string[] = [];
        const tabs = [
            { id: "a", label: "A", render: () => <div>body-a</div> },
            { id: "b", label: "B", render: () => <div>body-b</div> },
        ];
        render(<DetailTabs recordKey="r" tabs={tabs} value="b" onValueChange={(id) => seen.push(id)} />);
        expect(screen.getByText("body-b")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("tab", { name: "A" }));
        expect(seen.length).toBeGreaterThan(0);
        expect(new Set(seen)).toEqual(new Set(["a"]));
    });
});

describe("ModuleAccordion", () => {
    beforeEach(() => sessionStorage.clear());
    const sections = [
        { id: "one", title: "One", defaultOpen: true, render: () => <div>content-one</div> },
        { id: "two", title: "Two", render: () => <div>content-two</div> },
        { id: "three", title: "Three", render: () => <div>content-three</div> },
    ];

    it("toggles with keyboard and exposes aria-expanded", async () => {
        const user = userEvent.setup();
        render(<ModuleAccordion sections={sections} />);
        const one = screen.getByRole("button", { name: "One" });
        const two = screen.getByRole("button", { name: "Two" });
        expect(one).toHaveAttribute("aria-expanded", "true");
        expect(two).toHaveAttribute("aria-expanded", "false");
        expect(screen.queryByText("content-two")).not.toBeInTheDocument();

        one.focus();
        await user.keyboard("{ArrowDown}");
        expect(two).toHaveFocus();
        await user.keyboard("{Enter}");
        expect(two).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByText("content-two")).toBeInTheDocument();
        await user.keyboard("{End}");
        expect(screen.getByRole("button", { name: "Three" })).toHaveFocus();
        await user.keyboard("{Home}");
        expect(one).toHaveFocus();
        await user.keyboard("{ArrowUp}");
        expect(screen.getByRole("button", { name: "Three" })).toHaveFocus();
    });

    it("persists open state per persistKey in sessionStorage", async () => {
        const user = userEvent.setup();
        const { unmount } = render(<ModuleAccordion sections={sections} persistKey="license:1:ledger" />);
        await user.click(screen.getByRole("button", { name: "Two" }));
        await user.click(screen.getByRole("button", { name: "One" }));
        unmount();
        render(<ModuleAccordion sections={sections} persistKey="license:1:ledger" />);
        expect(screen.getByRole("button", { name: "One" })).toHaveAttribute("aria-expanded", "false");
        expect(screen.getByRole("button", { name: "Two" })).toHaveAttribute("aria-expanded", "true");
    });
});

describe("LicenceCopiesSection", () => {
    it("shows one button per distinct licence (first number wins) and opens its copy on click only", async () => {
        const open = openLicenseCopyPdf as unknown as ReturnType<typeof vi.fn>;
        open.mockClear();
        render(
            <LicenceCopiesSection
                emptyDescription="none"
                rows={[
                    { license_id: 11, license_number: "0310000011" },
                    { license_id: 11, license_number: "DUPLICATE" },
                    { license_id: 12, license_number: "0310000012" },
                    { license_id: 13, license_number: null },
                    { license_id: null, license_number: "NO-ID" },
                ]}
            />,
        );
        const section = screen.getByRole("region", { name: "Licence copies" });
        expect(section).toBeInTheDocument();
        const buttons = screen.getAllByRole("button");
        expect(buttons.map((b) => b.getAttribute("aria-label"))).toEqual([
            "Open License Copy PDF for 0310000011",
            "Open License Copy PDF for 0310000012",
        ]);
        expect(open).not.toHaveBeenCalled();
        await userEvent.click(screen.getByRole("button", { name: "Open License Copy PDF for 0310000012" }));
        expect(open).toHaveBeenCalledWith(12, "0310000012");
    });

    it("renders the empty state with the caller's description", () => {
        render(<LicenceCopiesSection rows={[]} emptyDescription="No licence rows are mapped to this BOE." />);
        const status = screen.getByRole("status");
        expect(status).toHaveTextContent("No licence documents");
        expect(status).toHaveTextContent("No licence rows are mapped to this BOE.");
        expect(screen.queryByRole("button")).toBeNull();
    });
});
