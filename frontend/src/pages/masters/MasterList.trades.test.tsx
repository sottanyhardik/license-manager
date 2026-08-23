import { describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

const listResponse = {
  results: [],
  count: 0,
  list_display: [],
  form_fields: [],
  search_fields: [],
  filter_fields: [],
  filter_config: {},
  ordering_fields: [],
  nested_field_defs: {},
  nested_list_display: {},
  field_meta: {},
  default_filters: {},
  inline_editable: [],
};

vi.mock("../../api/axios", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: listResponse })),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("../../services/api", () => ({
  boeApi: { fetchBOEList: vi.fn() },
}));

import { groupLinkedTrades } from "./MasterList";
import MasterList from "./MasterList";
import api from "../../api/axios";

const authValue = {
  user: { id: 1, username: "trade-user", is_superuser: true, roles: [] },
  loading: false,
  loginSuccess: vi.fn(),
  logout: vi.fn(),
  hasRole: () => true,
  hasAnyRole: () => true,
  isSuperAdmin: () => true,
  canManageUsers: () => true,
};

function renderTrades() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authValue as never}>
        <MemoryRouter initialEntries={["/trades"]}>
          <Routes>
            <Route path="/trades" element={<MasterList />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("groupLinkedTrades", () => {
  it("groups linked sale and purchase rows once without changing list order", () => {
    const groups = groupLinkedTrades([
      { id: 18, direction: "PURCHASE", linked_trade_info: { id: 17 } },
      { id: 17, direction: "SALE", linked_trade_info: { id: 18 } },
      { id: 19, direction: "COMMISSION_SALE", linked_trade_info: null },
    ]);

    expect(groups).toEqual([
      {
        type: "pair",
        sale: { id: 17, direction: "SALE", linked_trade_info: { id: 18 } },
        purchase: { id: 18, direction: "PURCHASE", linked_trade_info: { id: 17 } },
        pairKey: "pair-17",
      },
      {
        type: "single",
        trade: { id: 19, direction: "COMMISSION_SALE", linked_trade_info: null },
        pairKey: "single-19",
      },
    ]);
  });

  it("keeps a linked row single when its partner is outside the current page", () => {
    const groups = groupLinkedTrades([
      { id: 31, direction: "SALE", linked_trade_info: { id: 99 } },
    ]);

    expect(groups).toEqual([
      {
        type: "single",
        trade: { id: 31, direction: "SALE", linked_trade_info: { id: 99 } },
        pairKey: "single-31",
      },
    ]);
  });

  it("performs one ID lookup per row for a large linked page", () => {
    const trades = Array.from({ length: 1_000 }, (_, index) => {
      const id = index + 1;
      const partner = id % 2 === 0 ? id - 1 : id + 1;
      return {
        id,
        direction: id % 2 === 0 ? "PURCHASE" : "SALE",
        linked_trade_info: { id: partner },
      };
    });

    const groups = groupLinkedTrades(trades);

    expect(groups).toHaveLength(500);
    expect(groups.every((group) => group.type === "pair")).toBe(true);
  });

  it("issues one canonical list request for the initial trades route", async () => {
    const get = api.get as unknown as ReturnType<typeof vi.fn>;
    get.mockClear();
    renderTrades();

    await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
    expect(get).toHaveBeenCalledWith(
      "trades/",
      expect.objectContaining({
        params: { page: 1, page_size: 25 },
        signal: expect.any(AbortSignal),
      }),
    );
  });
});
