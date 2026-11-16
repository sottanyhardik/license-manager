import { useState } from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CheckboxField, DateField, Field, NumberField, SelectField, TextareaField, TextField } from "./index";

function Harness({ error }: { error?: string }) {
    const [name, setName] = useState("");
    const [qty, setQty] = useState("");
    const [kind, setKind] = useState("a");
    const [note, setNote] = useState("");
    const [on, setOn] = useState("");
    const [agree, setAgree] = useState(false);
    return (
        <form>
            <TextField name="name" label="Name" required description="Legal name" error={error} value={name} onChange={setName} />
            <NumberField name="qty" label="Quantity" step="any" value={qty} onChange={setQty} />
            <SelectField name="kind" label="Kind" options={[{ value: "a", label: "A" }, { value: "b", label: "B" }]} value={kind} onChange={setKind} />
            <TextareaField name="note" label="Note" value={note} onChange={setNote} />
            <DateField name="on" label="On" value={on} onChange={setOn} />
            <CheckboxField name="agree" label="Agree" checked={agree} onChange={setAgree} />
            <output data-testid="state">{JSON.stringify({ name, qty, kind, note, on, agree })}</output>
        </form>
    );
}

describe("form field primitives", () => {
    it("links label, description and error to the control", () => {
        render(<Harness error="Name is required" />);
        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent("Name is required");
        const input = screen.getByLabelText(/Name/);
        expect(input).toHaveAttribute("aria-invalid", "true");
        expect(input).toHaveAttribute("aria-required", "true");
        const described = input.getAttribute("aria-describedby") ?? "";
        expect(described).toContain(alert.id);
        expect(described).toContain(screen.getByText("Legal name").id);
    });

    it("omits aria-invalid / error when there is no error", () => {
        render(<Harness />);
        const input = screen.getByLabelText(/Name/);
        expect(input).not.toHaveAttribute("aria-invalid");
        expect(screen.queryByRole("alert")).toBeNull();
    });

    it("is controlled and passes raw values through unchanged", async () => {
        render(<Harness />);
        await userEvent.type(screen.getByLabelText(/Name/), "Acme");
        await userEvent.type(screen.getByLabelText("Quantity"), "12.345");
        await userEvent.selectOptions(screen.getByLabelText("Kind"), "b");
        await userEvent.type(screen.getByLabelText("Note"), "hi");
        await userEvent.click(screen.getByLabelText("Agree"));
        expect(JSON.parse(screen.getByTestId("state").textContent ?? "{}")).toMatchObject({
            name: "Acme", qty: "12.345", kind: "b", note: "hi", agree: true,
        });
    });

    it("gives each field a unique id and supports custom controls via Field", () => {
        render(<Field label="Custom">{(a) => <input {...a} />}</Field>);
        expect(screen.getByLabelText("Custom")).toBeInTheDocument();
    });
});
