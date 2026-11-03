import { describe, expect, it } from "vitest";
import { describeFlag, movementLabel, statusDisplay } from "./labels";
import { parseStoredColumns } from "./useOptionalColumns";

describe("statusDisplay", () => {
  it.each([
    ["RECONCILED", "Reconciled", "good", "check"],
    ["REVIEW REQUIRED", "Review required", "warn", "warning"],
    ["OVER-UTILISED", "Over-utilised", "bad", "down"],
    ["UNMAPPED ITEM", "Unmapped item", "neutral", "help"],
    ["OVER-ALLOCATED", "Over-allocated", "bad", "stop"],
    ["UNIT_UNVERIFIED", "Unit unverified", "info", "ruler"],
  ])("maps %s to a labelled, toned, iconned pill", (code, label, tone, icon) => {
    expect(statusDisplay(code)).toEqual({ label, tone, icon });
  });

  it("is case and whitespace tolerant", () => {
    expect(statusDisplay("  reconciled ").label).toBe("Reconciled");
  });

  it("passes unknown statuses through as the raw text", () => {
    expect(statusDisplay("SOMETHING NEW")).toEqual({ label: "SOMETHING NEW", tone: "neutral", icon: "neutral" });
  });

  it("labels an empty status", () => {
    expect(statusDisplay(null).label).toBe("No status");
  });
});

describe("describeFlag", () => {
  it.each([
    ["ALLOT_AND_SALE_OVERLAP_UNVERIFIED", "An allotment and a sale on the same item may be the same entitlement — review"],
    ["ALLOTMENT_LINKED_BOE_NOT_ON_ITEM", "An allotment is linked to a BOE on another licence or item"],
    ["CROSS_ITEM", "A BOE on this item is linked to a sale of another item"],
    ["OVER_LINKED", "BOEs linked to a sale exceed its amount; the excess is counted"],
    ["UNIT_UNVERIFIED", "Quantity unit is not verified"],
    ["OVER_LINKED_MIXED_OWNERSHIP", "Over-linked excess whose sale has both previous-owner and current-owner BOEs; the excess owner is not determined — review"],
    ["OVER_UTILISED", "Available is negative"],
  ])("explains %s in plain language", (code, text) => {
    expect(describeFlag(code)).toEqual({ code, text, known: true });
  });

  it("shows the raw code for an unknown flag", () => {
    expect(describeFlag("NEW_FLAG_X")).toEqual({ code: "NEW_FLAG_X", text: "NEW_FLAG_X", known: false });
  });
});

describe("movementLabel", () => {
  it.each([
    ["ORIGINAL", "Original authorisation"],
    ["SALE", "Sale (invoiced)"],
    ["SALE_COVERED_BOE", "Sale-covered BOE"],
    ["BOE_DEBIT", "Bill of entry (used)"],
    ["OVER_LINKED_EXCESS", "Over-linked excess"],
    ["ALLOTMENT", "Reserved for customer"],
  ])("labels %s", (kind, label) => {
    expect(movementLabel(kind)).toBe(label);
  });

  it("passes unknown kinds through", () => {
    expect(movementLabel("FUTURE_KIND")).toBe("FUTURE_KIND");
  });
});

describe("parseStoredColumns", () => {
  it("keeps only known optional column ids", () => {
    expect([...parseStoredColumns('["qtyOriginal","bogus","legacy"]')]).toEqual(["qtyOriginal", "legacy"]);
  });

  it("ignores corrupt or non-array storage", () => {
    expect(parseStoredColumns("not json").size).toBe(0);
    expect(parseStoredColumns('{"qtyOriginal":true}').size).toBe(0);
    expect(parseStoredColumns(null).size).toBe(0);
  });
});
