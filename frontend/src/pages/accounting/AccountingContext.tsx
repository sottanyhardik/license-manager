import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { acctGet, acctKeys, type DiscoveredEntity, type EntityBooks } from "@/api/accountingApi";

const STORAGE_KEY = "accounting.workspace";

interface Selection {
    entityId: number | null;
    fy: string | null;
}

interface AccountingContextValue extends Selection {
    entities: EntityBooks[];
    discovered: DiscoveredEntity[];
    entity: EntityBooks | null;
    isLoading: boolean;
    setEntityId: (id: number | null) => void;
    setFy: (fy: string | null) => void;
    /** Common query params for entity-scoped report endpoints. */
    scope: { entity: number | undefined; fy: string | undefined };
    /** Date window of the selected FY for list endpoints (start/end filters). */
    fyRange: { start: string; end: string };
    refetchEntities: () => void;
}

const AccountingContext = createContext<AccountingContextValue | null>(null);

function readStored(): Selection {
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (raw) return { entityId: null, fy: null, ...JSON.parse(raw) };
    } catch {
        /* storage unavailable: fall back to defaults */
    }
    return { entityId: null, fy: null };
}

function store(sel: Selection): void {
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sel));
    } catch {
        /* ignore */
    }
}

export function fyDates(label: string): { start: string; end: string } {
    const y = Number(label.slice(0, 4));
    return { start: `${y}-04-01`, end: `${y + 1}-03-31` };
}

export function currentFyLabel(today = new Date()): string {
    const y = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
    return `${y}-${String(y + 1).slice(-2)}`;
}

export function AccountingProvider({ children }: { children: ReactNode }) {
    const [selection, setSelection] = useState<Selection>(readStored);
    const { data, isLoading, refetch } = useQuery({
        queryKey: [...acctKeys.all, "entities"],
        queryFn: () => acctGet<{ discovered: DiscoveredEntity[]; books: EntityBooks[] }>("entities/"),
    });
    const entities = useMemo(() => (data?.books ?? []).filter((b) => b.is_active), [data]);
    const entityId = entities.some((e) => e.id === selection.entityId) ? selection.entityId : entities[0]?.id ?? null;
    const entity = entities.find((e) => e.id === entityId) ?? null;
    const fy = selection.fy ?? currentFyLabel();

    const value = useMemo<AccountingContextValue>(() => ({
        entityId, fy, entities, discovered: data?.discovered ?? [], entity, isLoading,
        setEntityId: (id) => { const next = { ...selection, entityId: id }; store(next); setSelection(next); },
        setFy: (label) => { const next = { ...selection, fy: label }; store(next); setSelection(next); },
        scope: { entity: entityId ?? undefined, fy: fy ?? undefined },
        fyRange: fyDates(fy),
        refetchEntities: () => { void refetch(); },
    }), [entityId, fy, entities, data, entity, isLoading, refetch, selection]);

    return <AccountingContext.Provider value={value}>{children}</AccountingContext.Provider>;
}

export function useAccounting(): AccountingContextValue {
    const ctx = useContext(AccountingContext);
    if (!ctx) throw new Error("useAccounting must be used inside <AccountingProvider>");
    return ctx;
}
