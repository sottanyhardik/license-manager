import { describe, expect, it, vi, beforeEach } from "vitest";

import api from "../api/axios";
import { fetchCanonicalLedger } from "./canonicalLedgerAdapter";

vi.mock("../api/axios", () => ({ default: { get: vi.fn() } }));
const mockedGet = vi.mocked(api.get);

describe("fetchCanonicalLedger identity", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGet.mockResolvedValue({ data: { license_id: 7 } });
    });

    it("sends the licence type so a shared numeric id resolves to the requested record", async () => {
        await fetchCanonicalLedger(7, "RODTEP");
        expect(mockedGet).toHaveBeenCalledWith("license-ledger/7/ledger_detail/?license_type=RODTEP");
    });

    it("omits the type only when none was supplied (legacy AUTO lookup)", async () => {
        await fetchCanonicalLedger(7);
        expect(mockedGet).toHaveBeenCalledWith("license-ledger/7/ledger_detail/");
    });

    it("encodes unsafe identifiers instead of injecting path segments", async () => {
        await fetchCanonicalLedger("LIC/../7", "DFIA");
        expect(mockedGet).toHaveBeenCalledWith("license-ledger/LIC%2F..%2F7/ledger_detail/?license_type=DFIA");
    });
});
