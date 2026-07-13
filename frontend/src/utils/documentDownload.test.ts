import { describe, it, expect } from "vitest";
import { toProtectedMediaPath } from "./documentDownload";

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
});
