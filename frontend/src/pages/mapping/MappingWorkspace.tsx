/**
 * Mapping workspace (owner specs 2026-11-19) — three sources, each with its own saved mappings:
 *
 *   Licence Import Item: Original Item Description → Item Name(s)        (`LicenseImportItemsModel.items`)
 *   Allotment:           Item Name*                → Planning Target Item (`AllotmentModel.planning_target_item`)
 *   BOE:                 Product Name              → Planning Target Item (`BillOfEntryModel.planning_target_item`)
 *
 * Item Names and Planning Target Items are the same canonical master (`ItemNameModel`) that Item Pivot (Classic Mode)
 * groups by and Licence Planning consumes. Each unique source text is mapped once, applied to every existing record
 * with exactly that text and to future ones automatically; every write is validated on the server (SION rules / HSN)
 * and versioned for re-planning. Source texts, quantities, CIF and debit rows are never changed. A missing master
 * entry is created only through Masters → Item Names (the authorised master workflow).
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import { DetailTabs } from "@/components/workspace";

import DescriptionMapping from "./DescriptionMapping";
import MappingChanges from "./MappingChanges";
import { SOURCES } from "./mappingSources";

type Counts = Record<"import" | "boe" | "allotment", { records: number; descriptions: number }>;

export default function MappingWorkspace() {
    const [tab, setTab] = useState("import");
    const counts = useQuery({
        queryKey: ["item-name-mapping-counts"],
        queryFn: async ({ signal }) => (await api.get("item-pivot/matching/item-name-mapping/counts/", { signal })).data as Counts,
        staleTime: 30_000,
    });
    const n = (k: keyof Counts) => (counts.data ? ` (${counts.data[k].descriptions})` : "");
    return (
        <>
            <PageHeader title="Mapping" description="Map each original source text once — licence import descriptions to Item Names, BOE Product Names and Allotment Item Names to Planning Target Items (the same master Item Pivot and Licence Planning use). Source texts, quantities, CIF and debits are never changed." />
            <div className="space-y-3">
                <DetailTabs recordKey="mapping-workspace" value={tab} onValueChange={setTab} ariaLabel="Mapping sources"
                    tabs={[
                        { id: "import", label: `Licence Import Item${n("import")}`, render: () => <DescriptionMapping /> },
                        { id: "boe", label: `BOE${n("boe")}`, render: () => <DescriptionMapping key="boe" source={SOURCES.boe} /> },
                        { id: "allotment", label: `Allotment${n("allotment")}`, render: () => <DescriptionMapping key="allotment" source={SOURCES.allotment} /> },
                    ]} />
                <details className="rounded-lg border border-border/70 bg-card px-3 py-2 text-xs">
                    <summary className="cursor-pointer font-semibold">Mapping versions &amp; re-planning status</summary>
                    <div className="pt-2"><MappingChanges /></div>
                </details>
            </div>
        </>
    );
}
