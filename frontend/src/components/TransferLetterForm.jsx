import { useState, useEffect, useMemo } from "react";
import { toast } from "react-toastify";
import CreatableSelect from "react-select/creatable";
import AsyncSelect from "react-select/async";
import {
    Plus, X, Trash2, Info, FileText, FileArchive, Loader2,
} from "lucide-react";

import api from "../api/axios";
import { formatDate } from "../utils/dateFormatter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Reusable Transfer Letter Form — used by Allotment, BOE and Trade pages.
 * (Markup migrated to Tailwind/shadcn; all generation logic preserved.)
 */
export default function TransferLetterForm({
    instanceId,
    instanceType, // 'allotment' | 'boe' | 'trade'
    instanceIdentifier,
    items,
    disabled = false,
    onSuccess,
    onError,
}) {
    const [parties, setParties] = useState([
        { id: 1, company: null, addressLine1: "", addressLine2: "", template: null },
    ]);
    const [companyOptions, setCompanyOptions] = useState([]);
    const [licenseEdits, setLicenseEdits] = useState({});
    const [generating, setGenerating] = useState(null); // null | 'with_copy' | 'without_copy' | 'pdf'
    const [selectedItems, setSelectedItems] = useState(items?.map((item) => item.id) || []);

    useEffect(() => {
        setSelectedItems(items?.map((item) => item.id) || []);
    }, [items]);

    const groupedItems = useMemo(() => {
        const groups = {};
        (items || []).forEach((item) => {
            const key = item.license_number || "-";
            if (!groups[key]) {
                groups[key] = { license_number: key, purchase_status: item.purchase_status, item_ids: [], total_cif: 0 };
            }
            groups[key].item_ids.push(item.id);
            groups[key].total_cif += parseFloat(item.cif_fc || 0);
        });
        return Object.values(groups);
    }, [items]);

    const loadCompanyOptions = async (inputValue) => {
        try {
            const { data } = await api.get(`masters/companies/?search=${inputValue}`);
            const results = data.results || data || [];
            return results.map((company) => ({ value: company.id, label: company.name, ...company }));
        } catch {
            return [];
        }
    };

    const loadTransferLetterOptions = async (inputValue) => {
        try {
            const { data } = await api.get(`masters/transfer-letters/?search=${inputValue || ""}`);
            const results = data.results || data || [];
            return results.map((tl) => ({ value: tl.id, label: tl.name }));
        } catch {
            return [];
        }
    };

    const addParty = () =>
        setParties((prev) => [...prev, { id: Date.now(), company: null, addressLine1: "", addressLine2: "", template: null }]);
    const removeParty = (id) => setParties((prev) => prev.filter((p) => p.id !== id));
    const updateParty = (id, updates) => setParties((prev) => prev.map((p) => (p.id === id ? { ...p, ...updates } : p)));

    const handlePartyCompanyChange = async (id, selectedCompany, actionMeta) => {
        updateParty(id, { company: selectedCompany });
        if (selectedCompany && selectedCompany.value && actionMeta.action !== "create-option") {
            try {
                const { data } = await api.get(`masters/companies/${selectedCompany.value}/`);
                updateParty(id, { company: selectedCompany, addressLine1: data.address_line_1 || "", addressLine2: data.address_line_2 || "" });
            } catch {
                toast.error("Failed to fetch company details");
            }
        } else if (!selectedCompany) {
            updateParty(id, { company: null, addressLine1: "", addressLine2: "" });
        }
    };

    const handleLicenseEdit = (licenseNumber, value) => setLicenseEdits((prev) => ({ ...prev, [licenseNumber]: value }));

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
        if (partiesWithoutTemplate.length > 0) {
            onError?.(`Please select a template for all parties`);
            return;
        }
        if (validParties.length === 0) {
            onError?.("Please enter at least one company name and select its template");
            return;
        }
        const selectedGroups = groupedItems.filter((g) => isGroupSelected(g.license_number));
        if (selectedGroups.length === 0) {
            onError?.("Please select at least one license to generate transfer letter");
            return;
        }

        if (format === "pdf") setGenerating("pdf");
        else setGenerating(includeLicenseCopy ? "with_copy" : "without_copy");

        const filteredCifEdits = {};
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
            if (format === "pdf") {
                link.setAttribute("download", `TransferLetter_${instanceType}_${identifier}.pdf`);
            } else {
                const copyType = includeLicenseCopy ? "WithCopy" : "WithoutCopy";
                link.setAttribute("download", `TransferLetter_${instanceType}_${identifier}_${copyType}.zip`);
            }
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            const msg = format === "pdf"
                ? `Transfer letter PDF generated successfully`
                : validParties.length > 1
                ? `Transfer letters for ${validParties.length} parties generated successfully`
                : `Transfer letter ${includeLicenseCopy ? "with" : "without"} license copy generated successfully`;
            onSuccess?.(msg);
        } catch (err) {
            onError?.(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGenerating(null);
        }
    };

    const selectedCount = groupedItems.filter((g) => isGroupSelected(g.license_number)).length;
    const genDisabled = generating !== null || disabled || validParties.length === 0 || selectedItems.length === 0 || selectedCount === 0;

    const statusVariant = (s) =>
        s === "CO" ? "success" : s === "FS" ? "default" : s === "PP" ? "warning" : "secondary";

    return (
        <Card className="mb-4">
            <CardContent className="pt-5">
                <h2 className="mb-3 text-base font-semibold tracking-tight text-foreground">Generate Transfer Letter</h2>

                {/* Recipients */}
                <div className="mb-4">
                    <div className="mb-2 flex items-center justify-between">
                        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                            Recipients
                            {parties.length > 1 && <Badge>{parties.length}</Badge>}
                        </span>
                        <Button variant="outline" size="sm" onClick={addParty} disabled={disabled}>
                            <Plus className="size-3.5" />Add Party
                        </Button>
                    </div>

                    <div className="flex flex-col gap-2">
                        {parties.map((party, idx) => (
                            <div key={party.id} className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2">
                                {parties.length > 1 && (
                                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
                                        {idx + 1}
                                    </span>
                                )}
                                <div className="min-w-[180px] flex-1">
                                    <CreatableSelect
                                        value={party.company}
                                        onChange={(val, action) => handlePartyCompanyChange(party.id, val, action)}
                                        onInputChange={(inputValue) => {
                                            if (inputValue.length >= 2) loadCompanyOptions(inputValue).then((opts) => setCompanyOptions(opts));
                                        }}
                                        options={companyOptions}
                                        placeholder="Company name..."
                                        isClearable
                                        formatCreateLabel={(v) => `Use: "${v}"`}
                                        isDisabled={disabled}
                                        classNamePrefix="react-select"
                                        styles={{
                                            control: (base) => ({ ...base, minHeight: "34px", fontSize: 14 }),
                                            valueContainer: (base) => ({ ...base, padding: "0 8px" }),
                                        }}
                                    />
                                </div>
                                <Input
                                    className="h-9 min-w-[140px] flex-1"
                                    value={party.addressLine1}
                                    onChange={(e) => updateParty(party.id, { addressLine1: e.target.value })}
                                    placeholder="Address line 1"
                                    disabled={disabled}
                                />
                                <Input
                                    className="h-9 min-w-[140px] flex-1"
                                    value={party.addressLine2}
                                    onChange={(e) => updateParty(party.id, { addressLine2: e.target.value })}
                                    placeholder="Address line 2"
                                    disabled={disabled}
                                />
                                <div className="min-w-[180px] flex-1">
                                    <AsyncSelect
                                        value={party.template}
                                        onChange={(val) => updateParty(party.id, { template: val })}
                                        loadOptions={loadTransferLetterOptions}
                                        defaultOptions
                                        cacheOptions
                                        placeholder="Template..."
                                        isClearable
                                        isDisabled={disabled}
                                        classNamePrefix="react-select"
                                        styles={{
                                            control: (base) => ({
                                                ...base,
                                                minHeight: "34px",
                                                fontSize: 14,
                                                borderColor: !party.template && (party.company?.label || "").trim() ? "var(--tb-warning)" : base.borderColor,
                                            }),
                                            valueContainer: (base) => ({ ...base, padding: "0 8px" }),
                                        }}
                                    />
                                </div>
                                {parties.length > 1 && (
                                    <Button variant="outline" size="icon" className="size-9 shrink-0" onClick={() => removeParty(party.id)} disabled={disabled} title="Remove party">
                                        <X className="size-4" />
                                    </Button>
                                )}
                            </div>
                        ))}
                    </div>
                    <div className="mt-1.5 flex flex-wrap justify-between gap-2 text-[11.5px] text-muted-foreground">
                        <span>Select from dropdown to auto-fill addresses, or type to create a custom entry</span>
                        <span className="flex items-center gap-1">
                            <Info className="size-3.5" />
                            Today's date ({formatDate(new Date())}) will be included automatically
                        </span>
                    </div>
                </div>

                {/* Items table */}
                {groupedItems.length > 0 && (
                    <div className="mb-4">
                        <h3 className="mb-2 text-sm font-semibold text-foreground">
                            Items for Transfer Letter ({selectedCount} of {groupedItems.length} selected)
                            {items.length > groupedItems.length && (
                                <span className="ml-2 text-[12.5px] font-normal text-muted-foreground">({items.length} rows merged by license)</span>
                            )}
                        </h3>
                        <div className="overflow-x-auto rounded-md border border-border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th className="w-12 px-3 py-2">#</th>
                                        <th className="px-3 py-2">License Number</th>
                                        <th className="px-3 py-2">Purchase Status</th>
                                        <th className="w-[170px] px-3 py-2">Total CIF FC (editable)</th>
                                        <th className="w-[100px] px-3 py-2">Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {groupedItems.map((group, idx) => {
                                        const isSelected = isGroupSelected(group.license_number);
                                        const displayCif = licenseEdits[group.license_number] !== undefined
                                            ? licenseEdits[group.license_number]
                                            : group.total_cif.toFixed(2);
                                        return (
                                            <tr key={group.license_number} className={`border-b border-border/60 ${!isSelected ? "opacity-55" : ""}`}>
                                                <td className="px-3 py-1.5">{idx + 1}</td>
                                                <td className="px-3 py-1.5">
                                                    {group.license_number}
                                                    {group.item_ids.length > 1 && (
                                                        <Badge variant="info" className="ml-2">{group.item_ids.length} rows</Badge>
                                                    )}
                                                </td>
                                                <td className="px-3 py-1.5">
                                                    <Badge variant={statusVariant(group.purchase_status)}>{group.purchase_status || "N/A"}</Badge>
                                                </td>
                                                <td className="px-3 py-1.5">
                                                    <Input
                                                        type="number"
                                                        className="h-8"
                                                        value={displayCif}
                                                        onChange={(e) => handleLicenseEdit(group.license_number, e.target.value)}
                                                        step="0.01"
                                                        disabled={disabled || !isSelected}
                                                    />
                                                </td>
                                                <td className="px-3 py-1.5">
                                                    <Button
                                                        variant="outline"
                                                        size="icon"
                                                        className="size-8"
                                                        onClick={() => toggleGroup(group.license_number)}
                                                        disabled={disabled}
                                                        title={isSelected ? "Remove from transfer letter" : "Add to transfer letter"}
                                                    >
                                                        {isSelected ? <Trash2 className="size-3.5" /> : <Plus className="size-3.5" />}
                                                    </Button>
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
                    <div className="mb-4 rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-[13px] text-warning">
                        No items found. Please add items first.
                    </div>
                )}

                {/* Generate buttons */}
                <div className="flex flex-wrap justify-end gap-2">
                    <Button onClick={() => generating === null && handleGenerate(true, "pdf")} disabled={genDisabled} title="Download all TL pages merged into a single PDF">
                        {generating === "pdf" ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
                        {generating === "pdf" ? "Generating…" : "Download PDF"}
                    </Button>
                    <Button variant="outline" onClick={() => generating === null && handleGenerate(true, "zip")} disabled={genDisabled}>
                        {generating === "with_copy" ? <Loader2 className="size-4 animate-spin" /> : <FileArchive className="size-4" />}
                        {generating === "with_copy" ? "Generating…" : `With Copy (${selectedCount}${validParties.length > 1 ? ` × ${validParties.length} parties` : ""})`}
                    </Button>
                    <Button variant="outline" onClick={() => generating === null && handleGenerate(false, "zip")} disabled={genDisabled}>
                        {generating === "without_copy" ? <Loader2 className="size-4 animate-spin" /> : <FileArchive className="size-4" />}
                        {generating === "without_copy" ? "Generating…" : `Without Copy (${selectedCount}${validParties.length > 1 ? ` × ${validParties.length} parties` : ""})`}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
