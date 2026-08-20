import React, {useEffect, useState, useCallback, useRef, useLayoutEffect} from "react";
import {Link, useNavigate, useSearchParams} from "react-router-dom";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {formatIndianNumber} from "../../utils/numberFormatter";
import {toast} from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeftRight, Bell, Calculator, CalendarDays, FileSpreadsheet, FileText, Filter, Inbox, Info, Loader2, Package, RefreshCw, StickyNote, Tag, Target, TriangleAlert, XCircle } from "lucide-react";
import LicensePlanningPanel from "../../components/planning/LicensePlanningPanel";
import { PURCHASE_STATUS_PALETTE, PURCHASE_STATUS_UNKNOWN } from "../../theme/tokens";
import NormCardGrid from "./NormCardGrid";
import ItemPivotFilters from "./ItemPivotFilters";
import { openAuthedFile } from "../../utils/documentDownload";
import { usePurchaseStatusOptions } from "../../hooks/useMasterOptions";

// Default Purchase Status selection on first load — Global Exim, MITC,
// Conversion (matches the bulk License Balance report's default filter).
// Distinct, subtle background tints cycled per item so each item's column
// group (and its name header) is easy to tell apart at a glance.
const ITEM_BG_COLORS = [
    'rgba(59,130,246,0.10)',   // blue
    'rgba(16,185,129,0.10)',   // green
    'rgba(249,115,22,0.10)',   // orange
    'rgba(139,92,246,0.10)',   // purple
    'rgba(236,72,153,0.10)',   // pink
    'rgba(234,179,8,0.12)',    // amber
    'rgba(6,182,212,0.10)',    // cyan
    'rgba(107,114,128,0.10)',  // gray
];
const itemBgColor = (idx) => ITEM_BG_COLORS[idx % ITEM_BG_COLORS.length];

// Compact Scroll Mode — while a pivot table is scrolled horizontally away
// from its resting position, the mid-table columns (Exporter through
// Planned CIF) are removed from the rendered table entirely (not just
// styled to zero width — `table-layout: auto` doesn't reliably treat
// max-width as a hard clamp, so a CSS-only collapse can leave reserved
// space) so the frozen Sr No/DFIA No/Expiry Dt/Balance CIF columns and the
// per-item pivot columns sit directly adjacent, needing far less scrolling
// to compare items across a wide license. Reverses itself automatically
// since it's driven live off `scrollLeft` rather than any persisted state.
//
// The frozen columns' sticky `left` offsets are never hard-coded pixel
// guesses — DFIA No/Expiry Dt/Balance CIF's cells genuinely vary in width
// (e.g. the DFIA No cell carries a license-number link, a "Docs" button,
// and stacked status badges), so a fixed px offset drifts out of alignment
// with real content and either overlaps the next column or leaves a gap.
// Instead each group's Sr No/DFIA No/Expiry Dt header cells are measured
// via ref after layout (see `useFrozenColumnOffsets` below) and the
// cumulative real widths are used as the `left` values.
function useFrozenColumnOffsets(measureKeys: string[]) {
    const cellRefs = useRef<Record<string, { srNo?: HTMLElement | null; dfia?: HTMLElement | null; expiry?: HTMLElement | null }>>({});
    const [offsets, setOffsets] = useState<Record<string, { dfia: number; expiry: number; balance: number }>>({});

    const makeRef = useCallback((groupKey: string, col: 'srNo' | 'dfia' | 'expiry') => (el: HTMLElement | null) => {
        if (!cellRefs.current[groupKey]) cellRefs.current[groupKey] = {};
        cellRefs.current[groupKey][col] = el;
    }, []);

    const measure = useCallback(() => {
        setOffsets(prev => {
            let changed = false;
            const next = { ...prev };
            for (const groupKey of measureKeys) {
                const cells = cellRefs.current[groupKey];
                if (!cells?.srNo || !cells?.dfia || !cells?.expiry) continue;
                const srNoWidth = cells.srNo.getBoundingClientRect().width;
                const dfiaWidth = cells.dfia.getBoundingClientRect().width;
                const expiryWidth = cells.expiry.getBoundingClientRect().width;
                const dfia = srNoWidth;
                const expiry = srNoWidth + dfiaWidth;
                const balance = srNoWidth + dfiaWidth + expiryWidth;
                const prevForGroup = prev[groupKey];
                if (!prevForGroup || prevForGroup.dfia !== dfia || prevForGroup.expiry !== expiry || prevForGroup.balance !== balance) {
                    next[groupKey] = { dfia, expiry, balance };
                    changed = true;
                }
            }
            return changed ? next : prev;
        });
    }, [measureKeys]);

    useLayoutEffect(() => {
        measure();
    });

    useEffect(() => {
        window.addEventListener('resize', measure);
        return () => window.removeEventListener('resize', measure);
    }, [measure]);

    return { makeRef, offsets };
}

type ItemPivotPathOptions = {
    format: "json" | "excel";
    normClass?: unknown;
    selectedCompanies?: unknown[];
    excludeCompanies?: unknown[];
    minBalance?: unknown;
    licenseStatus?: unknown;
    expiryDateFrom?: unknown;
    expiryDateTo?: unknown;
    purchaseStatus?: unknown[];
};

export function toFiniteNumber(value: unknown, fallback = 0): number {
    const parsed = Number.parseFloat(String(value ?? ""));
    return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeFilterValues(values?: unknown[]): string[] {
    if (!Array.isArray(values)) {
        return [];
    }

    return values
        .map((value) => String(value ?? "").trim())
        .filter(Boolean);
}

export function buildItemPivotReportPath({
    format,
    normClass,
    selectedCompanies = [],
    excludeCompanies = [],
    minBalance = 200,
    licenseStatus = "active",
    expiryDateFrom,
    expiryDateTo,
    purchaseStatus = [],
}: ItemPivotPathOptions): string {
    const params = new URLSearchParams({
        format,
        days: "30",
    });
    const normClassValue = String(normClass ?? "").trim();
    const includeCompanyIds = normalizeFilterValues(selectedCompanies);
    const excludeCompanyIds = normalizeFilterValues(excludeCompanies);
    const purchaseStatuses = normalizeFilterValues(purchaseStatus);
    const expiryFrom = String(expiryDateFrom ?? "").trim();
    const expiryTo = String(expiryDateTo ?? "").trim();

    if (normClassValue) params.set("sion_norm", normClassValue);
    if (includeCompanyIds.length > 0) params.set("company_ids", includeCompanyIds.join(","));
    if (excludeCompanyIds.length > 0) params.set("exclude_company_ids", excludeCompanyIds.join(","));
    params.set("min_balance", String(toFiniteNumber(minBalance, 200)));
    params.set("license_status", String(licenseStatus || "active"));
    if (expiryFrom) params.set("expiry_date_from", expiryFrom);
    if (expiryTo) params.set("expiry_date_to", expiryTo);
    if (purchaseStatuses.length > 0) params.set("purchase_status", purchaseStatuses.join(","));

    return `reports/item-pivot/?${params.toString()}`;
}

// Shared style for the compact Condition / Transfer / Note action pills that
// sit next to each DFIA number. Soft tint + coloured text/border, icon inline.
const ACTION_PILL_BASE = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: 5,
    width: '100%',
    fontSize: 11,
    fontWeight: 600,
    lineHeight: 1.3,
    padding: '3px 8px',
    borderRadius: 6,
    whiteSpace: 'nowrap',
    cursor: 'pointer',
};

// Purchase-status badge palette now lives in theme/tokens.js (single source of truth).
const PURCHASE_STATUS_STYLES = PURCHASE_STATUS_PALETTE;
const UNKNOWN_PS_STYLE = PURCHASE_STATUS_UNKNOWN;

function PurchaseStatusBadge({ code, label }) {
    if (!code) return null;
    const s = PURCHASE_STATUS_STYLES[code] || UNKNOWN_PS_STYLE;
    return (
        <span
            title={label || code}
            style={{
                display: 'inline-block',
                backgroundColor: s.bg,
                color: s.color,
                fontWeight: 600,
                fontSize: 11,
                padding: '1px 6px',
                borderRadius: 'var(--tb-r-sm)',
                lineHeight: 1.4,
                whiteSpace: 'nowrap',
            }}
        >
            {s.short}
        </span>
    );
}

function pivotNumber(value: unknown, digits: number) {
    if (value == null || value === '') return '—';
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    // Backend positions are normalized; retain this final display guard so a
    // malformed response can never present a negative business balance.
    return Math.max(n, 0).toLocaleString('en-IN', {minimumFractionDigits: digits, maximumFractionDigits: digits});
}

/** A stale response must never turn serialized decimal zero into an issue. */
function isPositivePivotIssue(issue: any) {
    const type = String(issue?.type || '');
    const excess = type.includes('_cif_')
        ? (type.includes('over_planned') ? issue?.planned_excess_cif : issue?.actual_excess_cif)
        : (type.includes('over_planned') ? issue?.planned_excess_qty : issue?.actual_excess_qty);
    const value = Number(excess ?? 0);
    return Number.isFinite(value) && value > 0;
}

function PivotTotalCells({ group }: { group: any }) {
    return <>{group.item_groups.flatMap((item, itemIndex) => {
        const total = group.totals?.items?.[item.key];
        const bg = {backgroundColor: itemBgColor(itemIndex)};
        return ['hsn','description','total_qty','allotted_qty','debited_qty','balance_qty','restriction_percent','restriction_value','plan_qty','planned_cif'].map(key => {
            const text = ['hsn','description','restriction_percent'].includes(key) ? '—' : pivotNumber(total?.[key], key.includes('cif') || key.includes('value') ? 2 : 3);
            return <td key={`${item.key}-total-${key}`} className={cn('border p-2', ['total_qty','allotted_qty','debited_qty','balance_qty','restriction_value','plan_qty','planned_cif'].includes(key) && 'text-right')} style={bg}>{text}</td>;
        });
    })}</>;
}

