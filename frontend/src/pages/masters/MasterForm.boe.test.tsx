import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import MasterForm from "./MasterForm";
import api from "../../api/axios";

const BOE_META = {
  form_fields: ["bill_of_entry_number", "port"],
  fields: ["bill_of_entry_number", "port"],
  nested_field_defs: {},
  field_meta: {
    bill_of_entry_number: { label: "BOE Number", required: true },
    port: { label: "Port" },
  },
};

const COMPANY_META = {
  form_fields: ["name", "email", "is_active"],
  fields: ["name", "email", "is_active"],
  nested_field_defs: {},
  field_meta: {
    name: { label: "Name", required: true, default: "Default Company" },
    email: { label: "Email", type: "email" },
    is_active: { label: "Active", type: "boolean", default: true },
  },
};

vi.mock("../../api/axios", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock("../../components/LicenseBalanceModal", () => ({
  default: () => null,
}));

vi.mock("./LicenseParsePanel", () => ({
  default: () => null,
}));

vi.mock("./BoeParsePanel", () => ({
  default: () => null,
}));

vi.mock("./NestedFieldArray", () => ({
  default: () => null,
}));

vi.mock("../../utils/documentDownload", () => ({
  openDocument: vi.fn(),
  toProtectedMediaPath: (path: string) => path,
}));

function renderAt(path: string) {
  const masterForm = (
    <MasterForm
      entityName={undefined}
      recordId={undefined}
      onClose={undefined}
      onSuccess={undefined}
    />
  );

  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/masters/:entity/create" element={masterForm} />
        <Route path="/masters/:entity/:id/edit" element={masterForm} />
        <Route path="/masters/:entity" element={<div>Companies list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function control(label: string) {
  return screen.getByLabelText(new RegExp(label, "i")) as HTMLInputElement;
}

const EXISTING = { id: 7, bill_of_entry_number: "BE-1", port: "INNSA" };

function mockBoeEdit() {
  (api.get as ReturnType<typeof vi.fn>).mockImplementation((url: string) =>
    Promise.resolve({ data: /\/7\/$/.test(url) ? EXISTING : BOE_META }),
  );
}

describe("MasterForm BOE sticky bars + unsaved guard", () => {
  beforeAll(() => {
    globalThis.ResizeObserver =
      globalThis.ResizeObserver ??
      class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      };
  });
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders labelled sticky header and footer for BOE, state is clean after load", async () => {
    mockBoeEdit();
    renderAt("/masters/bill-of-entries/7/edit");
    await waitFor(() => expect(control("BOE Number")).toHaveValue("BE-1"));
    expect(screen.getByRole("region", { name: "Bill of Entry header" })).toBeInTheDocument();
    const footer = screen.getByRole("region", { name: "Bill of Entry form actions" });
    expect(within(footer).getByRole("button", { name: /update/i })).toBeInTheDocument();
    expect(within(footer).getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Saved"));
  });

  it("prompts on Cancel only when dirty; stays on form if declined", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockBoeEdit();
    renderAt("/masters/bill-of-entries/7/edit");
    await waitFor(() => expect(control("BOE Number")).toHaveValue("BE-1"));
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Saved"));

    // clean: no prompt (leaves to list)
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("dirty Cancel prompts and keeps input when declined", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockBoeEdit();
    renderAt("/masters/bill-of-entries/7/edit");
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Saved"));
    await user.type(control("BOE Number"), "X");
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Unsaved changes"));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(control("BOE Number")).toHaveValue("BE-1X");
  });

  it("failed save keeps input and dirty state; successful save leaves without prompt", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockBoeEdit();
    (api.patch as ReturnType<typeof vi.fn>).mockRejectedValueOnce({ response: { status: 500, data: {} }, message: "boom" });
    renderAt("/masters/bill-of-entries/7/edit");
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Saved"));
    await user.type(control("BOE Number"), "Z");
    await user.click(screen.getByRole("button", { name: /update/i }));
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: /update/i })).toBeEnabled());
    expect(control("BOE Number")).toHaveValue("BE-1Z");
    expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Unsaved changes");

    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: { id: 7 } });
    await user.click(screen.getByRole("button", { name: /update/i }));
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(2));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("disables Save while a save is pending (no double submit)", async () => {
    const user = userEvent.setup();
    mockBoeEdit();
    let resolve!: (v: unknown) => void;
    (api.patch as ReturnType<typeof vi.fn>).mockReturnValue(new Promise((r) => { resolve = r; }));
    renderAt("/masters/bill-of-entries/7/edit");
    await waitFor(() => expect(screen.getByTestId("boe-form-state")).toHaveTextContent("Saved"));
    await user.type(control("BOE Number"), "Q");
    const save = screen.getByRole("button", { name: /update/i });
    await user.click(save);
    await waitFor(() => expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled());
    await user.click(screen.getByRole("button", { name: /saving/i }));
    expect(api.patch).toHaveBeenCalledTimes(1);
    resolve({ data: { id: 7 } });
  });

  it("non-BOE entities render without sticky regions or guard UI", async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: COMPANY_META });
    renderAt("/masters/companies/create");
    expect(await screen.findByText(/New\s+Companies/)).toBeInTheDocument();
    expect(screen.queryByRole("region")).toBeNull();
    expect(screen.queryByTestId("boe-form-state")).toBeNull();
  });
});
