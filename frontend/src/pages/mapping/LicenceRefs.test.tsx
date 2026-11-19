import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { LICENCE_LIST_URL, takeLicenceTarget } from "@/features/licenses/openLicenceTarget";
import LicenceRefs from "./LicenceRefs";

const refs = Array.from({ length: 6 }, (_, n) => ({ id: 100 + n, license_number: `02101183${String(90 + n)}` }));
function Where() { const l = useLocation(); return <div data-testid="where">{l.pathname + l.search}</div>; }
const renderRefs = (ui: React.ReactNode) => render(<MemoryRouter><Routes><Route path="*" element={<>{ui}<Where /></>} /></Routes></MemoryRouter>);

beforeEach(() => sessionStorage.clear());

describe("LicenceRefs", () => {
    it("two records on one licence show 2 records · 1 licence and the number once", () => {
        renderRefs(<LicenceRefs refs={[refs[0]]} records={2} label="X" />);
        expect(screen.getByText("2 records · 1 licence")).toBeInTheDocument();
        expect(screen.getAllByRole("link")).toHaveLength(1);
    });

    it("a chip opens the Licence List with the standard filters and hands over the real licence id + number", async () => {
        renderRefs(<LicenceRefs refs={refs} records={9} label="REFINED PALMOLEIN OIL" />);
        await userEvent.setup().click(screen.getByRole("link", { name: "Open licence 0210118390" }));
        expect(screen.getByTestId("where").textContent).toBe(LICENCE_LIST_URL);
        expect(LICENCE_LIST_URL).toBe("/licenses?flags__is_null=False&is_expired=False&page=1&purchase_status=11%2C10%2C1%2C2%2C4%2C5%2C7");
        expect(takeLicenceTarget()).toEqual({ id: 100, license_number: "0210118390" });
    });

    it("chips revealed by + N more behave the same", async () => {
        const user = userEvent.setup();
        renderRefs(<LicenceRefs refs={refs} records={9} label="REFINED PALMOLEIN OIL" />);
        const list = screen.getByRole("list", { name: "Licences for REFINED PALMOLEIN OIL" });
        expect(within(list).getAllByRole("link")).toHaveLength(3);
        await user.click(screen.getByRole("button", { name: "+ 3 more" }));
        expect(within(list).getAllByRole("link")).toHaveLength(6);
        await user.click(within(list).getByRole("link", { name: "Open licence 0210118395" }));
        expect(takeLicenceTarget()).toEqual({ id: 105, license_number: "0210118395" });
    });

    it("the count uses the exact total when the list itself is truncated", () => {
        renderRefs(<LicenceRefs refs={refs.slice(0, 2)} records={300} total={223} label="Y" />);
        expect(screen.getByText("300 records · 223 licences")).toBeInTheDocument();
    });

    it("a modified click (new tab) hands nothing over", async () => {
        renderRefs(<LicenceRefs refs={refs} records={9} label="Z" />);
        const user = userEvent.setup();
        await user.keyboard("{Control>}");
        await user.click(screen.getByRole("link", { name: "Open licence 0210118390" }));
        await user.keyboard("{/Control}");
        expect(takeLicenceTarget()).toBeNull();
    });
});

