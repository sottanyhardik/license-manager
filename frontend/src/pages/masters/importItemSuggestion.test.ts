import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();
vi.mock("../../api/axios", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

import { suggestImportItem } from "./NestedFieldArray";

describe("suggestImportItem", () => {
    beforeEach(() => post.mockReset());

    it("asks the backend with the description and the licence's norm ids, and returns the first item", async () => {
        post.mockResolvedValue({ data: { items: [{ id: 5, name: "FRONT WHEELRIM" }] } });
        const item = await suggestImportItem("Front Wheel Rim", { export_license: [{ norm_class: "3" }] });
        expect(post).toHaveBeenCalledWith("import-item-suggestion/", { description: "Front Wheel Rim", norm_class_ids: [3] });
        expect(item).toEqual({ id: 5, name: "FRONT WHEELRIM" });
    });

    it("returns null without calling the backend when there is no norm or no description", async () => {
        expect(await suggestImportItem("Front Wheel Rim", { export_license: [] })).toBeNull();
        expect(await suggestImportItem("   ", { export_license: [{ norm_class: 3 }] })).toBeNull();
        expect(post).not.toHaveBeenCalled();
    });

    it("returns null when the backend suggests nothing or fails", async () => {
        post.mockResolvedValue({ data: { items: [] } });
        expect(await suggestImportItem("(DELETED)", { export_license: [{ norm_class: 3 }] })).toBeNull();
        post.mockResolvedValue(undefined); // malformed response: destructuring fails inside the helper
        expect(await suggestImportItem("Front Wheel Rim", { export_license: [{ norm_class: 3 }] })).toBeNull();
    });
});
