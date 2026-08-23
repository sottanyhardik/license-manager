import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import TradesListView, { type TradeGroup } from "./TradesListView";

vi.mock("../../api/axios", () => ({ default: { get: vi.fn() } }));

const singleTrade = {
  id: 9,
  direction: "SALE",
  direction_label: "Sale",
  invoice_number: "INV-009",
  invoice_date: "2026-08-22",
  license_type_label: "Advance Authorisation",
  from_company_label: "Exporter One",
  to_company_label: "Buyer Two",
  total_amount: "0",
  paid_or_received: "1500.50",
  due_amount: "0",
  boes: [{ bill_of_entry_number: "BOE-1" }],
  lines: [{ id: 4, sr_number: 1, description: "Item one", qty_kg: "0", cif_fc: "0", cif_inr: "0", amount_inr: "0" }],
};

function renderView(groups: TradeGroup[] = [{ type: "single", trade: singleTrade, pairKey: "single-9" }]) {
  return render(<TradesListView
    loading={false}
    data={[singleTrade]}
    tradeGroups={groups}
    canWrite
    entityName="trades"
    filterParams={{}}
    currentPage={1}
    pageSize={25}
    navigate={vi.fn()}
    onDelete={vi.fn()}
    onOpenLink={vi.fn()}
    onCopyToCounterpart={vi.fn()}
    onTransferLetter={vi.fn()}
    expandedTrades={new Set()}
    onToggleTrade={vi.fn()}
    expandedPairs={new Set()}
    onTogglePair={vi.fn()}
  />);
}

describe("TradesListView", () => {
  it("renders explicit zero values together with all trade identity, counterparty, BOE, amount, and action information", () => {
    renderView();
    expect(screen.getByText("INV-009")).toBeInTheDocument();
    expect(screen.getByText("Exporter One")).toBeInTheDocument();
    expect(screen.getAllByText("Buyer Two").length).toBeGreaterThan(0);
    expect(screen.getByText("BOE-1")).toBeInTheDocument();
    expect(screen.getAllByText("₹0").length).toBeGreaterThan(0);
    expect(screen.getByTitle("Transfer Letter")).toBeInTheDocument();
    expect(screen.getByTitle("Edit")).toBeInTheDocument();
  });

  it("uses an accessible paired-trade disclosure instead of a clickable div", () => {
    const sale = { ...singleTrade, id: 10, invoice_number: "SALE-10" };
    const purchase = { ...singleTrade, id: 11, direction: "PURCHASE", invoice_number: "PURCHASE-11" };
    const onTogglePair = vi.fn();
    render(<TradesListView
      loading={false} data={[sale, purchase]}
      tradeGroups={[{ type: "pair", sale, purchase, pairKey: "pair-10" }]}
      canWrite entityName="trades" filterParams={{}} currentPage={1} pageSize={25}
      navigate={vi.fn()} onDelete={vi.fn()} onOpenLink={vi.fn()} onCopyToCounterpart={vi.fn()} onTransferLetter={vi.fn()}
      expandedTrades={new Set()} onToggleTrade={vi.fn()} expandedPairs={new Set()} onTogglePair={onTogglePair}
    />);
    const button = screen.getByRole("button", { name: /sale.*purchase/i });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(onTogglePair).toHaveBeenCalledWith("pair-10");
  });
});
