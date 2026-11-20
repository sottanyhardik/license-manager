import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate, useNavigationType } from "react-router-dom";
import type { NavigateFunction } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { useUrlFilters } from "./useUrlFilters";

const KEYS = ["status", "days"] as const;
const normalize = (raw: { status: string | null; days: string | null }) => ({
    status: raw.status === "expiring" ? "expiring" : "active",
    days: /^\d+$/.test(raw.days ?? "") ? String(raw.days) : "30",
});

let navigate: NavigateFunction = () => undefined;

function LocationProbe() {
    const location = useLocation();
    const navigationType = useNavigationType();
    navigate = useNavigate();
    return <output data-testid="location" data-action={navigationType}>{`${location.pathname}${location.search}`}</output>;
}

function Probe() {
    const [filters, setFilters] = useUrlFilters(KEYS, normalize);
    return (
        <>
            <output data-testid="values">{`${filters.status}|${filters.days}`}</output>
            <button type="button" onClick={() => setFilters({ status: "expiring" })}>expiring</button>
            <button type="button" onClick={() => setFilters({ days: "90" }, { replace: true })}>days</button>
        </>
    );
}

const setup = (entries: string[]) => render(
    <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
        <LocationProbe />
        <Routes>
            <Route path="/r" element={<Probe />} />
            <Route path="/other" element={<p>other</p>} />
        </Routes>
    </MemoryRouter>,
);
const params = () => new URLSearchParams(screen.getByTestId("location").textContent!.split("?")[1] ?? "");

describe("useUrlFilters", () => {
    it("writes the defaults into the URL with replace and keeps unrelated params", () => {
        setup(["/r?days=abc&keep=1"]);
        expect(screen.getByTestId("values")).toHaveTextContent("active|30");
        expect(params().get("status")).toBe("active");
        expect(params().get("days")).toBe("30");
        expect(params().get("keep")).toBe("1");
        expect(screen.getByTestId("location")).toHaveAttribute("data-action", "REPLACE");
    });

    it("reads existing params (refresh) and follows back/forward", () => {
        setup(["/r?status=active&days=45"]);
        expect(screen.getByTestId("values")).toHaveTextContent("active|45");
        act(() => screen.getByText("expiring").click());
        expect(screen.getByTestId("values")).toHaveTextContent("expiring|45");
        act(() => navigate(-1));
        expect(screen.getByTestId("values")).toHaveTextContent("active|45");
        act(() => navigate(1));
        expect(screen.getByTestId("values")).toHaveTextContent("expiring|45");
    });

    it("replace-mode updates do not create a back step", () => {
        setup(["/other", "/r?status=active&days=30"]);
        act(() => screen.getByText("days").click());
        expect(params().get("days")).toBe("90");
        act(() => navigate(-1));
        expect(screen.getByTestId("location")).toHaveTextContent("/other");
    });
});
