import { useState, useEffect } from 'react';
import api from '../api/axios';
import AsyncSelect from 'react-select/async';
import Select from 'react-select';
import { toast } from "sonner";
import { formatDate } from '../utils/dateFormatter';
import { openPdfPreview } from '../utils/pdfPreview';
import { openAuthedFile } from '../utils/documentDownload';
import ConditionBadge from './ConditionBadge';
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FileText, FileSpreadsheet, X, Loader2, Check, CheckCircle, Inbox, Package, PenSquare, Pencil, Plus } from "lucide-react";

const UNSAFE_PATH_SEGMENT_CHARS = new Set(["/", "?", "#", "\\"]);

// License Marking values map directly to the backend `condition_type` field.
// "" is rendered as "None" and clears the restriction.
const LICENSE_MARKING_OPTIONS = [
    { value: "",    label: "None" },
    { value: "AU",  label: "AU"   },
    { value: "10%", label: "10%"  },
    { value: "5%",  label: "5%"   },
    { value: "3%",  label: "3%"   },
    { value: "2%",  label: "2%"   },
];

export function toSafeLicensePathSegment(licenseId) {
    const value = String(licenseId ?? "").trim();
    const hasUnsafePathSegmentChar = [...value].some((char) => {
        const code = char.charCodeAt(0);
        return UNSAFE_PATH_SEGMENT_CHARS.has(char) || code < 32 || code === 127;
    });

    if (!value || hasUnsafePathSegmentChar) {
        throw new Error("A valid license id is required.");
    }

    return encodeURIComponent(value);
}

export function buildLicenseEndpoint(licenseId, suffix = "") {
    return `licenses/${toSafeLicensePathSegment(licenseId)}/${suffix}`;
}

export function formatFiniteDecimal(value, fractionDigits = 2) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(fractionDigits) : Number(0).toFixed(fractionDigits);
}

function normalizeArray(value) {
    return Array.isArray(value) ? value : [];
}

export function normalizeItemOptions(data) {
    return normalizeArray(data?.results)
        .filter((item) => item && item.id != null && item.name != null)
        .map((item) => ({
            value: item.id,
            label: String(item.name),
        }));
}

export function normalizeUsageData(data) {
    return {
        boes: normalizeArray(data?.boes),
        allotments: normalizeArray(data?.allotments),
    };
}

export function normalizeLicenseBalanceData(data) {
    if (!data || typeof data !== "object") {
        return null;
    }

    return {
        ...data,
        export_license: normalizeArray(data.export_license),
        import_license: normalizeArray(data.import_license),
    };
}

// Inline Editable Text Component
function InlineEditableText({ licenseId, text, fieldName, label, onUpdate }) {
    const [isEditing, setIsEditing] = useState(false);
    const [textValue, setTextValue] = useState(text);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setTextValue(text);
    }, [text]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.patch(`licenses/${licenseId}/`, {
                [fieldName]: textValue
            });
            onUpdate(textValue);
            setIsEditing(false);
            toast.success(`${label} saved successfully`);
        } catch (error) {
            console.error(`Error saving ${label}:`, error);
            toast.error(`Failed to save ${label}`);
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        setTextValue(text);
        setIsEditing(false);
    };

    return (
        <div>
            {isEditing ? (
                <div>
                    <textarea
                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm mb-2 outline-none focus-visible:border-ring"
                        rows={4}
                        value={textValue}
                        onChange={(e) => setTextValue(e.target.value)}
                        placeholder={`Enter ${label.toLowerCase()} here...`}
                        style={{
                            fontSize: 14,
                            borderColor: 'var(--primary-color)',
                            backgroundColor: 'var(--row-yellow-bg)'
                        }}
                    />
                    <div className="flex gap-2">
                        <button
                            className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90"
                            onClick={handleSave}
                            disabled={saving}
                            style={{
                                background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))',
                                border: 'none'
                            }}
                        >
                            <CheckCircle className="size-4 mr-1" />
                            {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                            onClick={handleCancel}
                            disabled={saving}
                        >
                            <X className="size-4 mr-1" />Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <div
                    onClick={() => setIsEditing(true)}
                    style={{
                        minHeight: '80px',
                        padding: '0.75rem',
                        backgroundColor: textValue ? 'var(--row-yellow-bg)' : 'var(--tb-sunken)',
                        border: '1px solid var(--tb-border)',
                        borderRadius: 'var(--tb-r-sm)',
                        cursor: 'pointer',
                        fontSize: 14,
                        whiteSpace: 'pre-wrap',
                        transition: 'all 0.2s'
                    }}
                    onMouseOver={(e) => {
                        e.currentTarget.style.borderColor = 'var(--primary-color)';
                        e.currentTarget.style.backgroundColor = textValue ? 'var(--row-yellow-bg)' : 'var(--tb-gray-100)';
                    }}
                    onMouseOut={(e) => {
                        e.currentTarget.style.borderColor = 'var(--tb-border)';
                        e.currentTarget.style.backgroundColor = textValue ? 'var(--row-yellow-bg)' : 'var(--tb-sunken)';
                    }}
                >
                    {textValue || <span style={{ color: 'var(--tb-text-secondary)', fontStyle: 'italic' }}>Click to add {label.toLowerCase()}...</span>}
                </div>
            )}
        </div>
    );
}

