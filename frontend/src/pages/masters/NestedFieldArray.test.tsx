import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import NestedFieldArray from "./NestedFieldArray";

const BOE_ITEM_FIELDS = [
    { name: "cif_inr", label: "CIF (INR)", type: "number" },
    { name: "cif_fc", label: "CIF (FC)", type: "number" },
    { name: "qty", label: "Quantity", type: "number" },
];

function BilledItemFields() {
    const [items, setItems] = useState([{ cif_inr: "", cif_fc: "", qty: "" }]);

    return (
        <NestedFieldArray
            label="Item details"
            fields={BOE_ITEM_FIELDS}
            value={items}
            onChange={setItems}
            fieldKey="item_details"
            entityName="bill-of-entries"
            formData={{ exchange_rate: "96.05" }}
        />
    );
}

describe("NestedFieldArray BOE amounts", () => {
    it("allows multi-digit entry while calculating only the counterpart", async () => {
        const user = userEvent.setup();
        render(<BilledItemFields />);

        const cifInr = screen.getByLabelText("CIF (INR)") as HTMLInputElement;
        const cifFc = screen.getByLabelText("CIF (FC)") as HTMLInputElement;
        const quantity = screen.getByLabelText("Quantity") as HTMLInputElement;

        await user.type(cifInr, "1200.25");
        expect(cifInr).toHaveValue("1200.25");
        expect(cifFc).toHaveValue("12.50");

        await user.clear(cifFc);
        await user.type(cifFc, "99.75");
        await user.type(quantity, "120000");

        expect(cifFc).toHaveValue("99.75");
        expect(quantity).toHaveValue("120000");
        expect(cifInr).toHaveAttribute("inputmode", "decimal");
    });
});