function FioriSummary({ summary, groups, grandTotal, onException }: { summary: any; groups: any[]; grandTotal: any; onException: (item: any, group?: any) => void }) {
    // The backend owns the row order.  Prefixing the visible item label makes
    // that active SION-rule priority auditable without re-sorting in React.
    const withPriorityLabel = (group: any) => ({
        ...group,
        item_summary: (group?.item_summary || []).map((item: any) => ({
            ...item,
            item_name: item.planning_priority != null ? `${item.planning_priority} · ${item.item_name}` : item.item_name,
        })),
    });
    groups = groups.map(withPriorityLabel);
    grandTotal = withPriorityLabel(grandTotal);
    const cards = [
        ['Total Licences', summary?.license_count, 0, 'text-blue-700'], ['Total Licence CIF', summary?.total_cif, 2, 'text-blue-700'],
        ['Actual BOE CIF', summary?.actual_boe_cif, 2, 'text-amber-700'], ['Actual Allotment CIF', summary?.actual_allotment_cif, 2, 'text-amber-700'],
        ['Actual Balance CIF', summary?.actual_balance_cif, 2, 'text-green-700'], ['Effective Planned CIF', summary?.effective_planned_cif, 2, 'text-blue-700'],
        ['Final Balance CIF', summary?.final_balance_cif, 2, 'text-green-700'], ['Coverage %', summary?.planning_coverage_percent, 2, 'text-green-700'],
    ];
    const Section = ({ title, group, strong = false }: { title: string; group: any; strong?: boolean }) => <Card className={cn("mt-4 rounded-md shadow-none", strong && "border-2 border-primary")}><CardHeader className={cn("border-b py-3", strong ? "bg-primary text-primary-foreground" : "bg-muted/40")}><div><h2 className="text-base font-semibold">{title}</h2><p className="text-xs opacity-80">{group?.license_count ?? 0} Licences · canonical item and SION reconciliation</p></div></CardHeader><CardContent className="p-0"><div className="overflow-x-auto"><table className="min-w-full border-collapse text-xs"><thead className="sticky top-0 z-10 bg-muted"><tr><th rowSpan={2} className="border p-2 text-left">ITEM</th><th rowSpan={2} className="border p-2">SION</th><th rowSpan={2} className="border p-2">HSN CODES</th><th rowSpan={2} className="border p-2">LICENCES</th><th colSpan={7} className="border p-2 text-center">QUANTITY POSITION</th><th colSpan={5} className="border p-2 text-center">CIF POSITION</th><th rowSpan={2} className="border p-2">EXCEPTIONS</th><th rowSpan={2} className="border p-2">STATUS</th></tr><tr>{['TOTAL QTY','BOE QTY','ALLOTTED QTY','USED QTY','AVAILABLE QTY','PLANNED QTY','BALANCE QTY','USED CIF','AVAILABLE CIF','PLANNED CIF','BALANCE CIF','AVG PRICE'].map(name => <th key={name} className="border p-2 text-right whitespace-nowrap">{name}</th>)}</tr></thead><tbody>{(group?.item_summary || []).map((item: any) => <tr key={`${item.canonical_item_id}:${item.sion}`} className="hover:bg-muted/30"><td className="border p-2 font-semibold">{item.item_name}</td><td className="border p-2 text-center">{item.sion}</td><td className="border p-2">{item.hsn_codes?.join(', ') || '—'}</td><td className="border p-2 text-right">{item.license_count}</td>{['total_qty','boe_used_qty','allotted_qty','actual_used_qty','available_qty','planned_qty','balance_qty'].map(key => <td key={key} className="border p-2 text-right tabular-nums">{pivotNumber(item[key], 3)}</td>)}{['actual_used_cif','available_cif','planned_cif','balance_cif','average_unit_price'].map(key => <td key={key} className="border p-2 text-right tabular-nums">{(key === 'available_cif' || key === 'balance_cif') && item[key] == null ? '—' : pivotNumber(item[key], 2)}</td>)}<td className="border p-2 text-center">{item.exception_count || '—'}</td><td className="border p-2">{item.exception_count ? <button type="button" onClick={() => onException(item, group)}><Badge variant="destructive">{item.status}</Badge></button> : <Badge variant="secondary">{item.status}</Badge>}</td></tr>)}<tr className="bg-slate-200 font-bold"><td colSpan={4} className="border p-2">SUBTOTAL</td>{['total_qty','boe_used_qty','allotted_qty','actual_used_qty','available_qty','planned_qty','balance_qty'].map(key => <td key={key} className="border p-2 text-right">{pivotNumber(group?.item_summary_totals?.[key], 3)}</td>)}{['actual_used_cif','available_cif','planned_cif','balance_cif','weighted_average_unit_price'].map(key => <td key={key} className="border p-2 text-right">{pivotNumber(group?.item_summary_totals?.[key], 2)}</td>)}<td colSpan={2} className="border p-2" /></tr></tbody></table></div></CardContent></Card>;
    return <><div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">{cards.map(([label, value, digits, color]) => <Card key={String(label)} className="rounded-md shadow-none"><CardContent className="p-3"><div className="text-[11px] font-medium text-muted-foreground">{label}</div><div className={cn('mt-1 text-sm font-bold tabular-nums', color as string)}>{pivotNumber(value, digits as number)}</div></CardContent></Card>)}</div>{groups.map(group => <Section key={`${group.notification_number}:${group.purchase_status?.name}`} title={`Notification Number: ${group.notification_number} · ${group.purchase_status?.name || 'UNASSIGNED'}`} group={group} />)}<Section title="TOTAL SUMMARY — ALL NOTIFICATIONS" group={grandTotal} strong /></>;
}

/** Backend-owned canonical pivot DTO.  This component formats only. */
function CanonicalPivot({ groups, onCondition, onTransfer, onReplan, onIssue, selectedItem, exceptionOnly }: { groups: any[]; onCondition: (license: any) => void; onTransfer: (license: any) => void; onReplan: (license: any) => void; onIssue: (license: any) => void; selectedItem?: string | null; exceptionOnly?: boolean }) {
    const fixed = ['SR NO', 'DFIA NO', 'EXPIRY DT', 'EXPORTER', 'TOTAL CIF', 'DEBITED CIF', 'ALLOTTED CIF', 'PLANNED CIF', 'BALANCE CIF', 'ISSUES'];
    return <div className="space-y-5">
        {groups.map((group) => { const visibleLicenses = group.licenses.filter((license) => !exceptionOnly || license.issues?.some((issue) => !selectedItem || issue.item_key === selectedItem)); return visibleLicenses.length ? <Card key={`${group.notification_number}-${group.purchase_status?.id ?? group.purchase_status?.name}`}>
            <CardHeader className="flex-row items-center justify-between text-primary-foreground" style={{background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))'}}>
                <div><div className="flex items-center gap-2 font-semibold"><Bell className="size-4" /> Notification Number: {group.notification_number}<Badge variant="secondary">{group.purchase_status?.name || 'UNASSIGNED'}</Badge></div><div className="mt-1 text-xs opacity-90">{group.license_count} Licences</div></div>
                <span className="flex size-9 items-center justify-center rounded-full bg-white/20 font-bold">{group.license_count}</span>
            </CardHeader>
            <CardContent className="p-0"><div className="overflow-x-auto"><table className="w-max min-w-full border-collapse text-sm"><thead className="sticky top-0 z-20 bg-muted"><tr>{fixed.map((name, i) => <th key={name} rowSpan={2} className={cn('border p-2 text-left whitespace-nowrap', i < 2 && 'sticky z-30 bg-muted')} style={i === 0 ? {left: 0} : i === 1 ? {left: 58} : {}}>{name}</th>)}{group.item_groups.map((item, i) => <th id={`pivot-item-${item.key}`} key={item.key} colSpan={10} className={cn('border p-2 text-center font-bold', selectedItem === item.key && 'ring-2 ring-red-500')} style={{backgroundColor: itemBgColor(i)}}>{item.name} — {item.sion}</th>)}</tr><tr>{group.item_groups.flatMap((item, i) => ['HSN CODE','DESCRIPTION','TOTAL QTY','ALLOTTED QTY','DEBITED QTY','BALANCE QTY','RESTRICTION %','RESTRICTION VAL','PLAN QTY','PLANNED CIF'].map(name => <th key={`${item.key}-${name}`} className="border p-2 whitespace-nowrap" style={{backgroundColor: itemBgColor(i)}}>{name}</th>))}</tr></thead>
                <tbody>{visibleLicenses.map((license, index) => {
                    const pivotCells = group.item_groups.flatMap((item, itemIndex) => {
                        const cell = license.items?.[item.key];
                        const bg = {backgroundColor: itemBgColor(itemIndex)};
                        return ['hsn_code','description','total_qty','allotted_qty','debited_qty','balance_qty','restriction_percent','restriction_value','plan_qty','planned_cif'].map(key => {
                            const display = !cell ? '—' : (key === 'description' || key === 'hsn_code' ? (cell[key] || '—') : key === 'restriction_percent' && cell[key] != null ? <Badge>{cell[key]}%</Badge> : pivotNumber(cell[key], key.includes('cif') || key.includes('value') ? 2 : 3));
                            return <td key={`${item.key}-${key}`} className={cn('border p-2', ['total_qty','allotted_qty','debited_qty','balance_qty','restriction_value','plan_qty','planned_cif'].includes(key) && 'text-right', key === 'debited_qty' && 'text-orange-700', key === 'allotted_qty' && 'text-blue-700', key === 'balance_qty' && 'text-green-700')} style={bg}>{display}</td>;
                        });
                    });
                    return <tr key={license.license_id} className={cn('align-middle hover:bg-muted/40', license.issue_count && 'border-l-4 border-l-red-600')}><td className="sticky left-0 z-10 border bg-background p-2 text-right">{index + 1}</td><td className="dfia-sticky-cell sticky z-20 border bg-background p-2" style={{left: 58, pointerEvents: 'auto'}}><Link to={`/licenses/${license.license_id}/overview`} className="font-semibold text-primary underline hover:text-primary/80 focus-visible:outline focus-visible:outline-2">{license.license_number}</Link>{license.highest_issue && <Badge variant="destructive" className="ml-1 text-[10px]">{license.highest_issue.replace('_', ' ')}</Badge>}<div className="mt-1 flex flex-col gap-1 text-[11px]">{license.condition_available ? <button type="button" onClick={(event) => { event.stopPropagation(); onCondition(license); }} style={{...ACTION_PILL_BASE, color: '#92610a', backgroundColor: 'rgba(234,179,8,0.13)', border: '1px solid rgba(234,179,8,0.45)'}}><FileText className="size-3.5" />Condition</button> : <button type="button" disabled title="No condition sheet is available" style={{...ACTION_PILL_BASE, opacity: .5}}>Condition</button>}{license.transfer_available ? <button type="button" onClick={(event) => { event.stopPropagation(); onTransfer(license); }} style={{...ACTION_PILL_BASE, color: '#1d4ed8', backgroundColor: 'rgba(59,130,246,0.13)', border: '1px solid rgba(59,130,246,0.45)'}}><ArrowLeftRight className="size-3.5" />Transfer</button> : <button type="button" disabled title="No transfer status is available" style={{...ACTION_PILL_BASE, opacity: .5}}>Transfer</button>}<button type="button" onClick={(event) => { event.stopPropagation(); onReplan(license); }} style={{...ACTION_PILL_BASE, color: 'var(--tb-brand-active)', backgroundColor: 'var(--tb-brand-50)', border: '1px solid #a5b4fc'}}><Target className="size-3.5" />Re Plan me</button></div></td><td className="border p-2 whitespace-nowrap">{license.expiry_date || '—'}</td><td className="border p-2 min-w-48 whitespace-normal">{license.exporter || '—'}</td>{['total_cif','debited_cif','allotted_cif','planned_cif','balance_cif'].map(key => <td key={key} className={cn('border p-2 text-right whitespace-nowrap', key === 'debited_cif' && 'text-orange-700', key === 'allotted_cif' && 'text-blue-700', key === 'balance_cif' && 'text-green-700')}>{pivotNumber(license[key], 2)}</td>)}<td className="border p-2 text-center">{license.issue_count ? <button type="button" onClick={() => onIssue(license)}><Badge variant="destructive">{license.issue_count} Issues</Badge></button> : <Badge variant="secondary" className="text-green-700">OK</Badge>}</td>{pivotCells}</tr>;
                })}<tr className="border-t-4 border-double border-slate-400 bg-slate-200 font-bold"><td className="sticky left-0 z-10 border bg-slate-200 p-2 text-right" colSpan={2}>TOTAL — {group.license_count} LICENCES</td><td className="border bg-slate-200 p-2">—</td><td className="border bg-slate-200 p-2">—</td>{['total_cif','debited_cif','allotted_cif','planned_cif','balance_cif'].map(key => <td key={key} className="border bg-slate-200 p-2 text-right whitespace-nowrap">{pivotNumber(group.totals?.[key], 2)}</td>)}<td className="border bg-slate-200 p-2">{group.issue_license_count || 'OK'}</td><PivotTotalCells group={group} /></tr></tbody></table></div></CardContent>
        </Card> : null})}
    </div>;
}

