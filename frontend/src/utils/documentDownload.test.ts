import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../api/axios";
import { normalizeAuthedFilePath, openAuthedFile, toProtectedMediaPath } from "./documentDownload";

vi.mock("../api/axios", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockedGet = vi.mocked(api.get);

beforeEach(() => {
  mockedGet.mockReset();
});

describe("toProtectedMediaPath", () => {
  it("normalizes a full media URL (strips host)", () => {
    expect(toProtectedMediaPath("https://host/media/licenses/1/copy.pdf")).toBe(
      "/media/licenses/1/copy.pdf",
    );
  });

  it("keeps an already /media/ path stable", () => {
    expect(toProtectedMediaPath("/media/foo/bar.pdf")).toBe("/media/foo/bar.pdf");
  });

  it("prefixes a bare relative path", () => {
    expect(toProtectedMediaPath("foo/bar.pdf")).toBe("/media/foo/bar.pdf");
  });

  it("handles a leading media/ without doubling", () => {
    expect(toProtectedMediaPath("media/x.pdf")).toBe("/media/x.pdf");
  });

  it("rejects empty and unsafe media paths", () => {
    expect(() => toProtectedMediaPath(" ")).toThrow("Protected media path is required.");
    expect(() => toProtectedMediaPath("folder\\file.pdf")).toThrow("Protected media path is required.");
  });
});

describe("normalizeAuthedFilePath", () => {
  it("keeps relative API paths stable", () => {
    expect(normalizeAuthedFilePath(" reports/item-report/?format=excel ")).toBe("reports/item-report/?format=excel");
    expect(normalizeAuthedFilePath("/licenses/1/merged-documents/")).toBe("/licenses/1/merged-documents/");
  });

  it("rejects blank, absolute, protocol-relative, and backslash paths", () => {
    expect(() => normalizeAuthedFilePath("")).toThrow("Authenticated file path is required.");
    expect(() => normalizeAuthedFilePath("https://example.test/file.pdf")).toThrow("relative to the API origin");
    expect(() => normalizeAuthedFilePath("//example.test/file.pdf")).toThrow("relative to the API origin");
    expect(() => normalizeAuthedFilePath("media\\file.pdf")).toThrow("unsafe characters");
  });
});

describe("openAuthedFile", () => {
  it("rejects unsafe paths before issuing a request", async () => {
    await expect(openAuthedFile("https://example.test/file.pdf")).rejects.toThrow("relative to the API origin");
    expect(mockedGet).not.toHaveBeenCalled();
  });
});
