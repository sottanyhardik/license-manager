import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StickyFormBar } from "./StickyFormBar";

describe("StickyFormBar", () => {
  it("renders a labelled sticky region", () => {
    render(<StickyFormBar position="bottom" label="Actions"><button>Save</button></StickyFormBar>);
    const region = screen.getByRole("region", { name: "Actions" });
    expect(region.className).toContain("sticky");
    expect(region.className).toContain("bottom-0");
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("renders children untouched when disabled", () => {
    render(<StickyFormBar position="top" enabled={false} label="H"><span>x</span></StickyFormBar>);
    expect(screen.queryByRole("region")).toBeNull();
    expect(screen.getByText("x")).toBeInTheDocument();
  });
});
