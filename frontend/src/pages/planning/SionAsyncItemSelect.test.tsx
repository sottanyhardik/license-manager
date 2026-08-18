import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { SionImportItemAsyncSelect } from "./SionAsyncItemSelect";

const food = { id: 1261, name: "FOOD FLAVOUR - E126", sionCode: "E126" };
const searchSionImportItems = vi.fn(async (_sionId?: number, _search?: string, _page?: number) => ({ items: [food], nextPage: null }));
const fetchSionImportItem = vi.fn(async (_sionId?: number, _itemId?: number) => food);

vi.mock("@/services/api/planningRuleApi", () => ({
  searchSionImportItems: (sionId: number, search?: string, page?: number) => searchSionImportItems(sionId, search, page),
  fetchSionImportItem: (sionId: number, itemId: number) => fetchSionImportItem(sionId, itemId),
}));

function Harness() {
  const [value, setValue] = useState<number | null>(null);
  const [renders, setRenders] = useState(0);
  return <>
    <button onClick={() => setRenders((count) => count + 1)}>Parent rerender {renders}</button>
    <SionImportItemAsyncSelect sionId={126} value={value} onChange={setValue} />
  </>;
}

describe("SionImportItemAsyncSelect", () => {
  it("keeps the selected label through search clearing, parent rerender, and refetch", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const user = userEvent.setup();
    render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>);

    await user.type(screen.getByRole("combobox"), "foo");
    await user.click(await screen.findByText(food.name));
    expect(screen.getByText(food.name)).toBeVisible();
    expect(screen.getByRole("combobox")).toHaveValue("");

    await user.click(screen.getByRole("button", { name: /Parent rerender/ }));
    await client.invalidateQueries({ queryKey: ["sion-import-items"] });
    await waitFor(() => expect(searchSionImportItems).toHaveBeenCalled());
    expect(screen.getByText(food.name)).toBeVisible();
  });
});
