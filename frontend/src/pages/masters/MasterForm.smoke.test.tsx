import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import MasterForm from "./MasterForm";
import api from "../../api/axios";

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

function fieldControl(label: string) {
  const labelNode = screen.getByText(label);
  const wrapper = labelNode.closest("div");
  const control = wrapper?.querySelector("input, textarea");

  if (!control) {
    throw new Error(`No form control found for ${label}`);
  }

  return control as HTMLInputElement | HTMLTextAreaElement;
}

describe("MasterForm smoke", () => {
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
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: COMPANY_META });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { id: 12 } });
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { id: 12 } });
  });

  it("creates a generic master record from metadata defaults", async () => {
    const user = userEvent.setup();

    renderAt("/masters/companies/create");

    expect(await screen.findByText(/New\s+Companies/)).toBeInTheDocument();
    expect(screen.getByText("Create a new record")).toBeInTheDocument();
    expect(fieldControl("Name")).toHaveValue("Default Company");
    expect(screen.getByText("Yes")).toBeInTheDocument();

    await user.clear(fieldControl("Name"));
    await user.type(fieldControl("Name"), "Acme Exports");
    await user.type(fieldControl("Email"), "ops@acme.test");
    await user.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith("masters/companies/", {
        name: "Acme Exports",
        email: "ops@acme.test",
        is_active: true,
      });
    });

    expect(await screen.findByText("Companies list")).toBeInTheDocument();
  });

  it("loads and updates an existing generic master record", async () => {
    const user = userEvent.setup();
    (api.get as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({ data: COMPANY_META })
      .mockResolvedValueOnce({
        data: {
          id: 12,
          name: "Existing Company",
          email: "old@example.test",
          is_active: false,
          created_on: "2026-01-01T00:00:00Z",
          modified_on: "2026-01-02T00:00:00Z",
        },
      });

    renderAt("/masters/companies/12/edit");

    expect(await screen.findByText(/Edit\s+Companies/)).toBeInTheDocument();
    expect(screen.getByText("Update existing record")).toBeInTheDocument();

    await waitFor(() => expect(fieldControl("Name")).toHaveValue("Existing Company"));
    expect(screen.getByText("No")).toBeInTheDocument();

    await user.clear(fieldControl("Email"));
    await user.type(fieldControl("Email"), "new@example.test");
    await user.click(screen.getByRole("button", { name: /update/i }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith("masters/companies/12/", {
        id: 12,
        name: "Existing Company",
        email: "new@example.test",
        is_active: false,
      });
    });

    const list = await screen.findByText("Companies list");
    expect(within(list.parentElement as HTMLElement).getByText("Companies list")).toBeInTheDocument();
  });
});
