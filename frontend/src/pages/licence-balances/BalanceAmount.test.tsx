import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import BalanceAmount from "./BalanceAmount";
import { statusDisplay } from "./labels";
import type { BalanceBlock } from "./types";

describe("BalanceAmount under licence-level CIF control", () => {
  const licenceControlledItem: BalanceBlock = {
    available: "-59388.22",
    is_over_utilised: false,
    status: "LICENCE-LEVEL CONTROL",
    cif_control: "LICENCE",
    raw_status: "OVER-UTILISED",
  };

  it("shows a negative item CIF as attribution: no over-utilised badge and no red text", () => {
    const { container } = render(<BalanceAmount block={licenceControlledItem} field="available" kind="cif" />);

    expect(screen.getByText("-59,388.22")).toBeInTheDocument();
    // The label is the row's CIF Control column, not part of the figure.
    expect(screen.queryByText("Licence-level CIF control")).not.toBeInTheDocument();
    expect(screen.queryByText("Over-utilised")).not.toBeInTheDocument();
    expect(container.querySelector(".text-destructive")).toBeNull();
  });

  it("badges over-utilisation only when the backend says so", () => {
    const itemLevel: BalanceBlock = { available: "-59388.22", is_over_utilised: true, status: "OVER-UTILISED", cif_control: "ITEM" };
    render(<BalanceAmount block={itemLevel} field="available" kind="cif" />);

    expect(screen.getByText("Over-utilised")).toBeInTheDocument();
    expect(screen.queryByText("Licence-level CIF control")).not.toBeInTheDocument();
  });

  it("does not infer over-utilisation from the sign of a figure the backend did not flag", () => {
    render(<BalanceAmount block={{ available: "-5.00", is_over_utilised: false, status: "RECONCILED" }} field="available" kind="cif" />);

    expect(screen.queryByText("Over-utilised")).not.toBeInTheDocument();
  });

});

describe("status labels for licence-level CIF control", () => {
  it("labels the item CIF status as licence-level control, in a neutral tone", () => {
    expect(statusDisplay("LICENCE-LEVEL CONTROL")).toEqual({
      label: "Licence-level CIF control",
      tone: "neutral",
      icon: "neutral",
    });
  });
});