export default function LicenseBalanceModal({ show, onHide, licenseId }) {
    const [loading, setLoading] = useState(false);
    const [licenseData, setLicenseData] = useState(null);
    const [expandedItem, setExpandedItem] = useState(null);
    const [usageData, setUsageData] = useState(null);

    // Inline editing state
    const [editingItemId, setEditingItemId] = useState(null);
    const [editingItems, setEditingItems] = useState([]);
    const [saving, setSaving] = useState(false);
    // Row id currently showing the inline "add item tag" selector.
    const [addingItemId, setAddingItemId] = useState(null);
    // Row ids with an in-flight tag PATCH (disables the row's tag controls).
    const [tagSaving, setTagSaving] = useState({});

    useEffect(() => {
        const fetchLicenseData = async () => {
            setLoading(true);
            try {
                const { data } = await api.get(buildLicenseEndpoint(licenseId));
                const normalizedData = normalizeLicenseBalanceData(data);
                if (!normalizedData) {
                    throw new Error("Malformed license response");
                }
                setLicenseData(normalizedData);
            } catch (error) {
                console.error('Error fetching license data:', error);
                toast.error('Failed to load license data');
            } finally {
                setLoading(false);
            }
        };

        if (show && licenseId) {
            fetchLicenseData();
        }
    }, [show, licenseId]);

    const fetchItemUsage = async (item, type) => {
        try {
            const response = await api.get(buildLicenseEndpoint(licenseId, "item-usage/"), {
                params: {
                    item_id: item.id,
                    type: type
                }
            });
            setUsageData(normalizeUsageData(response.data));
        } catch (error) {
            toast.error('Failed to load usage details.');
            setUsageData(normalizeUsageData(null));
        }
    };

    const handleRowClick = (item, type) => {
        // Don't expand if we're editing
        if (editingItemId) return;

        if (expandedItem?.id === item.id) {
            setExpandedItem(null);
            setUsageData(null);
        } else {
            setExpandedItem({ ...item, type });
            fetchItemUsage(item, type);
        }
    };

    const loadItemOptions = async (inputValue) => {
        try {
            // Filter items by license's norm class (get_norm_class)
            const params: Record<string, any> = {
                search: inputValue,
                page_size: 50
            };

            // Add norm class filter if available
            if (licenseData?.get_norm_class) {
                params.norm_class = licenseData.get_norm_class;
            }

            const { data } = await api.get('masters/item-names/', {
                params
            });
            return normalizeItemOptions(data);
        } catch (error) {
            console.error('Error loading items:', error);
            return [];
        }
    };

    const handleEditClick = (e, item) => {
        e.stopPropagation();
        setEditingItemId(item.id);
        // Convert items_detail to react-select format
        const selectedItems = (item.items_detail || []).map(i => ({
            value: i.id,
            label: i.name
        }));
        setEditingItems(selectedItems);
    };

    const handleSaveItems = async (e, item) => {
        e.stopPropagation();
        setSaving(true);
        try {
            // Extract just the IDs
            const itemIds = editingItems.map(i => i.value);

            // Update only the specific item via the license-items endpoint
            // This prevents overriding other concurrent changes to the license
            await api.patch(`license-items/${item.id}/`, {
                items: itemIds
            });

            // Update local state without reloading
            setLicenseData(prevData => ({
                ...prevData,
                import_license: normalizeArray(prevData?.import_license).map(importItem => {
                    if (importItem.id === item.id) {
                        return {
                            ...importItem,
                            items: itemIds,
                            items_detail: editingItems.map(i => ({
                                id: i.value,
                                name: i.label
                            }))
                        };
                    }
                    return importItem;
                })
            }));

            toast.success('Items updated successfully');
            setEditingItemId(null);
        } catch (error) {
            console.error('Error updating items:', error);
            toast.error(error.response?.data?.detail || error.response?.data?.error || 'Failed to update items');
        } finally {
            setSaving(false);
        }
    };

    // Persist a row's item-name tags and update local state (no full reload).
    const patchItemTags = async (item, newDetails) => {
        const itemIds = newDetails.map((d) => d.id);
        const prevData = licenseData;
        // Optimistic update.
        setLicenseData((prev) => ({
            ...prev,
            import_license: normalizeArray(prev?.import_license).map((it) =>
                it.id === item.id ? { ...it, items: itemIds, items_detail: newDetails } : it),
        }));
        setTagSaving((s) => ({ ...s, [item.id]: true }));
        try {
            await api.patch(`license-items/${item.id}/`, { items: itemIds });
        } catch (error) {
            setLicenseData(prevData); // revert on failure
            toast.error(error.response?.data?.detail || error.response?.data?.error || 'Failed to update items');
        } finally {
            setTagSaving((s) => ({ ...s, [item.id]: false }));
        }
    };

    const handleRemoveItemTag = (e, item, tagId) => {
        e.stopPropagation();
        const newDetails = (item.items_detail || []).filter((d) => d.id !== tagId);
        patchItemTags(item, newDetails);
    };

    const handleAddItemTag = (item, option) => {
        setAddingItemId(null);
        if (!option) return;
        if ((item.items_detail || []).some((d) => d.id === option.value)) return; // already present
        const newDetails = [...(item.items_detail || []), { id: option.value, name: option.label }];
        patchItemTags(item, newDetails);
    };

    const handleConditionTypeChange = async (item, newValue) => {
        const previous = item.condition_type || "";
        if (previous === newValue) return;
        // Optimistic UI: update local state first; revert if the PATCH fails.
        setLicenseData(prev => ({
            ...prev,
            import_license: normalizeArray(prev?.import_license).map(it =>
                it.id === item.id ? { ...it, condition_type: newValue } : it
            ),
        }));
        try {
            await api.patch(`license-items/${item.id}/`, { condition_type: newValue });
            toast.success("License marking updated");
        } catch (err) {
            setLicenseData(prev => ({
                ...prev,
                import_license: normalizeArray(prev?.import_license).map(it =>
                    it.id === item.id ? { ...it, condition_type: previous } : it
                ),
            }));
            toast.error(
                err.response?.data?.detail ||
                err.response?.data?.condition_type?.[0] ||
                "Failed to update license marking"
            );
        }
    };

    const handleCancelEdit = (e) => {
        e.stopPropagation();
        setEditingItemId(null);
        setEditingItems([]);
    };

    const handleDownloadPDF = async () => {
        try {
            toast.info('Generating PDF file...');

            const response = await api.get(buildLicenseEndpoint(licenseId, "balance-pdf/"), {
                responseType: 'blob',
            });
            openPdfPreview(response.data, `${licenseData?.license_number || licenseId}-balance.pdf`);

            toast.success('PDF file is being generated!');
        } catch (error) {
            console.error('Error generating PDF:', error);
            toast.error(error?.response?.data?.error || 'Failed to generate PDF file');
        }
    };

    const handleDownloadExcel = async () => {
        try {
            toast.info('Generating Excel file...');

            // Download via the authenticated axios instance (Authorization header),
            // not a ?access_token= URL which leaks the JWT into logs/history.
            await openAuthedFile(
                buildLicenseEndpoint(licenseId, "balance-excel/"),
                `${licenseData?.license_number || licenseId}-balance.xlsx`,
            );

            toast.success('Excel file downloaded successfully!');
        } catch (error) {
            console.error('Error generating Excel:', error);
            toast.error('Failed to generate Excel file');
        }
    };

    if (!show) return null;

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent
                showCloseButton={false}
                className="flex max-h-[95vh] w-[98vw] max-w-[1920px] flex-col overflow-hidden p-0"
            >
                {/* Custom gradient header */}
                <div
                    className="flex shrink-0 items-center justify-between px-6 py-4 text-white"
                    style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' }}
                >
                    <h5 className="flex items-center gap-2 text-[1.15rem] font-semibold tracking-tight text-white">
                        <FileText className="size-5" />
                        License Balance Report{licenseData ? ` — ${licenseData.license_number}` : ''}
                    </h5>
                    <div className="flex items-center gap-2">
                        {licenseData && (
                            <>
                                <Button
                                    size="sm"
                                    onClick={handleDownloadPDF}
                                    disabled={loading}
                                    className="border border-white/30 bg-white/15 text-white hover:bg-white/25"
                                    variant="outline"
                                >
                                    <FileText className="size-3.5" />Download PDF
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleDownloadExcel}
                                    disabled={loading}
                                    className="border border-white/30 bg-white/15 text-white hover:bg-white/25"
                                    variant="outline"
                                >
                                    <FileSpreadsheet className="size-3.5" />Download Excel
                                </Button>
                            </>
                        )}
                        <button
                            type="button"
                            onClick={onHide}
                            aria-label="Close"
                            className="ml-1 flex size-8 items-center justify-center rounded-sm opacity-70 hover:opacity-100 cursor-pointer bg-transparent border-0 text-white"
                        >
                            <X className="size-4" />
                        </button>
                    </div>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto bg-muted/40" style={{ padding: '1.5rem' }}>
                        {loading || !licenseData ? (
                            <div className="flex flex-col items-center gap-2 py-10 text-center">
                                <Loader2 className="size-8 animate-spin text-primary" />
                                <p className="mt-2" style={{ color: 'var(--tb-text-secondary)' }}>Loading...</p>
                            </div>
                        ) : (
                            <>
                                {/* License Header Details */}
                                <div style={{
                                    backgroundColor: 'var(--tb-card-bg)',
                                    borderRadius: 'var(--tb-r-md)',
                                    padding: '1.5rem',
                                    marginBottom: '1.5rem',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                }}>
                                    <div className="table-responsive">
                                        <table className="table table-sm" style={{ marginBottom: '0', border: 'none' }}>
                                            <thead style={{ backgroundColor: 'var(--primary-color)', color: '#fff' }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>License Number</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>License Date</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>License Expiry Date</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>Exporter Name</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>Port Name</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr style={{ backgroundColor: 'var(--tb-sunken)' }}>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)', fontWeight: '500' }}>
                                                        <div className="flex items-center gap-2" style={{ flexWrap: 'nowrap' }}>
                                                            <span style={{ fontWeight: '600', color: 'var(--tb-text)' }}>
                                                                {licenseData.license_number || '-'}
                                                            </span>
                                                            {(licenseData.has_tl || licenseData.has_copy) && (
                                                                <a
                                                                    href="#"
                                                                    title="View merged documents"
                                                                    onClick={async (e) => {
                                                                        e.preventDefault();
                                                                        e.stopPropagation();
                                                                        try {
                                                                            const response = await api.get(buildLicenseEndpoint(licenseData.id, "merged-documents/"), {
                                                                                responseType: 'blob',
                                                                            });
                                                                            openPdfPreview(response.data, `${licenseData?.license_number || licenseData?.id}-copy.pdf`);
                                                                        } catch {
                                                                            toast.error('Failed to load merged documents');
                                                                        }
                                                                    }}
                                                                    style={{
                                                                        fontSize: 12,
                                                                        color: 'var(--success-color)',
                                                                        textDecoration: 'none',
                                                                        padding: '2px 6px',
                                                                        backgroundColor: 'var(--success-bg)',
                                                                        borderRadius: '3px',
                                                                        fontWeight: '500',
                                                                        transition: 'all 0.2s',
                                                                        whiteSpace: 'nowrap'
                                                                    }}
                                                                    onMouseOver={(e) => {
                                                                        (e.target as HTMLElement).style.backgroundColor = 'var(--success-border)';
                                                                        (e.target as HTMLElement).style.textDecoration = 'underline';
                                                                    }}
                                                                    onMouseOut={(e) => {
                                                                        (e.target as HTMLElement).style.backgroundColor = 'var(--success-bg)';
                                                                        (e.target as HTMLElement).style.textDecoration = 'none';
                                                                    }}
                                                                >
                                                                    Copy
                                                                </a>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.license_date ? formatDate(licenseData.license_date) : '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.license_expiry_date ? formatDate(licenseData.license_expiry_date) : '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.exporter_name || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.port_name || '-'}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table className="table table-sm" style={{ marginBottom: '0', border: 'none', marginTop: '0.5rem' }}>
                                            <thead style={{ backgroundColor: 'var(--primary-color)', color: '#fff' }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>Purchase Status</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>Balance CIF</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14 }}>Get Norm Class</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: 14, minWidth: '300px' }}>Latest Transfer</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr style={{ backgroundColor: 'var(--tb-sunken)' }}>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.purchase_status || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {formatFiniteDecimal(licenseData.balance_cif)}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.get_norm_class || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                        {licenseData.latest_transfer || '-'}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {/* Condition Sheet Section */}
                                <div className="mb-4" style={{
                                    backgroundColor: 'var(--tb-card-bg)',
                                    borderRadius: 'var(--tb-r-md)',
                                    padding: '1.5rem',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                }}>
                                    <div className="flex justify-between items-center mb-3">
                                        <h5 style={{
                                            color: 'var(--tb-text)',
                                            fontWeight: '600',
                                            borderBottom: '2px solid var(--tb-brand)',
                                            paddingBottom: '0.5rem',
                                            marginBottom: '0',
                                            flex: 1
                                        }}>
                                            <FileText className="size-4 mr-2" />
                                            Condition Sheet
                                        </h5>
                                    </div>
                                    <InlineEditableText
                                        licenseId={licenseId}
                                        text={licenseData.condition_sheet || ''}
                                        fieldName="condition_sheet"
                                        label="Condition Sheet"
                                        onUpdate={(newText) => {
                                            setLicenseData(prev => ({ ...prev, condition_sheet: newText }));
                                        }}
                                    />
                                </div>

                                {/* Notes Section */}
                                <div className="mb-4" style={{
                                    backgroundColor: 'var(--tb-card-bg)',
                                    borderRadius: 'var(--tb-r-md)',
                                    padding: '1.5rem',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                }}>
                                    <div className="flex justify-between items-center mb-3">
                                        <h5 style={{
                                            color: 'var(--tb-text)',
                                            fontWeight: '600',
                                            borderBottom: '2px solid var(--tb-brand)',
                                            paddingBottom: '0.5rem',
                                            marginBottom: '0',
                                            flex: 1
                                        }}>
                                            <PenSquare className="size-4 mr-2" />
                                            Notes
                                        </h5>
                                    </div>
                                    <InlineEditableText
                                        licenseId={licenseId}
                                        text={licenseData.balance_report_notes || ''}
                                        fieldName="balance_report_notes"
                                        label="Notes"
                                        onUpdate={(newText) => {
                                            setLicenseData(prev => ({ ...prev, balance_report_notes: newText }));
                                        }}
                                    />
                                </div>

                                {/* Export Items */}
                                {licenseData.export_license && licenseData.export_license.length > 0 && (
                                    <div className="mb-4" style={{
                                        backgroundColor: 'var(--tb-card-bg)',
                                        borderRadius: 'var(--tb-r-md)',
                                        padding: '1.5rem',
                                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                    }}>
                                        <h5 className="mb-3" style={{
                                            color: 'var(--tb-text)',
                                            fontWeight: '600',
                                            borderBottom: '2px solid var(--tb-brand)',
                                            paddingBottom: '0.5rem'
                                        }}>
                                            <Package className="size-4 mr-2" />
                                            Export Items
                                        </h5>
                                        <table className="table" style={{
                                            marginBottom: '0',
                                            border: 'none'
                                        }}>
                                            <thead style={{
                                                backgroundColor: 'var(--primary-color)',
                                                color: '#fff'
                                            }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Item</th>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Total CIF</th>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Balance CIF</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {licenseData.export_license.map((item, index) => (
                                                    <>
                                                        <tr
                                                            key={item.id}
                                                            onClick={() => handleRowClick(item, 'export')}
                                                            style={{
                                                                cursor: 'pointer',
                                                                backgroundColor: expandedItem?.id === item.id ? 'var(--indigo-50)' : index % 2 === 0 ? 'var(--tb-card-bg)' : 'var(--tb-sunken)',
                                                                transition: 'all 0.2s'
                                                            }}
                                                            onMouseOver={(e) => {
                                                                if (expandedItem?.id !== item.id) {
                                                                    e.currentTarget.style.backgroundColor = 'var(--indigo-100)';
                                                                }
                                                            }}
                                                            onMouseOut={(e) => {
                                                                if (expandedItem?.id !== item.id) {
                                                                    e.currentTarget.style.backgroundColor = index % 2 === 0 ? 'var(--tb-card-bg)' : 'var(--tb-sunken)';
                                                                }
                                                            }}
                                                        >
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                {item.description || item.norm_class_label || 'None'}
                                                            </td>
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                {formatFiniteDecimal(item.cif_fc ?? item.fob_fc)}
                                                            </td>
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                {formatFiniteDecimal(licenseData.balance_cif)}
                                                            </td>
                                                        </tr>
                                                        {expandedItem?.id === item.id && usageData && (
                                                            <tr>
                                                                <td colSpan={3}>
                                                                    <div className="p-3 bg-light">
                                                                        <h6>Usage Details:</h6>

                                                                        {/* BOE Table */}
                                                                        {usageData.boes && usageData.boes.length > 0 ? (
                                                                            <div className="mb-3">
                                                                                <strong>BOEs:</strong>
                                                                                <table className="table table-sm">
                                                                                    <thead>
                                                                                        <tr>
                                                                                            <th>BOE Number</th>
                                                                                            <th>Date</th>
                                                                                            <th>Port</th>
                                                                                            <th>Company</th>
                                                                                            <th>Qty</th>
                                                                                            <th>CIF $</th>
                                                                                            <th>CIF INR</th>
                                                                                        </tr>
                                                                                    </thead>
                                                                                    <tbody>
                                                                                        {usageData.boes.map((boe) => (
                                                                                            <tr key={boe.id}>
                                                                                                <td>{boe.bill_of_entry_number}</td>
                                                                                                <td>{boe.date ? formatDate(boe.date) : '-'}</td>
                                                                                                <td>{boe.port || '-'}</td>
                                                                                                <td>{boe.company || '-'}</td>
                                                                                                <td>{formatFiniteDecimal(boe.quantity)}</td>
                                                                                                <td>{formatFiniteDecimal(boe.cif_fc)}</td>
                                                                                                <td>{formatFiniteDecimal(boe.cif_inr)}</td>
                                                                                            </tr>
                                                                                        ))}
                                                                                    </tbody>
                                                                                </table>
                                                                            </div>
                                                                        ) : (
                                                                            <p className="text-muted">No BOE usage found</p>
                                                                        )}

                                                                        {/* Allotment Table */}
                                                                        {usageData.allotments && usageData.allotments.length > 0 && (
                                                                            <div>
                                                                                <strong>Allotments:</strong>
                                                                                <table className="table table-sm">
                                                                                    <thead>
                                                                                        <tr>
                                                                                            <th>Company</th>
                                                                                            <th>Qty</th>
                                                                                            <th>CIF $</th>
                                                                                            <th>CIF INR</th>
                                                                                        </tr>
                                                                                    </thead>
                                                                                    <tbody>
                                                                                        {usageData.allotments.map((allotment) => (
                                                                                            <tr key={allotment.id}>
                                                                                                <td>{allotment.company || '-'}</td>
                                                                                                <td>{formatFiniteDecimal(allotment.quantity)}</td>
                                                                                                <td>{formatFiniteDecimal(allotment.cif_fc)}</td>
                                                                                                <td>{formatFiniteDecimal(allotment.cif_inr)}</td>
                                                                                            </tr>
                                                                                        ))}
                                                                                    </tbody>
                                                                                </table>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        )}
                                                    </>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}

                                {/* Import Items */}
                                {licenseData.import_license && licenseData.import_license.length > 0 && (
                                    <div style={{
                                        backgroundColor: 'var(--tb-card-bg)',
                                        borderRadius: 'var(--tb-r-md)',
                                        padding: '1.5rem',
                                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                    }}>
                                        <h5 className="mb-3" style={{
                                            color: 'var(--tb-text)',
                                            fontWeight: '600',
                                            borderBottom: '2px solid var(--tb-brand)',
                                            paddingBottom: '0.5rem'
                                        }}>
                                            <Inbox className="size-4 mr-2" />
                                            Import Items
                                        </h5>
                                        <div className="table-responsive">
                                            <table className="table table-sm" style={{
                                                marginBottom: '0',
                                                border: 'none'
                                            }}>
                                                <thead style={{
                                                    backgroundColor: 'var(--primary-dark)',
                                                    color: '#fff'
                                                }}>
                                                    <tr>
                                                        <th style={{ minWidth: '50px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Sr No</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>HS Code</th>
                                                        <th style={{ minWidth: '200px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Description</th>
                                                        <th style={{ minWidth: '250px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Item</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Total Quantity</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Allotted Qty</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Debited Qty</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Available Qty</th>
                                                        <th style={{ minWidth: '120px', border: 'none', padding: '0.75rem', fontSize: 14 }}>License Marking</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>CIF FC</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: 14 }}>Balance CIF FC</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {licenseData.import_license.map((item, index) => (
                                                        <>
                                                            <tr
                                                                key={item.id}
                                                                onClick={() => handleRowClick(item, 'import')}
                                                                style={{
                                                                    cursor: editingItemId ? 'default' : 'pointer',
                                                                    backgroundColor: expandedItem?.id === item.id ? 'var(--indigo-50)' : index % 2 === 0 ? 'var(--tb-card-bg)' : 'var(--tb-sunken)',
                                                                    transition: 'all 0.2s'
                                                                }}
                                                                onMouseOver={(e) => {
                                                                    if (expandedItem?.id !== item.id && !editingItemId) {
                                                                        e.currentTarget.style.backgroundColor = 'var(--indigo-100)';
                                                                    }
                                                                }}
                                                                onMouseOut={(e) => {
                                                                    if (expandedItem?.id !== item.id) {
                                                                        e.currentTarget.style.backgroundColor = index % 2 === 0 ? 'var(--tb-card-bg)' : 'var(--tb-sunken)';
                                                                    }
                                                                }}
                                                            >
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {item.serial_number || index + 1}
                                                                    <ConditionBadge type={item.condition_type} size="xs" />
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {item.hs_code_label || item.hs_code || '-'}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {item.description || '-'}
                                                                </td>
                                                                <td onClick={(e) => e.stopPropagation()} style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {editingItemId === item.id ? (
                                                                        <div className="flex items-center gap-1">
                                                                            <AsyncSelect
                                                                                isMulti
                                                                                cacheOptions
                                                                                defaultOptions
                                                                                value={editingItems}
                                                                                loadOptions={loadItemOptions}
                                                                                onChange={(v) => setEditingItems(v as any[])}
                                                                                placeholder="Select items..."
                                                                                className="flex-grow-1"
                                                                                menuPortalTarget={document.body}
                                                                                menuPosition="fixed"
                                                                                styles={{
                                                                                    control: (base) => ({
                                                                                        ...base,
                                                                                        minHeight: '32px',
                                                                                        fontSize: 14,
                                                                                        minWidth: '400px'
                                                                                    }),
                                                                                    valueContainer: (base) => ({
                                                                                        ...base,
                                                                                        flexWrap: 'wrap',
                                                                                        maxHeight: '100px',
                                                                                        overflow: 'auto'
                                                                                    }),
                                                                                    multiValue: (base) => ({
                                                                                        ...base,
                                                                                        maxWidth: '100%'
                                                                                    }),
                                                                                    multiValueLabel: (base) => ({
                                                                                        ...base,
                                                                                        whiteSpace: 'normal',
                                                                                        wordBreak: 'break-word',
                                                                                        padding: '3px 6px'
                                                                                    }),
                                                                                    menuPortal: (base) => ({
                                                                                        ...base,
                                                                                        zIndex: 9999
                                                                                    }),
                                                                                    menu: (base) => ({
                                                                                        ...base,
                                                                                        minWidth: '400px',
                                                                                        width: 'max-content'
                                                                                    }),
                                                                                    option: (base) => ({
                                                                                        ...base,
                                                                                        whiteSpace: 'nowrap'
                                                                                    })
                                                                                }}
                                                                            />
                                                                            <button
                                                                                className="flex items-center gap-1.5 rounded bg-success px-2.5 py-1 text-xs font-medium text-white cursor-pointer"
                                                                                onClick={(e) => handleSaveItems(e, item)}
                                                                                disabled={saving}
                                                                            >
                                                                                <Check className="size-4" />
                                                                            </button>
                                                                            <button
                                                                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                                onClick={handleCancelEdit}
                                                                                disabled={saving}
                                                                            >
                                                                                <X className="size-4" />
                                                                            </button>
                                                                        </div>
                                                                    ) : (
                                                                        <div className="flex flex-wrap items-center gap-1" style={{ minWidth: 220 }}>
                                                                            {(item.items_detail || []).map((d) => (
                                                                                <span key={d.id} className="chip chip-neutral inline-flex items-center gap-1" style={{ paddingRight: 4 }}>
                                                                                    {d.name}
                                                                                    <button
                                                                                        onClick={(e) => handleRemoveItemTag(e, item, d.id)}
                                                                                        disabled={tagSaving[item.id]}
                                                                                        className="hover:text-red-600 cursor-pointer"
                                                                                        title={`Remove ${d.name}`}
                                                                                    >
                                                                                        <X className="size-3" />
                                                                                    </button>
                                                                                </span>
                                                                            ))}
                                                                            {(item.items_detail || []).length === 0 && addingItemId !== item.id && (
                                                                                <span className="text-muted-foreground">-</span>
                                                                            )}
                                                                            {addingItemId === item.id ? (
                                                                                <div onClick={(e) => e.stopPropagation()} style={{ minWidth: 220 }}>
                                                                                    <AsyncSelect
                                                                                        autoFocus
                                                                                        cacheOptions
                                                                                        defaultOptions
                                                                                        loadOptions={loadItemOptions}
                                                                                        onChange={(opt) => handleAddItemTag(item, opt as any)}
                                                                                        onBlur={() => setAddingItemId(null)}
                                                                                        placeholder="Add item…"
                                                                                        menuPortalTarget={document.body}
                                                                                        menuPosition="fixed"
                                                                                        styles={{
                                                                                            control: (base) => ({ ...base, minHeight: '32px', fontSize: 14, minWidth: '220px' }),
                                                                                            menuPortal: (base) => ({ ...base, zIndex: 9999 }),
                                                                                            menu: (base) => ({ ...base, minWidth: '260px', width: 'max-content' }),
                                                                                            option: (base) => ({ ...base, whiteSpace: 'nowrap' }),
                                                                                        }}
                                                                                    />
                                                                                </div>
                                                                            ) : (
                                                                                <>
                                                                                    <button
                                                                                        onClick={(e) => { e.stopPropagation(); setAddingItemId(item.id); }}
                                                                                        disabled={tagSaving[item.id]}
                                                                                        className="chip chip-primary inline-flex items-center gap-1 cursor-pointer border-0"
                                                                                        title="Add item"
                                                                                    >
                                                                                        <Plus className="size-3" />Add
                                                                                    </button>
                                                                                    <button
                                                                                        onClick={(e) => handleEditClick(e, item)}
                                                                                        className="text-muted-foreground hover:text-foreground cursor-pointer ml-0.5"
                                                                                        title="Edit all item tags"
                                                                                    >
                                                                                        <Pencil className="size-3.5" />
                                                                                    </button>
                                                                                </>
                                                                            )}
                                                                            {tagSaving[item.id] && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
                                                                        </div>
                                                                    )}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.quantity)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.allotted_quantity)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.debited_quantity)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.available_quantity)}
                                                                </td>
                                                                <td
                                                                    onClick={(e) => e.stopPropagation()}
                                                                    style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)', textAlign: 'center' }}
                                                                >
                                                                    {/* Editable license marking — writes to backend `condition_type`. */}
                                                                    <Select
                                                                        options={LICENSE_MARKING_OPTIONS}
                                                                        value={LICENSE_MARKING_OPTIONS.find(o => o.value === (item.condition_type || ""))}
                                                                        onChange={(sel) => handleConditionTypeChange(item, sel?.value ?? "")}
                                                                        isSearchable={false}
                                                                        menuPortalTarget={document.body}
                                                                        menuPosition="fixed"
                                                                        styles={{
                                                                            control: (base) => ({
                                                                                ...base,
                                                                                minHeight: '32px',
                                                                                fontSize: 12.5,
                                                                                minWidth: '110px',
                                                                            }),
                                                                            valueContainer: (base) => ({
                                                                                ...base,
                                                                                padding: '0 6px',
                                                                            }),
                                                                            indicatorsContainer: (base) => ({
                                                                                ...base,
                                                                                height: '30px',
                                                                            }),
                                                                            menuPortal: (base) => ({
                                                                                ...base,
                                                                                zIndex: 9999,
                                                                            }),
                                                                            menu: (base) => ({
                                                                                ...base,
                                                                                fontSize: 12.5,
                                                                            }),
                                                                        }}
                                                                    />
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.cif_fc)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: 14, border: 'none', borderBottom: '1px solid var(--tb-border-soft)' }}>
                                                                    {formatFiniteDecimal(item.balance_cif_fc)}
                                                                </td>
                                                            </tr>
                                                            {expandedItem?.id === item.id && usageData && (
                                                                <tr>
                                                                    <td colSpan={11}>
                                                                        <div className="p-3 bg-light">
                                                                            <h6>Usage Details:</h6>

                                                                            {/* BOE Table */}
                                                                            {usageData.boes && usageData.boes.length > 0 ? (
                                                                                <div className="mb-3">
                                                                                    <strong>BOEs:</strong>
                                                                                    <table className="table table-sm">
                                                                                        <thead>
                                                                                            <tr>
                                                                                                <th>BOE Number</th>
                                                                                                <th>Date</th>
                                                                                                <th>Port</th>
                                                                                                <th>Company</th>
                                                                                                <th>Qty</th>
                                                                                                <th>CIF $</th>
                                                                                                <th>CIF INR</th>
                                                                                            </tr>
                                                                                        </thead>
                                                                                        <tbody>
                                                                                            {usageData.boes.map((boe) => (
                                                                                                <tr key={boe.id}>
                                                                                                    <td>{boe.bill_of_entry_number}</td>
                                                                                                    <td>{boe.date ? formatDate(boe.date) : '-'}</td>
                                                                                                    <td>{boe.port || '-'}</td>
                                                                                                    <td>{boe.company || '-'}</td>
                                                                                                    <td>{formatFiniteDecimal(boe.quantity)}</td>
                                                                                                    <td>{formatFiniteDecimal(boe.cif_fc)}</td>
                                                                                                    <td>{formatFiniteDecimal(boe.cif_inr)}</td>
                                                                                                </tr>
                                                                                            ))}
                                                                                        </tbody>
                                                                                    </table>
                                                                                </div>
                                                                            ) : (
                                                                                <p className="text-muted mb-2">No BOE usage found</p>
                                                                            )}

                                                                            {/* Allotment Table */}
                                                                            {usageData.allotments && usageData.allotments.length > 0 ? (
                                                                                <div>
                                                                                    <strong>Allotments:</strong>
                                                                                    <table className="table table-sm">
                                                                                        <thead>
                                                                                            <tr>
                                                                                                <th>Company</th>
                                                                                                <th>Qty</th>
                                                                                                <th>CIF $</th>
                                                                                                <th>CIF INR</th>
                                                                                            </tr>
                                                                                        </thead>
                                                                                        <tbody>
                                                                                            {usageData.allotments.map((allotment) => (
                                                                                                <tr key={allotment.id}>
                                                                                                    <td>{allotment.company || '-'}</td>
                                                                                                    <td>{formatFiniteDecimal(allotment.quantity)}</td>
                                                                                                    <td>{formatFiniteDecimal(allotment.cif_fc)}</td>
                                                                                                    <td>{formatFiniteDecimal(allotment.cif_inr)}</td>
                                                                                                </tr>
                                                                                            ))}
                                                                                        </tbody>
                                                                                    </table>
                                                                                </div>
                                                                            ) : (
                                                                                <p className="text-muted mb-2">No Allotment usage found</p>
                                                                            )}

                                                                            {/* Balance Calculation */}
                                                                            <div className="mt-3 pt-2 border-top">
                                                                                <strong>Balance Calculation:</strong>
                                                                                <div className="ms-3 mt-2">
                                                                                    <div className="row">
                                                                                        <div className="flex-1">
                                                                                            <small className="text-muted">
                                                                                                Balance Quantity = Total Quantity - Debited Qty - Allotted Qty
                                                                                            </small>
                                                                                        </div>
                                                                                        <div className="flex-1 text-right">
                                                                                            <strong>
                                                                                                Balance: {formatFiniteDecimal(
                                                                                                    Number(item.quantity || 0) -
                                                                                                    Number(item.debited_quantity || 0) -
                                                                                                    Number(item.allotted_quantity || 0)
                                                                                                )}
                                                                                            </strong>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            )}
                                                        </>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                <div className="flex justify-end border-t border-border bg-muted/40 px-6 py-3">
                    <Button variant="outline" onClick={onHide}>
                        <X className="size-4" />Close
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
