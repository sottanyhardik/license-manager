import { useState, useEffect, useMemo } from "react";
import { toast } from "sonner";
import CreatableSelect from "react-select/creatable";
import AsyncSelect from "react-select/async";
import {
    Plus, X, Trash2, Info, FileText, FileArchive, Loader2,
    Send, Users, ClipboardList, CheckCircle,
} from "lucide-react";

import api from "../api/axios";
import { formatDate } from "../utils/dateFormatter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

/**
 * Reusable Transfer Letter Form — used by Allotment, BOE and Trade pages.
 */
export default function TransferLetterForm({
    instanceId,
    instanceType,
    instanceIdentifier,
    items,
    disabled = false,
    onSuccess,
    onError,
}: {
    instanceId?: string | number;
    instanceType?: string;
    instanceIdentifier?: string;
    items?: Record<string, any>[];
    disabled?: boolean;
    onSuccess?: (msg: string) => void;
    onError?: (msg: string) => void;
}) {
    const [parties, setParties] = useState([
        { id: 1, company: null, addressLine1: "", addressLine2: "", template: null },
    ]);
    const [companyOptions, setCompanyOptions] = useState([]);
    const [licenseEdits, setLicenseEdits] = useState<Record<string, any>>({});
    const [generating, setGenerating] = useState(null);
    const [selectedItems, setSelectedItems] = useState(items?.map((item) => item.id) || []);

    useEffect(() => {
        setSelectedItems(items?.map((item) => item.id) || []);
    }, [items]);

    const groupedItems = useMemo(() => {
        const groups: Record<string, { license_number: string; purchase_status: any; item_ids: any[]; total_cif: number }> = {};
        (items || []).forEach((item) => {
            const key = String(item.license_number || "-");
            if (!groups[key]) {
                groups[key] = { license_number: key, purchase_status: item.purchase_status, item_ids: [], total_cif: 0 };
            }
            groups[key].item_ids.push(item.id);
            groups[key].total_cif += parseFloat(String(item.cif_fc || 0));
        });
        return Object.values(groups);
    }, [items]);

    const loadCompanyOptions = async (inputValue) => {
        try {
            const { data } = await api.get(`masters/companies/?search=${inputValue}`);
            return (data.results || data || []).map((c) => ({ value: c.id, label: c.name, ...c }));
        } catch { return []; }
    };

    const loadTransferLetterOptions = async (inputValue) => {
        try {
            const { data } = await api.get(`masters/transfer-letters/?search=${inputValue || ""}`);
            return (data.results || data || []).map((tl) => ({ value: tl.id, label: tl.name }));
        } catch { return []; }
    };

    const addParty = () =>
        setParties((prev) => [...prev, { id: Date.now(), company: null, addressLine1: "", addressLine2: "", template: null }]);
    const removeParty = (id) => setParties((prev) => prev.filter((p) => p.id !== id));
    const updateParty = (id, updates) => setParties((prev) => prev.map((p) => (p.id === id ? { ...p, ...updates } : p)));

    const handlePartyCompanyChange = async (id, selectedCompany, actionMeta) => {
        updateParty(id, { company: selectedCompany });
        if (selectedCompany?.value && actionMeta.action !== "create-option") {
            try {
                const { data } = await api.get(`masters/companies/${selectedCompany.value}/`);
                updateParty(id, { company: selectedCompany, addressLine1: data.address_line_1 || "", addressLine2: data.address_line_2 || "" });
            } catch { toast.error("Failed to fetch company details"); }
        } else if (!selectedCompany) {
            updateParty(id, { company: null, addressLine1: "", addressLine2: "" });
        }
    };

    const handleLicenseEdit = (licenseNumber, value) =>
        setLicenseEdits((prev) => ({ ...prev, [licenseNumber]: value }));

    const isGroupSelected = (licenseNumber) => {
        const group = groupedItems.find((g) => g.license_number === licenseNumber);
        return group?.item_ids.every((id) => selectedItems.includes(id)) ?? false;
    };

    const toggleGroup = (licenseNumber) => {
        const group = groupedItems.find((g) => g.license_number === licenseNumber);
        if (!group) return;
        if (isGroupSelected(licenseNumber)) {
            setSelectedItems((prev) => prev.filter((id) => !group.item_ids.includes(id)));
        } else {
            setSelectedItems((prev) => [...new Set([...prev, ...group.item_ids])]);
        }
    };

    const validParties = parties.filter((p) => (p.company?.label || "").trim() && p.template);

    const handleGenerate = async (includeLicenseCopy = true, format = "zip") => {
        const partiesWithoutTemplate = parties.filter((p) => (p.company?.label || "").trim() && !p.template);
        if (partiesWithoutTemplate.length > 0) { onError?.(`Please select a template for all parties`); return; }
        if (validParties.length === 0) { onError?.("Please enter at least one company name and select its template"); return; }
        const selectedGroups = groupedItems.filter((g) => isGroupSelected(g.license_number));
        if (selectedGroups.length === 0) { onError?.("Please select at least one license to generate transfer letter"); return; }

        if (format === "pdf") setGenerating("pdf");
        else setGenerating(includeLicenseCopy ? "with_copy" : "without_copy");

        const filteredCifEdits: Record<string, any> = {};
        groupedItems.forEach((group) => {
            const editedTotal = licenseEdits[group.license_number];
            if (editedTotal !== undefined) {
                const activeIds = group.item_ids.filter((id) => selectedItems.includes(id));
                activeIds.forEach((id, idx) => { filteredCifEdits[id] = idx === 0 ? editedTotal : "0"; });
            }
        });

        const requestData = {
            parties: validParties.map((p) => ({
                company_name: (p.company?.label || "").trim(),
                address_line1: p.addressLine1.trim(),
                address_line2: p.addressLine2.trim(),
                template_id: p.template?.value || p.template,
            })),
            cif_edits: filteredCifEdits,
            include_license_copy: format === "pdf" ? true : includeLicenseCopy,
            selected_items: selectedItems,
            include_todays_date: true,
            format,
        };

        try {
            const endpoint = instanceType === "allotment"
                ? `/allotment-actions/${instanceId}/generate-transfer-letter/`
                : instanceType === "trade"
                ? `/trades/${instanceId}/generate-transfer-letter/`
                : `/bill-of-entries/${instanceId}/generate-transfer-letter/`;

            const response = await api.post(endpoint, requestData, { responseType: "blob" });
            const identifier = instanceIdentifier || instanceId;
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", format === "pdf"
                ? `TransferLetter_${instanceType}_${identifier}.pdf`
                : `TransferLetter_${instanceType}_${identifier}_${includeLicenseCopy ? "WithCopy" : "WithoutCopy"}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            onSuccess?.(format === "pdf"
                ? `Transfer letter PDF generated`
                : validParties.length > 1
                ? `Transfer letters for ${validParties.length} parties generated`
                : `Transfer letter ${includeLicenseCopy ? "with" : "without"} license copy generated`);
        } catch (err) {
            onError?.(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGenerating(null);
        }
    };

    const selectedCount = groupedItems.filter((g) => isGroupSelected(g.license_number)).length;
    const genDisabled = generating !== null || disabled || validParties.length === 0 || selectedItems.length === 0 || selectedCount === 0;

    const psColors: Record<string, { bg: string; color: string }> = {
        GE: { bg: "#DBEAFE", color: "#1E3A8A" },
        MI: { bg: "#D1FAE5", color: "var(--tb-success-text)" },
        CO: { bg: "#EDE9FE", color: "#5B21B6" },
        PP: { bg: "#FED7AA", color: "#7C2D12" },
        SM: { bg: "#FCE7F3", color: "#831843" },
        GO: { bg: "#E2E8F0", color: "#1E293B" },
    };
    const getPsStyle = (s: string) => psColors[s] || { bg: "var(--tb-sunken)", color: "var(--tb-text-secondary)" };

    return (
        <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            {/* ── Header ─────────────────────────────────────────── */}
            <div className="flex items-center gap-3 border-b border-border/60 px-5 py-3.5" style={{ background: 'linear-gradient(135deg, var(--tb-brand-50), var(--tb-card-bg))' }}>
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg" style={{ background: 'var(--tb-brand)', boxShadow: '0 2px 8px rgba(var(--tb-brand-rgb,59,130,246),.25)' }}>
                    <Send className="size-4 text-white" aria-hidden="true" />
                </div>
                <div>
                    <h2 className="text-[13px] font-bold leading-tight tracking-tight text-foreground">Generate Transfer Letter</h2>
                    <p className="text-[11px] text-muted-foreground">
                        {validParties.length > 0 ? `${validParties.length} recipient${validParties.length > 1 ? 's' : ''} ready` : 'Add recipients to generate'}
                        {selectedCount > 0 && ` · ${selectedCount} license${selectedCount > 1 ? 's' : ''} selected`}
                    </p>
                </div>
                {validParties.length > 0 && selectedCount > 0 && (
                    <div className="ml-auto flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                        <CheckCircle className="size-3.5" />{validParties.length} party · {selectedCount} license
                    </div>
                )}
            </div>

            <div className="px-5 py-4">
                {/* ── Recipients ───────────────────────────────────── */}
                <div className="mb-5">
                    <div className="mb-2.5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Users className="size-3.5 text-muted-foreground" />
                            <span className="text-[12px] font-bold uppercase tracking-wider text-muted-foreground">Recipients</span>
                            {parties.length > 1 && (
                                <span className="inline-flex size-[18px] items-center justify-center rounded-full bg-primary text-[10px] font-bold leading-none text-white">{parties.length}</span>
                            )}
                        </div>
                        <button
                            type="button"
                            onClick={addParty}
                            disabled={disabled}
                            className="flex items-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1 text-[11.5px] font-semibold text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                        >
                            <Plus className="size-3.5" />Add Party
                        </button>
                    </div>

                    <div className="flex flex-col gap-2">
                        {parties.map((party, idx) => (
                            <div key={party.id} className="group flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-background px-3 py-2.5 transition-shadow hover:shadow-sm">
                                {parties.length > 1 && (
                                    <span className="inline-flex size-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-white">
                                        {idx + 1}
                                    </span>
                                )}
                                <div className="min-w-[200px] flex-[2]">
                                    <CreatableSelect
                                        value={party.company}
                                        onChange={(val, action) => handlePartyCompanyChange(party.id, val, action)}
                                        onInputChange={(v) => { if (v.length >= 2) loadCompanyOptions(v).then(setCompanyOptions); }}
                                        options={companyOptions}
                                        placeholder="Company name..."
                                        isClearable
                                        formatCreateLabel={(v) => `Use: "${v}"`}
                                        isDisabled={disabled}
                                        classNamePrefix="react-select"
                                        styles={{ control: (b) => ({ ...b, minHeight: 34, fontSize: 13 }), valueContainer: (b) => ({ ...b, padding: "0 8px" }) }}
                                    />
                                </div>
                                <Input className="h-[34px] min-w-[150px] flex-[1.5] text-sm" value={party.addressLine1}
                                    onChange={(e) => updateParty(party.id, { addressLine1: e.target.value })}
                                    placeholder="Address line 1" disabled={disabled} />
                                <Input className="h-[34px] min-w-[150px] flex-[1.5] text-sm" value={party.addressLine2}
                                    onChange={(e) => updateParty(party.id, { addressLine2: e.target.value })}
                                    placeholder="Address line 2" disabled={disabled} />
                                <div className="min-w-[180px] flex-[1.5]">
                                    <AsyncSelect
                                        value={party.template}
                                        onChange={(val) => updateParty(party.id, { template: val })}
                                        loadOptions={loadTransferLetterOptions}
                                        defaultOptions cacheOptions
                                        placeholder="Template..."
                                        isClearable isDisabled={disabled}
                                        classNamePrefix="react-select"
                                        styles={{
                                            control: (b) => ({
                                                ...b, minHeight: 34, fontSize: 13,
                                                borderColor: !party.template && (party.company?.label || "").trim() ? "var(--tb-warning)" : b.borderColor,
                                            }),
                                            valueContainer: (b) => ({ ...b, padding: "0 8px" }),
                                        }}
                                    />
                                </div>
                                {parties.length > 1 && (
                                    <button type="button" onClick={() => removeParty(party.id)} disabled={disabled}
                                        className="flex size-[34px] shrink-0 items-center justify-center rounded-md border border-border/70 text-muted-foreground transition-colors hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive">
                                        <X className="size-3.5" />
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                    <div className="mt-2 flex flex-wrap justify-between gap-1.5 text-[11px] text-muted-foreground">
                        <span>Select from dropdown to auto-fill addresses, or type to create a custom entry</span>
                        <span className="flex items-center gap-1 opacity-80">
                            <Info className="size-3" />
                            Today's date ({formatDate(new Date())}) will be included automatically
                        </span>
                    </div>
                </div>

                {/* ── Items for Transfer Letter ─────────────────────── */}
                {groupedItems.length > 0 && (
                    <div className="mb-5">
                        <div className="mb-2 flex items-center gap-2">
                            <ClipboardList className="size-3.5 text-muted-foreground" />
                            <span className="text-[12px] font-bold uppercase tracking-wider text-muted-foreground">
                                Items for Transfer Letter
                            </span>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${selectedCount > 0 ? 'bg-primary/5 text-primary' : 'bg-muted text-muted-foreground'}`}>
                                {selectedCount} of {groupedItems.length} selected
                            </span>
                            {items && items.length > groupedItems.length && (
                                <span className="text-[11px] text-muted-foreground">({items.length} rows merged by license)</span>
                            )}
                        </div>
                        <div className="overflow-hidden rounded-lg border border-border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/40 text-left text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
                                        <th scope="col" className="w-10 px-3 py-2.5">#</th>
                                        <th scope="col" className="px-3 py-2.5">License Number</th>
                                        <th scope="col" className="w-28 px-3 py-2.5">Purchase Status</th>
                                        <th scope="col" className="w-44 px-3 py-2.5">Total CIF FC <span className="font-normal normal-case opacity-60">(editable)</span></th>
                                        <th scope="col" className="w-16 px-3 py-2.5 text-center">Select</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/40">
                                    {groupedItems.map((group, idx) => {
                                        const isSelected = isGroupSelected(group.license_number);
                                        const displayCif = licenseEdits[group.license_number] !== undefined
                                            ? licenseEdits[group.license_number]
                                            : group.total_cif.toFixed(2);
                                        const psStyle = getPsStyle(group.purchase_status);
                                        return (
                                            <tr key={group.license_number}
                                                className={`transition-colors ${isSelected ? "bg-background hover:bg-muted/30" : "bg-muted/20 opacity-50"}`}>
                                                <td className="px-3 py-2 text-muted-foreground">{idx + 1}</td>
                                                <td className="px-3 py-2">
                                                    <span className="font-mono text-[13px] font-semibold text-foreground">{group.license_number}</span>
                                                    {group.item_ids.length > 1 && (
                                                        <span className="ml-2 rounded bg-primary/5 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                                                            {group.item_ids.length} rows
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2">
                                                    <span className="rounded px-2 py-0.5 text-[11px] font-semibold" style={{ background: psStyle.bg, color: psStyle.color }}>
                                                        {group.purchase_status || "N/A"}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2">
                                                    <Input type="number" className="h-8 text-sm font-mono" value={displayCif}
                                                        onChange={(e) => handleLicenseEdit(group.license_number, e.target.value)}
                                                        step="0.01" disabled={disabled || !isSelected} />
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    <button type="button" onClick={() => toggleGroup(group.license_number)} disabled={disabled}
                                                        className={`flex size-7 items-center justify-center rounded-md border transition-colors ${
                                                            isSelected
                                                                ? "border-destructive/50 text-destructive hover:bg-destructive/10"
                                                                : "border-primary/50 text-primary hover:bg-primary/10"
                                                        }`}
                                                        title={isSelected ? "Remove from transfer letter" : "Add to transfer letter"}>
                                                        {isSelected ? <Trash2 className="size-3" /> : <Plus className="size-3" />}
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {groupedItems.length === 0 && (
                    <div className="mb-5 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-[13px] text-amber-700">
                        <Info className="size-4 shrink-0" />
                        No items found. Please add items first.
                    </div>
                )}

                {/* ── Generate actions ─────────────────────────────── */}
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
                    <div className="text-[11.5px] text-muted-foreground">
                        {genDisabled && validParties.length === 0 && (
                            <span className="flex items-center gap-1"><Info className="size-3.5" />Add at least one recipient with a template to generate</span>
                        )}
                        {!genDisabled && (
                            <span className="flex items-center gap-1 font-medium text-emerald-700">
                                <CheckCircle className="size-3.5" />Ready to generate for {validParties.length} recipient{validParties.length > 1 ? 's' : ''}
                            </span>
                        )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <Button variant="outline" size="sm"
                            onClick={() => generating === null && handleGenerate(false, "zip")}
                            disabled={genDisabled}>
                            {generating === "without_copy" ? <Loader2 className="size-3.5 animate-spin" /> : <FileArchive className="size-3.5" />}
                            {generating === "without_copy" ? "Generating…" : `Without Copy (${selectedCount})`}
                        </Button>
                        <Button variant="outline" size="sm"
                            onClick={() => generating === null && handleGenerate(true, "zip")}
                            disabled={genDisabled}>
                            {generating === "with_copy" ? <Loader2 className="size-3.5 animate-spin" /> : <FileArchive className="size-3.5" />}
                            {generating === "with_copy" ? "Generating…" : `With Copy (${selectedCount}${validParties.length > 1 ? ` × ${validParties.length}` : ""})`}
                        </Button>
                        <Button size="sm"
                            style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))', border: 'none', color: '#fff', boxShadow: '0 2px 8px rgba(59,130,246,.3)' }}
                            onClick={() => generating === null && handleGenerate(true, "pdf")}
                            disabled={genDisabled}>
                            {generating === "pdf" ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                            {generating === "pdf" ? "Generating…" : "Download PDF"}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}