export default function ItemPivotReport() {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
    const [reportView, setReportView] = useState<'summary' | 'matrix'>(searchParams.get('view') === 'license-matrix' ? 'matrix' : 'summary');
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [filtersCollapsed, setFiltersCollapsed] = useState(false);
    const [activeNormTab, setActiveNormTab] = useState(null);
    const [availableNorms, setAvailableNorms] = useState([]);
    const [minBalance, setMinBalance] = useState(200);
    const [licenseStatus, setLicenseStatus] = useState('active');
    const [expiryDateFrom, setExpiryDateFrom] = useState('');
    const [expiryDateTo, setExpiryDateTo] = useState('');
    // Purchase Status filter — options AND the default selection both come
    // from the Purchase Status master's `is_active` rows (never hardcoded —
    // see useMasterOptions.ts), applied once as soon as the master data
    // loads (matches the same one-time-default pattern the Item Report page
    // uses for its own Purchase Status filter).
    const { options: purchaseStatusOptions } = usePurchaseStatusOptions();
    const [purchaseStatus, setPurchaseStatus] = useState<string[]>([]);
    const purchaseStatusDefaultApplied = useRef(false);
    useEffect(() => {
        if (!purchaseStatusDefaultApplied.current && purchaseStatusOptions.length > 0) {
            purchaseStatusDefaultApplied.current = true;
            setPurchaseStatus(purchaseStatusOptions.map(o => o.value));
        }
    }, [purchaseStatusOptions]);
    const [conditionModal, setConditionModal] = useState(null); // { licenseNumber, content }
    const [transferModal, setTransferModal] = useState(null); // { licenseNumber, content }
    const [issueModal, setIssueModal] = useState(null);
    const [noteModal, setNoteModal] = useState(null); // { licenseNumber, content }
    // Utilization planning panel (same component the licenses page uses).
    const [showPlanModal, setShowPlanModal] = useState(false);
    const [planLicense, setPlanLicense] = useState(null); // { id, number, balance }

    // AbortController ref — cancels the previous in-flight loadReport request
    // when a new one starts, preventing stale responses from overwriting fresh data.
    const reportAbortRef = useRef<AbortController | null>(null);

    // Compact Scroll Mode — one flag per notification-group table (each group
    // renders its own independently-scrollable pivot table), keyed by that
    // group's key. Derived live from each table's scrollLeft — never written
    // anywhere else, so it always reflects the table's actual scroll position
    // and needs no reset/cleanup of its own.
    const [compactScrollGroups, setCompactScrollGroups] = useState<Record<string, boolean>>({});
    const handlePivotTableScroll = useCallback((groupKey: string) => (e: React.UIEvent<HTMLDivElement>) => {
        const isScrolled = e.currentTarget.scrollLeft > 0;
        setCompactScrollGroups(prev => (prev[groupKey] === isScrolled ? prev : {...prev, [groupKey]: isScrolled}));
    }, []);
    const pivotGroupKeys = Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {});
    const { makeRef: makeFrozenColRef, offsets: frozenColOffsets } = useFrozenColumnOffsets(pivotGroupKeys);

    useEffect(() => {
        loadAvailableNorms();
    }, []);

    // Reload available norms when filters change (but not on initial mount)
    useEffect(() => {
        // Skip first render (already loaded above)
        if (minBalance !== 200 || licenseStatus !== 'active') {
            loadAvailableNorms();
        }
    }, [minBalance, licenseStatus]);

    const loadAvailableNorms = async () => {
        try {
            // Fetch only the list of norm classes (lightweight endpoint)
            let url = `item-pivot/available-norms/`;
            const response = await api.get(url);

            const norms = response.data || [];
            // Response is now array of {norm_class, description} objects
            setAvailableNorms(Array.isArray(norms) ? norms : []);

            // Don't automatically set first norm as active - wait for user click
        } catch (error) {
            setAvailableNorms([]);
        }
    };

    const loadReport = useCallback(async (normClass) => {
        if (!normClass) return;

        // Cancel any in-flight request for this report — prevents the classic
        // "stale response overwrites fresh data" race condition where a slow
        // first request resolves after a faster second one and resets the table.
        if (reportAbortRef.current) {
            reportAbortRef.current.abort();
        }
        const controller = new AbortController();
        reportAbortRef.current = controller;

        setLoading(true);
        try {
            const response = await api.get(buildItemPivotReportPath({
                format: "json",
                normClass,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                licenseStatus,
                expiryDateFrom,
                expiryDateTo,
                purchaseStatus,
            }), { signal: controller.signal });

            // Only commit state if this request was not superseded
            if (!controller.signal.aborted) {
                setReportData(response.data);
            }
        } catch (error) {
            // Axios names aborted requests 'CanceledError'; ignore them silently
            if (
                error?.name === 'CanceledError' ||
                error?.code === 'ERR_CANCELED' ||
                controller.signal.aborted
            ) {
                return;
            }
            toast.error(error?.response?.data?.error || 'Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            if (!controller.signal.aborted) {
                setLoading(false);
            }
        }
    }, [selectedCompanies, excludeCompanies, minBalance, licenseStatus, expiryDateFrom, expiryDateTo, purchaseStatus]);

    // Load report when active norm tab changes or filters change
    useEffect(() => {
        if (activeNormTab) {
            loadReport(activeNormTab);
        }
    }, [activeNormTab, loadReport]);

    const handleUpdateBalance = async () => {
        const statusText = licenseStatus === 'active' ? 'active' : licenseStatus === 'inactive' ? 'inactive' : 'all';

        try {
            // Trigger the update task with current license status filter (no confirmation, runs in background)
            const response = await api.post('item-pivot/update-balance/', {
                license_status: licenseStatus
            });
            const taskId = response.data.task_id;
            if (!taskId) {
                toast.error('Balance update did not return a task id.');
                return;
            }

            // Show immediate toast notification
            toast.info(`Balance update started for ${statusText} licenses. You'll be notified when complete.`, {
                duration: 5000
            });

            // Start polling for status in background
            pollUpdateStatus(taskId);
        } catch (error) {
            toast.error('Failed to start balance update. Please try again.');
        }
    };

    const pollUpdateStatus = async (taskId) => {
        try {
            const response = await api.get(`item-pivot/task-status/${taskId}/`);
            const { state, result } = response.data;

            if (state === 'SUCCESS') {
                // Show success notification
                const updatedCount = toFiniteNumber(result?.updated, 0);
                const elapsedSeconds = toFiniteNumber(result?.elapsed_seconds, 0);
                toast.success(
                    `Balance update completed! Updated ${updatedCount} licenses in ${elapsedSeconds.toFixed(1)}s`,
                    { duration: 6000 }
                );

                // Reload the report if a norm is active
                if (activeNormTab) {
                    loadReport(activeNormTab);
                }
            } else if (state === 'FAILURE') {
                toast.error('Balance update failed. Please try again.');
            } else {
                // Continue polling every 2 seconds
                setTimeout(() => pollUpdateStatus(taskId), 2000);
            }
        } catch (error) {
            // Silently fail polling errors (task might still be running)
            console.error('Polling error:', error);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            await openAuthedFile(buildItemPivotReportPath({
                format: "excel",
                normClass: activeNormTab,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                licenseStatus,
                expiryDateFrom,
                expiryDateTo,
                purchaseStatus,
            }), "item_pivot_report.xlsx");
        } catch (error) {
            toast.error(error?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleCanonicalReplan = (license) => {
        // Reuse the established planning panel: it owns the corrected Auto
        // Plan mutation, loading state, cache refresh, and error handling.
        setPlanLicense({ id: license.license_id, number: license.license_number, balance: Number(license.balance_cif || 0) });
        setShowPlanModal(true);
    };
    const handleCanonicalCondition = (license) => setConditionModal({ licenseNumber: license.license_number, content: license.condition_sheet });
    const handleCanonicalTransfer = (license) => setTransferModal({ licenseNumber: license.license_number, content: license.latest_transfer });
    const handleCanonicalIssue = (license) => setIssueModal({
        ...license,
        issues: (license.issues || []).filter(isPositivePivotIssue),
    });
    const handleSummaryException = (item, group) => {
        setReportView('matrix');
        setSearchParams((current) => {
            const next = new URLSearchParams(current);
            next.set('view', 'license-matrix'); next.set('item', `${item.canonical_item_id}:${item.sion}`); next.set('exception', item.status); next.set('exceptions_only', '1');
            if (group?.notification_number) next.set('notification', group.notification_number);
            return next;
        });
    };
    const clearExceptionFilter = () => setSearchParams((current) => { const next = new URLSearchParams(current); ['item', 'exception', 'exceptions_only'].forEach(key => next.delete(key)); return next; });
    useEffect(() => {
        if (reportView === 'matrix' && searchParams.get('item')) document.getElementById(`pivot-item-${searchParams.get('item')}`)?.scrollIntoView({behavior: 'smooth', block: 'nearest', inline: 'center'});
    }, [reportView, searchParams]);

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handleClearFilters = () => {
        setSelectedCompanies([]);
        setExcludeCompanies([]);
        setMinBalance(200);
        setLicenseStatus('active');
        setExpiryDateFrom('');
        setExpiryDateTo('');
        // Back to the master's active-status default, not a hardcoded list.
        setPurchaseStatus(purchaseStatusOptions.map(o => o.value));
    };

    // Purchase Status is "active" only when it differs from the master's
    // full active-status default (order-independent).
    const isDefaultPurchaseStatus =
        purchaseStatus.length === purchaseStatusOptions.length &&
        purchaseStatusOptions.every(o => purchaseStatus.includes(o.value));
    const hasActiveFilters = selectedCompanies.length > 0 || excludeCompanies.length > 0 || minBalance !== 200 || licenseStatus !== 'active' || expiryDateFrom || expiryDateTo || !isDefaultPurchaseStatus;

    const getTotalLicenseCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            Object.values(notifications).forEach(licenses => {
                total += licenses.length;
            });
        });
        return total;
    };

    const getTotalNotificationCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            total += Object.keys(notifications).length;
        });
        return total;
    };

    return (
        <div className="min-h-screen bg-background">
            {/* Tabler-style page header */}
            <div className="page-header">
                <div className="min-w-0">
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        Reports
                        <span className="mx-1.5 opacity-50">/</span>
                        Item Pivot Report
                    </div>
                    <h1>Item Pivot Report</h1>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        {reportData && (
                            <span className="inline-flex items-center gap-1">
                                <CalendarDays className="size-3.5" aria-hidden="true" />
                                {reportData.report_date}
                            </span>
                        )}
                        <span className="inline-flex items-center gap-1">
                            <Tag className="size-3.5" aria-hidden="true" />
                            Active Norm:
                            <span className="font-semibold text-foreground">{activeNormTab || 'None'}</span>
                        </span>
                        {reportData && (
                            <>
                                <span className="inline-flex items-center gap-1">
                                    <Bell className="size-3.5" aria-hidden="true" />
                                    {getTotalNotificationCount()} Notifications
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <FileText className="size-3.5" aria-hidden="true" />
                                    {getTotalLicenseCount()} Licenses
                                </span>
                            </>
                        )}
                    </div>
                </div>
                <div className="page-actions">
                    <Button variant="ghost" size="sm" onClick={() => setFiltersCollapsed(!filtersCollapsed)}>
                        <Filter className="size-4" />
                        {filtersCollapsed ? 'Show' : 'Hide'} Filters
                        {hasActiveFilters && <Badge className="ml-1">Active</Badge>}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleUpdateBalance}
                        title="Update balance_cif, is_active, is_expired, and restrictions. Runs in background."
                    >
                        <RefreshCw className="size-3.5" />
                        Update Balance
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExport} disabled={downloading}>
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                        {downloading ? 'Generating…' : 'Excel'}
                    </Button>
                </div>
            </div>

            {/* Filters Section */}
            {!filtersCollapsed && (
                <ItemPivotFilters
                    minBalance={minBalance} setMinBalance={setMinBalance}
                    licenseStatus={licenseStatus} setLicenseStatus={setLicenseStatus}
                    purchaseStatus={purchaseStatus} setPurchaseStatus={setPurchaseStatus}
                    purchaseStatusOptions={purchaseStatusOptions}
                    expiryDateFrom={expiryDateFrom} setExpiryDateFrom={setExpiryDateFrom}
                    expiryDateTo={expiryDateTo} setExpiryDateTo={setExpiryDateTo}
                    selectedCompanies={selectedCompanies} handleCompanyChange={handleCompanyChange}
                    excludeCompanies={excludeCompanies} handleExcludeCompanyChange={handleExcludeCompanyChange}
                    hasActiveFilters={hasActiveFilters} handleClearFilters={handleClearFilters}
                    isDefaultPurchaseStatus={isDefaultPurchaseStatus}
                />
            )}

            {/* Norm Tabs — redesigned */}
            <NormCardGrid
                availableNorms={availableNorms}
                activeNormTab={activeNormTab}
                setActiveNormTab={setActiveNormTab}
                setReportData={setReportData}
                loading={loading}
            />

            {/* Report Tables - Only show active norm */}
            <div>
                    {/* Empty state: norms exist but none selected */}
                    {!activeNormTab && !loading && availableNorms.length > 0 && (
                        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border py-16 text-center">
                            <div className="flex size-16 items-center justify-center rounded-2xl bg-primary/10">
                                <Tag className="size-8 text-primary" />
                            </div>
                            <div>
                                <p className="text-base font-bold text-foreground">Select a Norm to View Report</p>
                                <p className="mt-1 text-[12.5px] text-muted-foreground">Click any norm card above to load license data for that SION norm class</p>
                            </div>
                            {availableNorms.length > 0 && (
                                <div className="flex flex-wrap justify-center gap-1.5 mt-1">
                                    {availableNorms.slice(0, 5).map((n) => (
                                        <button key={n.norm_class || n} type="button"
                                            onClick={() => { setReportData(null); setActiveNormTab(n.norm_class || n); }}
                                            className="rounded-lg px-3 py-1 text-xs font-bold transition-colors hover:opacity-90"
                                            style={{ background: ['E1','E5','E126','E132'].includes(n.norm_class || n) ? 'var(--tb-success-soft)' : 'var(--tb-brand-50)', color: ['E1','E5','E126','E132'].includes(n.norm_class || n) ? 'var(--tb-success-text)' : 'var(--tb-brand)', border: '1px solid' }}>
                                            {n.norm_class || n}
                                        </button>
                                    ))}
                                    {availableNorms.length > 5 && <span className="self-center text-[11px] text-muted-foreground">+{availableNorms.length - 5} more</span>}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Loading state */}
                    {loading && activeNormTab && (
                        <div className="mb-4 flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card py-14 text-center shadow-sm">
                            <div className="flex size-14 items-center justify-center rounded-full bg-primary/10">
                                <Loader2 className="size-7 animate-spin text-primary" />
                            </div>
                            <div>
                                <p className="font-semibold text-foreground">Loading {activeNormTab} Report…</p>
                                <p className="mt-0.5 text-[12.5px] text-muted-foreground">Fetching license data for this norm</p>
                            </div>
                        </div>
                    )}

                    {/* No data message after loading */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification && (!reportData?.licenses_by_norm_notification?.[activeNormTab] || Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length === 0) && (
                        <div className="mb-4 flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card py-12 text-center shadow-sm">
                            <Inbox className="size-10 opacity-20" aria-hidden="true" />
                            <div>
                                <p className="font-semibold text-foreground">No licenses found for <span className="text-primary">{activeNormTab}</span></p>
                                <p className="mt-0.5 text-[12.5px] text-muted-foreground">Try adjusting your filters — e.g. increase minimum balance or change purchase status.</p>
                            </div>
                            {hasActiveFilters && (
                                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                                    <XCircle className="size-4" />
                                    Clear Filters
                                </Button>
                            )}
                        </div>
                    )}

                    {!loading && activeNormTab && Array.isArray(reportData?.groups) && (
                        reportData.groups.length ? <><div className="mb-3 flex gap-1 border-b"><Button variant={reportView === 'summary' ? 'default' : 'ghost'} size="sm" onClick={() => setReportView('summary')}>Item Summary</Button><Button variant={reportView === 'matrix' ? 'default' : 'ghost'} size="sm" onClick={() => setReportView('matrix')}>Licence Matrix</Button>{searchParams.get('exceptions_only') && <Button variant="outline" size="sm" onClick={clearExceptionFilter}>Clear Exception Filter</Button>}</div>{reportView === 'summary' ? <FioriSummary summary={reportData.global_summary || reportData.summary} groups={reportData.notification_groups || reportData.groups} grandTotal={reportData.grand_total} onException={handleSummaryException} /> : <CanonicalPivot groups={reportData.groups} onCondition={handleCanonicalCondition} onTransfer={handleCanonicalTransfer} onReplan={handleCanonicalReplan} onIssue={handleCanonicalIssue} selectedItem={searchParams.get('item')} exceptionOnly={searchParams.get('exceptions_only') === '1'} />}</> : (
                            <div className="rounded-xl border border-border bg-card py-12 text-center text-muted-foreground">No licences match the selected filters.</div>
                        )
                    )}

                    {/* Show report data */}
                    {!loading && activeNormTab && !Array.isArray(reportData?.groups) && reportData?.licenses_by_norm_notification?.[activeNormTab] && Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length > 0 && (
                        <div>
                            {/* Notifications within active norm */}
                            {(Object.entries(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}) as [string, any][]).sort().map(([groupKey, licenses]: [string, any]) => {
                                // Backend-computed grand totals for this (norm, notification)
                                // group — the footer TOTAL row reads these directly instead of
                                // reducing `licenses` itself (Phase 2B.2A; see
                                // docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md).
                                const groupTotals = reportData?.notification_totals?.[activeNormTab]?.[groupKey] || {};
                                // Group key is "<Purchase Status> — <notification>" (see backend).
                                // Split it so the table header shows purchase status as a chip
                                // and the notification on its own.
                                const emIdx = groupKey.indexOf(' — ');
                                const psLabel = emIdx >= 0 ? groupKey.slice(0, emIdx) : (licenses[0]?.purchase_status_label || '');
                                const notification = emIdx >= 0 ? groupKey.slice(emIdx + 3) : groupKey;
                                // Per-group item filter: only render columns for items that have
                                // actual data (import qty, balance, or plan) in THIS notification
                                // group. Using the global reportData.items list would cause every
                                // possible E1/E5 item to appear as an empty column even when no
                                // license in this group planned or imported it.
                                const groupItems = (reportData.items as any[]).filter((item: any) => {
                                    if (!item.name) return false;
                                    return (licenses as any[]).some((license: any) => {
                                        const d = license.items?.[item.name] || {};
                                        return (
                                            (d.quantity ?? 0) > 0 ||
                                            (d.available_quantity ?? 0) > 0 ||
                                            (d.plan_quantity ?? 0) > 0 ||
                                            (d.plan_cif ?? 0) > 0
                                        );
                                    });
                                });
                                const isCompact = !!compactScrollGroups[groupKey];
                                // Fallback offsets (used only for the very first paint, before
                                // the ref-measured real widths land) — approximate, never relied
                                // on once `useFrozenColumnOffsets` has measured actual layout.
                                const frozenOffsets = frozenColOffsets[groupKey] || {dfia: 60, expiry: 210, balance: 310};
                                const dfiaLeft = `${frozenOffsets.dfia}px`;
                                const expiryLeft = `${frozenOffsets.expiry}px`;
                                const balanceLeft = `${frozenOffsets.balance}px`;
                                return (
                                <div key={`${activeNormTab}-${groupKey}`} className="mb-4">
                                    <Card>
                                        <CardHeader
                                            className="flex-row items-center justify-between gap-4 text-primary-foreground"
                                            style={{background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))'}}>
                                            <div>
                                                <h5 className="mb-0 flex items-center gap-2 font-semibold">
                                                    <Bell className="size-4" aria-hidden="true" />
                                                    Notification Number: {notification}
                                                    {notification === 'Unknown' && (
                                                        <span className="chip chip-warning ml-2"
                                                              title="Notification number is blank or missing">
                                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                                            Missing
                                                        </span>
                                                    )}
                                                    {psLabel && (
                                                        <span className="chip chip-info ml-2" title="Purchase status">
                                                            {psLabel}
                                                        </span>
                                                    )}
                                                </h5>
                                                <small className="opacity-75">
                                                    {licenses.length} License{licenses.length !== 1 ? 's' : ''}
                                                </small>
                                            </div>
                                            <span className="chip chip-neutral">{licenses.length}</span>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div className="overflow-x-auto" onScroll={handlePivotTableScroll(groupKey)} data-testid="pivot-scroll-container">
                                                <table className="table table-hover table-sm table-bordered mb-0"
                                                       style={{tableLayout: 'auto', minWidth: '960px'}}>
                                                    <thead style={{position: 'sticky', top: 0, zIndex: 10}}>
                                                    <tr className="table-light">
                                                        <th ref={makeFrozenColRef(groupKey, 'srNo')} scope="col" className="text-center" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '60px'
                                                        }}>Sr No
                                                        </th>
                                                        <th ref={makeFrozenColRef(groupKey, 'dfia')} scope="col" style={{
                                                            position: 'sticky',
                                                            left: dfiaLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '120px'
                                                        }}>DFIA No
                                                        </th>
                                                        <th ref={makeFrozenColRef(groupKey, 'expiry')} scope="col" style={{
                                                            position: 'sticky',
                                                            left: expiryLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Expiry Dt
                                                        </th>
                                                        {!isCompact && (<>
                                                        <th scope="col" style={{minWidth: '150px'}}>Exporter
                                                        </th>
                                                        <th scope="col" className="text-right" style={{minWidth: '100px'}}>Total CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{minWidth: '100px'}}>Debited CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{minWidth: '100px'}}>Alloted CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{minWidth: '100px'}}>Remaining CIF
                                                        </th>
                                                        </>)}
                                                        <th scope="col" className="text-right" style={{
                                                            position: 'sticky',
                                                            left: balanceLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '110px',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>Balance CIF
                                                        </th>
                                                        {/* DFIA Dt / Notif No temporarily hidden
                                                        <th style={{ minWidth: '100px' }}>DFIA Dt</th>
                                                        <th style={{ minWidth: '120px' }}>Notif No</th>
                                                        */}
                                                        {groupItems.map((item, itemIdx) => {
                                                            // Sub-cols per item: HSN, Description, Total, Allotted,
                                                            // Debited, Balance, Plan Qty, Plan CIF
                                                            // + 2 optional restriction cols when applicable
                                                            // + 1 optional RUTILE-specific Unit Price.
                                                            const isRutile = item.name === 'RUTILE - A3627';
                                                            const colSpan = 8
                                                                + (item.has_restriction ? 2 : 0)
                                                                + (isRutile ? 1 : 0);
                                                            return (
                                                                <th scope="col" key={`${item.id}-qty`} colSpan={colSpan}
                                                                    className="text-center"
                                                                    style={{minWidth: '200px', backgroundColor: itemBgColor(itemIdx)}}>
                                                                    <Package className="size-4" aria-hidden="true" />
                                                                    {item.name}
                                                                </th>
                                                            );
                                                        })}
                                                    </tr>
                                                    <tr className="table-secondary">
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: dfiaLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: expiryLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        {!isCompact && (<>
                                                        <th scope="col" style={{backgroundColor: 'var(--tb-border)'}}></th>
                                                        <th scope="col" style={{backgroundColor: 'var(--tb-border)'}}></th>
                                                        <th scope="col" style={{backgroundColor: 'var(--tb-border)'}}></th>
                                                        <th scope="col" style={{backgroundColor: 'var(--tb-border)'}}></th>
                                                        <th scope="col" style={{backgroundColor: 'var(--tb-border)'}}></th>
                                                        </>)}
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: balanceLeft,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}></th>
                                                        {/* DFIA Dt / Notif No spacers temporarily hidden */}
                                                        {groupItems.map(item => (
                                                            <React.Fragment key={`${item.id}-headers`}>
                                                                <th scope="col" style={{minWidth: '90px', fontSize: 13.5}}>HSN
                                                                    Code
                                                                </th>
                                                                <th scope="col" style={{
                                                                    minWidth: '150px',
                                                                    fontSize: 13.5
                                                                }}>Description
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '90px',
                                                                    fontSize: 13.5
                                                                }}>Total QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Allotted QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Debited QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '110px',
                                                                    fontSize: 13.5
                                                                }}>Balance QTY
                                                                </th>
                                                                {item.has_restriction && (
                                                                    <>
                                                                        <th scope="col" className="text-center" style={{
                                                                            minWidth: '90px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction %
                                                                        </th>
                                                                        <th scope="col" className="text-right" style={{
                                                                            minWidth: '120px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction Val
                                                                        </th>
                                                                    </>
                                                                )}
                                                                {/* Manual plan when present, else norm unit price / planned CIF */}
                                                                <th scope="col" className="text-right" style={{ minWidth: '110px', fontSize: 13.5 }}>Plan Qty</th>
                                                                <th scope="col" className="text-right" style={{ minWidth: '110px', fontSize: 13.5 }}>Remaining CIF</th>
                                                                {item.name === 'RUTILE - A3627' && (
                                                                    <th scope="col" className="text-right" style={{
                                                                        minWidth: '100px',
                                                                        fontSize: 13.5
                                                                    }}>Unit Price (RUTILE)
                                                                    </th>
                                                                )}
                                                            </React.Fragment>
                                                        ))}
                                                    </tr>
                                                    </thead>
                                                    <tbody>
                                                    {licenses.map((license, idx) => (
                                                        <React.Fragment key={license.license_number}>
                                                        <tr className="align-middle">
                                                            <td className="text-center font-bold" style={{
                                                                position: 'sticky',
                                                                left: 0,
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{idx + 1}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: dfiaLeft,
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>
                                                                <div className="flex items-center gap-2" style={{ flexWrap: 'nowrap' }}>
                                                                    <div>
                                                                        {(license.has_tl || license.has_copy) ? (
                                                                            <a
                                                                                href="#"
                                                                                title="Open DFIA documents in a new tab"
                                                                                onClick={async (e) => {
                                                                                    e.preventDefault();
                                                                                    e.stopPropagation();
                                                                                    try {
                                                                                        await openAuthedFile(`licenses/${license.id}/merged-documents/`);
                                                                                    } catch {
                                                                                        toast.error('Failed to open DFIA documents');
                                                                                    }
                                                                                }}
                                                                                className="cursor-pointer whitespace-nowrap font-semibold text-primary underline"
                                                                            >
                                                                                {license.license_number}
                                                                            </a>
                                                                        ) : (
                                                                            <span className="font-semibold">{license.license_number}</span>
                                                                        )}
                                                                        <div className="mt-1">
                                                                            <PurchaseStatusBadge
                                                                                code={license.purchase_status_code}
                                                                                label={license.purchase_status_label}
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                    {/* Condition / Transfer / Note — one vertical, centered column of
                                                                        buttons that open their content in a modal (saves row width). */}
                                                                    {(
                                                                        <div className="flex flex-col items-stretch justify-center gap-1" style={{ minWidth: 96 }}>
                                                                            {license.condition_sheet && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View condition sheet"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setConditionModal({ licenseNumber: license.license_number, content: license.condition_sheet }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#92610a', backgroundColor: 'rgba(234,179,8,0.13)', border: '1px solid rgba(234,179,8,0.45)' }}
                                                                                >
                                                                                    <FileText className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Condition
                                                                                </button>
                                                                            )}
                                                                            {license.latest_transfer && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View transfer status"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setTransferModal({ licenseNumber: license.license_number, content: license.latest_transfer }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#1d4ed8', backgroundColor: 'rgba(59,130,246,0.13)', border: '1px solid rgba(59,130,246,0.45)' }}
                                                                                >
                                                                                    <ArrowLeftRight className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Transfer
                                                                                </button>
                                                                            )}
                                                                            {license.balance_report_notes && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View notes"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setNoteModal({ licenseNumber: license.license_number, content: license.balance_report_notes }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#b91c1c', backgroundColor: 'rgba(239,68,68,0.13)', border: '1px solid rgba(239,68,68,0.45)' }}
                                                                                >
                                                                                    <StickyNote className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Note
                                                                                </button>
                                                                            )}
                                                                            <button
                                                                                type="button"
                                                                                title={license.plan_source === 'manual' ? 'Re-plan utilization (already planned)' : 'Plan utilization'}
                                                                                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setPlanLicense({ id: license.id, number: license.license_number, balance: Number(license.balance_cif || 0) }); setShowPlanModal(true); }}
                                                                                style={{ ...ACTION_PILL_BASE, color: 'var(--tb-brand-active)', backgroundColor: 'var(--tb-brand-50)', border: '1px solid #a5b4fc' }}
                                                                            >
                                                                                <Target className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                {license.plan_source === 'manual' ? 'Re Plan me' : 'Plan me'}
                                                                            </button>
                                                                        </div>)}
                                                                </div>
                                                            </td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: expiryLeft,
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{formatDate(license.license_expiry_date)}</td>
                                                            {!isCompact && (<>
                                                            <td className="text-truncate" style={{maxWidth: '150px'}} title={license.exporter}>
                                                                {license.exporter}
                                                            </td>
                                                            <td className="text-right font-semibold">{license.total_cif.toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-warning">{(license.debited_cif || 0).toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-info">{(license.alloted_cif || 0).toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-secondary">
                                                                {/* Planned CIF for this license — backend-computed sum of
                                                                    every item column's own effective planned CIF (manual
                                                                    plan when the product was manually planned, else
                                                                    norm-derived). See `total_effective_planned_cif` in
                                                                    item_pivot_report.py's `_build_license_row`. */}
                                                                {(license.total_effective_planned_cif || 0).toFixed(2)}
                                                            </td>
                                                            </>)}
                                                            <td className="text-right font-semibold text-success" style={{
                                                                position: 'sticky',
                                                                left: balanceLeft,
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)',
                                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                borderRight: '2px solid var(--tb-border)'
                                                            }}>{license.balance_cif.toFixed(2)}</td>
                                                            {/* DFIA Dt / Notif No temporarily hidden
                                                            <td className="text-nowrap">{formatDate(license.license_date)}</td>
                                                            <td className="text-nowrap">{license.notification_number}</td>
                                                            */}
                                                            {groupItems.map((item, itemIdx) => {
                                                                const itemData = license.items[item.name] || {};
                                                                const hasData = itemData.quantity > 0;
                                                                // Verification data: the exact import item(s) behind this
                                                                // cell's plan lines (see item_pivot_report.py). The backend
                                                                // already merges every import item that's the SAME physical
                                                                // product (same HSN + normalized description) into one
                                                                // `planned_import_items` entry before this ever reaches the
                                                                // UI — so `plannedItems.length` is 1 in the overwhelming
                                                                // common case, rendered identically to before via
                                                                // `itemData.hs_code`/`description`/`*_quantity` (which
                                                                // resolve to that one merged entry). More than one entry
                                                                // here means genuinely DIFFERENT products share this
                                                                // item-name column (different HSN or description) — that
                                                                // is never merged into one value; each is listed
                                                                // separately, one aligned line per column, below.
                                                                const plannedItems = itemData.planned_import_items || [];
                                                                const hasMultiplePlannedItems = plannedItems.length > 1;
                                                                // Per-product: whether THIS product was manually planned
                                                                // (independent of every other product on this license).
                                                                // A product was manually planned when its plan_quantity or
                                                                // plan_cif is non-zero; otherwise show norm-derived values.
                                                                // Each item's cells share one background tint so the item's
                                                                // column group is visually distinct from its neighbours.
                                                                const itemBg = itemBgColor(itemIdx);
                                                                return (
                                                                    <React.Fragment
                                                                        key={`${license.license_number}-${item.id}`}>
                                                                        <td style={{backgroundColor: itemBg}}>
                                                                            {hasMultiplePlannedItems ? (
                                                                                <div className="d-flex flex-column gap-1">
                                                                                    <span
                                                                                        className="chip chip-neutral text-nowrap"
                                                                                        title={`${plannedItems.length} distinct products share this item — different HSN/description, so they couldn't be merged into one row`}
                                                                                    >
                                                                                        {plannedItems.length} items
                                                                                    </span>
                                                                                    <span className="text-nowrap">
                                                                                        {plannedItems.map((pit) => pit.hs_code || '-').join(', ')}
                                                                                    </span>
                                                                                </div>
                                                                            ) : (itemData.hs_code || '-')}
                                                                            {itemData.condition_type && (
                                                                                <ConditionBadge type={itemData.condition_type} size="xs" />
                                                                            )}
                                                                        </td>
                                                                        <td className="text-truncate"
                                                                            style={{maxWidth: '180px', backgroundColor: itemBg}}
                                                                            title={hasMultiplePlannedItems
                                                                                ? plannedItems.map((pit) => pit.description || '-').join(', ')
                                                                                : (itemData.description || '')}>
                                                                            {hasMultiplePlannedItems
                                                                                ? plannedItems.map((pit) => pit.description || '-').join(', ')
                                                                                : (itemData.description || '-')}
                                                                        </td>
                                                                        {/* Quantity/Allotted/Debited/Available are already
                                                                            summed across every distinct product sharing this
                                                                            cell by the backend (see _build_license_row in
                                                                            item_pivot_report.py) — unlike HSN/Description
                                                                            (strings, never merged), these numeric totals are
                                                                            unambiguous, so `itemData.*` is rendered as-is here
                                                                            with no per-product branching. */}
                                                                        <td className="text-right" style={{backgroundColor: itemBg}}>
                                                                            {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'font-semibold text-primary')} style={{backgroundColor: itemBg}}>
                                                                            {itemData.allotted_quantity ? itemData.allotted_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className="text-right" style={{backgroundColor: itemBg, ...(hasData ? {color: 'var(--warning-color)'} : {})}}>
                                                                            {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'text-success font-semibold')} style={{backgroundColor: itemBg}}>
                                                                            {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        {item.has_restriction && (
                                                                            <>
                                                                                <td className="text-center" style={{backgroundColor: itemBg}}>
                                                                                    {itemData.restriction !== null && itemData.restriction !== undefined ? (
                                                                                        <span
                                                                                            className="chip chip-info">{itemData.restriction}%</span>
                                                                                    ) : '-'}
                                                                                </td>
                                                                                <td className={cn('text-right', hasData && 'font-semibold')} style={{backgroundColor: itemBg}}>
                                                                                    {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                                </td>
                                                                            </>
                                                                        )}
                                                                        {/* Per-product plan: manual plan takes priority when
                                                                            this product was manually planned; fall back to
                                                                            norm-derived values otherwise. `plan_quantity`/
                                                                            `plan_cif`/`unit_price`/`planned_cif` are already
                                                                            cell-level totals for the WHOLE item-name column
                                                                            (see `row_data['items'][item_name]` in
                                                                            item_pivot_report.py — sourced independently of
                                                                            `planned_import_items`), so — exactly like the
                                                                            Excel export's equivalent column — there is no
                                                                            per-product branching here even when the cell
                                                                            has several genuinely distinct merged products. */}
                                                                        <td className="text-right" style={{backgroundColor: itemBg}}>
                                                                            {(Number(itemData.plan_quantity || 0) > 0 || Number(itemData.plan_cif || 0) > 0)
                                                                                ? Number(itemData.plan_quantity || 0).toFixed(3)
                                                                                : (itemData.unit_price != null ? Number(itemData.unit_price).toFixed(2) : '-')}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'font-semibold')} style={{backgroundColor: itemBg}}>
                                                                            {/* Value is the backend's single manual-vs-norm
                                                                                selection (`effective_planned_cif`) — the
                                                                                manual/hasManual check here is display-only
                                                                                (a manually-planned $0 CIF still shows "0.00",
                                                                                a norm-derived $0 shows "-"), not a re-derivation
                                                                                of which figure is authoritative. */}
                                                                            {(Number(itemData.plan_quantity || 0) > 0 || Number(itemData.plan_cif || 0) > 0)
                                                                                ? Number(itemData.effective_planned_cif || 0).toFixed(2)
                                                                                : (itemData.effective_planned_cif ? Number(itemData.effective_planned_cif).toFixed(2) : '-')}
                                                                        </td>
                                                                        {item.name === 'RUTILE - A3627' && (
                                                                            <td className={cn('text-right', hasData && 'font-semibold text-warning')} style={{backgroundColor: itemBg}}>
                                                                                {itemData.unit_price ? itemData.unit_price.toFixed(4) : '-'}
                                                                            </td>
                                                                        )}
                                                                    </React.Fragment>
                                                                );
                                                            })}
                                                        </tr>
                                                        {/* Notes & Latest Transfer now open from the Note / Transfer buttons
                                                            in the DFIA cell (see above) — bottom detail row removed. */}
                                                        </React.Fragment>
                                                    ))}
                                                    <tr className="table-warning font-bold" style={{
                                                        position: 'sticky',
                                                        bottom: 0,
                                                        backgroundColor: 'var(--warning-bg)'
                                                    }}>
                                                        <td className="text-uppercase" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }} colSpan={3}>
                                                            <Calculator className="size-4" aria-hidden="true" />
                                                            TOTAL
                                                        </td>
                                                        {!isCompact && (<>
                                                        <td style={{backgroundColor: 'var(--warning-bg)'}}></td>
                                                        <td className="text-right text-primary" style={{backgroundColor: 'var(--warning-bg)'}}>
                                                            {(groupTotals.total_cif || 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-warning" style={{backgroundColor: 'var(--warning-bg)'}}>
                                                            {(groupTotals.debited_cif || 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-info" style={{backgroundColor: 'var(--warning-bg)'}}>
                                                            {(groupTotals.alloted_cif || 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-secondary" style={{backgroundColor: 'var(--warning-bg)'}}>
                                                            {(groupTotals.total_effective_planned_cif || 0).toFixed(2)}
                                                        </td>
                                                        </>)}
                                                        <td className="text-right text-success" style={{
                                                            position: 'sticky',
                                                            left: balanceLeft,
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>
                                                            {(groupTotals.balance_cif || 0).toFixed(2)}
                                                        </td>
                                                        {/* DFIA Dt / Notif No totals temporarily hidden */}
                                                        {groupItems.map(item => {
                                                            // Backend-computed per-item totals for this group — see
                                                            // `notification_totals[...].items` in item_pivot_report.py.
                                                            // React only reads and formats them (Phase 2B.2A).
                                                            const itemTotals = groupTotals.items?.[item.name] || {};
                                                            const totalQty = itemTotals.quantity || 0;
                                                            const totalAllotted = itemTotals.allotted_quantity || 0;
                                                            const totalDebited = itemTotals.debited_quantity || 0;
                                                            const totalAvail = itemTotals.available_quantity || 0;
                                                            const totalRestrictionVal = itemTotals.restriction_value || 0;
                                                            // Planned CIF: the backend's single manual-vs-norm selection
                                                            // rule (`effective_planned_cif`), already resolved and summed.
                                                            const totalPlanned = itemTotals.effective_planned_cif || 0;
                                                            // Total Plan Qty: sum of the manually-planned quantity only —
                                                            // mirrors exactly what the per-row "Plan Qty" cell shows (it
                                                            // never falls back to available_quantity/unit_price), so a
                                                            // norm-driven row with no manual plan contributes 0 here
                                                            // rather than being folded into a blended rate.
                                                            const totalPlanQty = itemTotals.plan_quantity || 0;
                                                            return (
                                                                <React.Fragment key={`total-${item.id}`}>
                                                                    <td className="text-muted-foreground">-</td>
                                                                    <td className="text-muted-foreground">-</td>
                                                                    <td className="text-right">
                                                                        {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-primary">
                                                                        {totalAllotted > 0 ? totalAllotted.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-warning">
                                                                        {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-success">
                                                                        {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                                    </td>
                                                                    {item.has_restriction && (
                                                                        <>
                                                                            <td className="text-muted-foreground">-</td>
                                                                            <td className="text-right font-bold">
                                                                                {totalRestrictionVal > 0 ? totalRestrictionVal.toFixed(2) : '-'}
                                                                            </td>
                                                                        </>
                                                                    )}
                                                                    {/* Plan Qty total. Must be exactly one <td> here — an
                                                                        extra placeholder cell shifts this and every later
                                                                        item's totals out from under their headers (this
                                                                        column previously rendered blank "-" under
                                                                        "Plan Qty / Unit Price" while the real number
                                                                        landed one column over). */}
                                                                    <td className="text-right">
                                                                        {totalPlanQty > 0 ? totalPlanQty.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {totalPlanned > 0 ? totalPlanned.toFixed(2) : '-'}
                                                                    </td>
                                                                    {item.name === 'RUTILE - A3627' && (
                                                                        <td className="text-muted-foreground">-</td>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </tr>
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* Summary Table */}
                                            {(() => {
                                                // Backend-computed Notification Summary (Phase 2B.2B) — pure
                                                // rendering layer, no local aggregation. See
                                                // docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md.
                                                const summary = reportData?.notification_summary?.[activeNormTab]?.[groupKey] || {};
                                                return (
                                                    <div className="mt-4 px-3 pb-3">
                                                        <h6 className="mb-3 text-primary">
                                                            <Calculator className="size-4" aria-hidden="true" />
                                                            Summary
                                                        </h6>
                                                        <div style={{maxWidth: '1400px'}}>
                                                            <table className="table table-bordered table-sm" style={{tableLayout: 'fixed', width: '1400px'}}>
                                                                <thead className="table-light">
                                                                <tr>
                                                                    <th scope="col" style={{width: '70px'}}>Sr No</th>
                                                                    <th scope="col" style={{width: '460px'}}>Item Name</th>
                                                                    <th scope="col" className="text-right" style={{width: '220px'}}>Available Balance QTY</th>
                                                                    <th scope="col" className="text-right" style={{width: '150px'}}>Remaining Qty</th>
                                                                    <th scope="col" className="text-right" style={{width: '170px'}}>Unit Price</th>
                                                                    <th scope="col" className="text-right" style={{width: '300px'}}>Total Remaining CIF ($)</th>
                                                                </tr>
                                                                </thead>
                                                                <tbody>
                                                                {/* Opening Balance */}
                                                                <tr className="table-info">
                                                                    <td colSpan={2} className="text-center font-bold">OPENING BALANCE</td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.opening_balance || 0, 2)}
                                                                    </td>
                                                                    <td className="text-right font-bold">-</td>
                                                                    <td className="text-right font-bold">-</td>
                                                                    <td className="text-right font-bold">-</td>
                                                                </tr>

                                                                {/* Regular Items */}
                                                                {(Object.entries(summary.regular_items || {}) as [string, any][]).map(([itemName, itemData]: [string, any], idx) => (
                                                                    <tr key={itemName}>
                                                                        <td className="text-center">{idx + 1}</td>
                                                                        <td className="font-bold">{itemName}</td>
                                                                        <td className="text-right">
                                                                            {formatIndianNumber(itemData.available, 2)}
                                                                        </td>
                                                                        <td className="text-right">
                                                                            {itemData.planned_qty ? formatIndianNumber(itemData.planned_qty, 2) : '-'}
                                                                        </td>
                                                                        <td className="text-right">
                                                                            {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                        </td>
                                                                        <td className="text-right font-semibold">
                                                                            {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                        </td>
                                                                    </tr>
                                                                ))}

                                                                {/* Restricted Items Grouped by Percentage */}
                                                                {Object.keys(summary.restricted_items_by_percentage || {}).length > 0 && (
                                                                    <>
                                                                        {Object.entries(summary.restricted_items_by_percentage || {})
                                                                            .sort(([pctA], [pctB]) => parseFloat(pctA) - parseFloat(pctB))
                                                                            .map(([percentage, groupData], groupIdx) => {
                                                                                const startIdx = Object.keys(summary.regular_items || {}).length +
                                                                                    Object.entries(summary.restricted_items_by_percentage || {})
                                                                                        .slice(0, groupIdx)
                                                                                        .reduce((acc: number, [, data]: [string, any]) => acc + Object.keys((data as any).items || {}).length, 0);

                                                                                return (
                                                                                    <React.Fragment key={percentage}>
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan={6} className="text-center font-bold">
                                                                                                <TriangleAlert className="size-4" aria-hidden="true" />
                                                                                                RESTRICTED ITEMS - {parseFloat(percentage)}%
                                                                                            </td>
                                                                                        </tr>
                                                                                        {(Object.entries((groupData as any).items || {}) as [string, any][]).map(([itemName, itemData]: [string, any], idx) => (
                                                                                            <tr key={itemName} className="table-light">
                                                                                                <td className="text-center">{startIdx + idx + 1}</td>
                                                                                                <td className="font-bold">{itemName}</td>
                                                                                                <td className="text-right">
                                                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                                                </td>
                                                                                                <td className="text-right">
                                                                                                    {itemData.planned_qty ? formatIndianNumber(itemData.planned_qty, 2) : '-'}
                                                                                                </td>
                                                                                                <td className="text-right">
                                                                                                    {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                                                </td>
                                                                                                <td className="text-right font-semibold">
                                                                                                    {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                                                </td>
                                                                                            </tr>
                                                                                        ))}
                                                                                        {/* Balance for this restriction percentage (shared across all items) */}
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan={2} className="text-center font-bold">Balance {parseFloat(percentage)}%</td>
                                                                                            <td className="text-right font-bold">
                                                                                                {formatIndianNumber((groupData as any).shared_restriction_value, 2)}
                                                                                            </td>
                                                                                            <td className="text-right font-bold">-</td>
                                                                                            <td className="text-right font-bold">-</td>
                                                                                            <td className="text-right font-bold">-</td>
                                                                                        </tr>
                                                                                    </React.Fragment>
                                                                                );
                                                                            })}
                                                                    </>
                                                                )}
                                                                {/* Grand-total row for the Summary table. */}
                                                                <tr className="table-success">
                                                                    <td colSpan={2} className="text-center font-bold">TOTAL REMAINING CIF ($)</td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.total_available || 0, 2)}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.total_planned_qty || 0, 2)}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {summary.total_planned_qty > 0
                                                                            ? summary.blended_unit_price.toFixed(2)
                                                                            : '-'}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.total_planned_cif || 0, 2)}
                                                                    </td>
                                                                </tr>
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </CardContent>
                                    </Card>
                                </div>
                                );
                            })}

                            {/* ── Norms Total Summary ────────────────────────── */}
                            {(() => {
                                // Flatten all licenses across every notification group
                                // for the active norm — used only to gate rendering and
                                // show the license count; the summary numbers themselves
                                // come from the backend-owned norm_summary (Phase 2B.2B).
                                const allNormLicenses: any[] = Object.values(
                                    reportData?.licenses_by_norm_notification?.[activeNormTab] || {}
                                ).flat();
                                if (allNormLicenses.length === 0) return null;
                                const totalLicenses = allNormLicenses.length;
                                const ns = reportData?.norm_summary?.[activeNormTab] || {};
                                const itemRows = [
                                    ...Object.entries((ns.regular_items || {}) as Record<string, any>),
                                    ...Object.values((ns.restricted_items_by_percentage || {}) as Record<string, any>)
                                        .flatMap((g: any) => Object.entries(g.items || {})),
                                ] as [string, any][];

                                return (
                                    <Card className="mb-4 border-primary/30">
                                        <CardHeader
                                            className="flex-row items-center gap-3 text-primary-foreground"
                                            style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' }}>
                                            <Calculator className="size-4" aria-hidden="true" />
                                            <h5 className="mb-0 font-semibold">
                                                {activeNormTab} — Norms Total Summary
                                            </h5>
                                            <span className="chip chip-neutral ml-auto">{totalLicenses} Licenses</span>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div style={{ maxWidth: '1400px', overflowX: 'auto' }}>
                                                <table className="table table-bordered table-sm mb-0" style={{ tableLayout: 'fixed', width: '1400px' }}>
                                                    <thead className="table-light">
                                                        <tr>
                                                            <th scope="col" style={{ width: '50px' }}>Sr No</th>
                                                            <th scope="col" style={{ width: '400px' }}>Item Name</th>
                                                            <th scope="col" className="text-right" style={{ width: '220px' }}>Available Balance QTY</th>
                                                            <th scope="col" className="text-right" style={{ width: '150px' }}>Remaining Qty</th>
                                                            <th scope="col" className="text-right" style={{ width: '170px' }}>Unit Price</th>
                                                            <th scope="col" className="text-right" style={{ width: '300px' }}>Total Remaining CIF ($)</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {/* Opening Balance */}
                                                        <tr className="table-info">
                                                            <td colSpan={2} className="text-center font-bold">OPENING BALANCE</td>
                                                            <td className="text-right font-bold">{formatIndianNumber(ns.opening_balance || 0, 2)}</td>
                                                            <td className="text-right font-bold">-</td>
                                                            <td className="text-right font-bold">-</td>
                                                            <td className="text-right font-bold">-</td>
                                                        </tr>

                                                        {/* Item rows */}
                                                        {itemRows.map(([itemName, itemData], idx) => (
                                                            <tr key={itemName}>
                                                                <td className="text-center">{idx + 1}</td>
                                                                <td className="font-bold">{itemName}</td>
                                                                <td className="text-right">
                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                </td>
                                                                <td className="text-right">
                                                                    {itemData.planned_qty ? formatIndianNumber(itemData.planned_qty, 2) : '-'}
                                                                </td>
                                                                <td className="text-right">
                                                                    {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                </td>
                                                                <td className="text-right font-semibold">
                                                                    {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                </td>
                                                            </tr>
                                                        ))}

                                                        {/* Grand total */}
                                                        <tr className="table-primary font-bold">
                                                            <td colSpan={2} className="text-center font-bold">TOTAL REMAINING CIF ($)</td>
                                                            <td className="text-right font-bold">
                                                                {formatIndianNumber(ns.total_available || 0, 2)}
                                                            </td>
                                                            <td className="text-right font-bold">
                                                                {formatIndianNumber(ns.total_planned_qty || 0, 2)}
                                                            </td>
                                                            <td className="text-right font-bold">
                                                                {(ns.total_planned_qty || 0) > 0
                                                                    ? (ns.blended_unit_price || 0).toFixed(2)
                                                                    : '-'}
                                                            </td>
                                                            <td className="text-right font-bold">
                                                                {formatIndianNumber(ns.total_planned_cif || 0, 2)}
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })()}

                            {/* Notes and Conditions Section */}
                            {activeNormTab && reportData?.norm_notes_conditions?.[activeNormTab] && (
                                reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 || reportData?.norm_notes_conditions?.[activeNormTab]?.conditions?.length > 0
                            ) && (
                                <Card className="mb-4">
                                    <CardHeader>
                                        <h5 className="flex items-center gap-2 font-semibold">
                                            <Info className="size-4" aria-hidden="true" />
                                            SION Norm {activeNormTab} - Notes & Conditions
                                        </h5>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-4">
                                            {/* Notes Section */}
                                            {reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 && (
                                                <div>
                                                    <h6 className="mb-3 flex items-center gap-2 text-primary">
                                                        <StickyNote className="size-4" aria-hidden="true" />
                                                        Notes
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.notes
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((note, index) => (
                                                                <div key={index} className="list-group-item border-start border-primary border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="chip chip-primary mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow whitespace-pre-wrap">
                                                                            {note.note_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Conditions Section */}
                                            {reportData?.norm_notes_conditions?.[activeNormTab]?.conditions?.length > 0 && (
                                                <div>
                                                    <h6 className="mb-3 flex items-center gap-2 text-warning">
                                                        <TriangleAlert className="size-4" aria-hidden="true" />
                                                        Conditions
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.conditions
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((condition, index) => (
                                                                <div key={index} className="list-group-item border-start border-warning border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="chip chip-warning mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow whitespace-pre-wrap">
                                                                            {condition.condition_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}

            </div>

            {conditionModal && (
                <Dialog open={!!conditionModal} onOpenChange={(o) => !o && setConditionModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-4xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileText className="size-4" />
                                Condition Sheet — {conditionModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {conditionModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConditionModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {transferModal && (
                <Dialog open={!!transferModal} onOpenChange={(o) => !o && setTransferModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <ArrowLeftRight className="size-4" />
                                Transfer Status — {transferModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {transferModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setTransferModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {issueModal && (
                <Dialog open={!!issueModal} onOpenChange={(open) => !open && setIssueModal(null)}>
                    <DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Issues — {issueModal.license_number}</DialogTitle></DialogHeader>
                        <div className="space-y-2">{(issueModal.issues || []).filter(isPositivePivotIssue).length ? (issueModal.issues || []).filter(isPositivePivotIssue).map((issue) => { const type = String(issue.type); const isCif = type.includes("_cif_"); const planned = type.includes("over_planned"); const excessQty = planned ? issue.planned_excess_qty : issue.actual_excess_qty; const excessCif = planned ? issue.planned_excess_cif : issue.actual_excess_cif; const label = ({ item_cif_over_utilized: "Item CIF Over-Utilized", item_cif_over_planned: "Item CIF Over-Planned", item_qty_over_utilized: "Item Quantity Over-Utilized", item_qty_over_planned: "Item Quantity Over-Planned" } as Record<string, string>)[type] ?? type.replace(/_/g, ' '); return <div key={`${issue.item_key}-${type}`} className="rounded border border-red-200 bg-red-50 p-3 text-sm"><div className="font-semibold text-red-800">{label}</div><div>{issue.item_key}{issue.sion ? ` · ${issue.sion}` : ''}</div>{isCif ? <div className="mt-1 space-y-0.5"><div>Item CIF Cap: {pivotNumber(issue.item_cif_cap, 2)} · BOE-Used CIF: {pivotNumber(issue.boe_used_cif, 2)} · Allotment CIF: {pivotNumber(issue.allotted_cif, 2)}</div><div>Total Actual Used CIF: {pivotNumber(issue.actual_used_cif, 2)} · Available CIF Before Plan: {pivotNumber(issue.available_cif, 2)}</div><div>Effective Planned CIF: {pivotNumber(issue.effective_planned_cif, 2)} · Balance CIF After Plan: {pivotNumber(issue.balance_cif_after_plan, 2)}</div><div>Positive Excess CIF: {pivotNumber(excessCif, 2)}</div></div> : <div className="mt-1"><div>Total Qty: {pivotNumber(issue.total_qty, 3)} · Total Utilized Qty: {pivotNumber(issue.total_utilized_qty, 3)}</div><div>Available Qty: {pivotNumber(issue.available_qty, 3)} · Effective Planned Qty: {pivotNumber(issue.planned_qty, 3)} · Positive Excess Qty: {pivotNumber(excessQty, 3)}</div></div>}</div>; }) : <p className="text-sm text-muted-foreground">No planning exceptions found.</p>}</div>
                        <DialogFooter><Button variant="outline" onClick={() => setIssueModal(null)}>Close</Button><Button onClick={() => handleCanonicalReplan(issueModal)}>Re Plan me</Button><Button onClick={() => navigate(`/licenses/${issueModal.license_id}/overview`)}>Open Licence</Button></DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {noteModal && (
                <Dialog open={!!noteModal} onOpenChange={(o) => !o && setNoteModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <StickyNote className="size-4" />
                                Notes — {noteModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {noteModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setNoteModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {/* Utilization planning — same panel the licenses page uses. */}
            <LicensePlanningPanel
                show={showPlanModal}
                onHide={() => { setShowPlanModal(false); setPlanLicense(null); }}
                licenseId={planLicense?.id}
                licenseNumber={planLicense?.number}
                balanceCif={planLicense?.balance || 0}
                onSaved={() => { if (activeNormTab) loadReport(activeNormTab); }}
            />
        </div>
    );
}
