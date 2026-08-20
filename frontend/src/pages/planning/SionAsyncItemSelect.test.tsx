import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { SionImportItemAsyncSelect } from "./SionAsyncItemSelect";

vi.mock("@/services/api/planningRuleApi", () => ({
  searchSionImportItems: vi.fn().mockResolvedValue({
    items: [{ id: 41, name: "Sweet whey powder" }],
    nextPage: null,
  }),
  fetchSionImportItem: vi.fn().mockResolvedValue({ id: 41, name: "Sweet whey powder" }),
}));

function StatefulSelector() {
  const [value, setValue] = useState<number | null>(null);
  return <SionImportItemAsyncSelect sionId={7} value={value} onChange={setValue} />;
}

describe("SionImportItemAsyncSelect", () => {
  it("retains an item selected by an inline parent callback", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const user = userEvent.setup();
    render(<QueryClientProvider client={client}><StatefulSelector /></QueryClientProvider>);

    await user.click(screen.getByText("Search import item..."));
    await user.click(await screen.findByText("Sweet whey powder"));

    expect(await screen.findByText("Sweet whey powder")).toBeInTheDocument();
  });
});
