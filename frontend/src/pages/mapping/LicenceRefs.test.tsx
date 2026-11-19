import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import LicenceRefs from "./LicenceRefs";

const refs = Array.from({ length: 6 }, (_, n) => ({ id: 100 + n, license_number: `34110085${String(n).padStart(2, "0")}` }));

describe("LicenceRefs", () => {
    it("two records on one licence show 2 records · 1 licence and the number once", () => {
        render(<MemoryRouter><LicenceRefs refs={[refs[0]]} records={2} label="X" /></MemoryRouter>);
        expect(screen.getByText("2 records · 1 licence")).toBeInTheDocument();
        expect(screen.getAllByRole("link")).toHaveLength(1);
    });

    it("shows the first few, + N more reveals all, each chip opens /licenses/:id/overview", async () => {
        render(<MemoryRouter><LicenceRefs refs={refs} records={9} label="REFINED PALMOLEIN OIL" /></MemoryRouter>);
        const list = screen.getByRole("list", { name: "Licences for REFINED PALMOLEIN OIL" });
        expect(within(list).getAllByRole("link")).toHaveLength(3);
        await userEvent.setup().click(screen.getByRole("button", { name: "+ 3 more" }));
        const links = within(list).getAllByRole("link");
        expect(links.map((l) => l.getAttribute("href"))).toEqual(refs.map((r) => `/licenses/${r.id}/overview`));
    });
});
