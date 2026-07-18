import { useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import api from "../../api/axios";
import { openDocument, toProtectedMediaPath } from "../../utils/documentDownload";
import AuthedImage from "../../components/AuthedImage";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { formatDateForInput, parseDate as parseDateUtil } from "../../utils/dateFormatter";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import { navigateToList } from "../../utils/navigationUtils";
import { useBackButton } from "../../hooks/useBackButton";
import { ENTITY_SECTIONS } from "./entitySections";
import { buildLicensePatch, buildLicenseSummary } from "./masterFormHelpers";
import LicenseParsePanel from "./LicenseParsePanel";
import TradeMetaBadges from "./TradeMetaBadges";
import BoeParsePanel from "./BoeParsePanel";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { AlertCircle, ArrowLeft, ArrowLeftRight, Award, Check, CheckCircle, ExternalLink, Eye, FileText, Info, Loader2, MoreHorizontal, PackagePlus, Receipt, Table, TriangleAlert, Wand2, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useMasterFormData } from "./hooks/useMasterFormData";
import { useMasterFormCalculations } from "./hooks/useMasterFormCalculations";
import { useMasterFormSubmit } from "./hooks/useMasterFormSubmit";

/**
 * Generic Master Form for Create/Edit
 *
 * URL Pattern:
 * - Create: /masters/:entity/create OR /licenses/create
 * - Edit: /masters/:entity/:id/edit OR /licenses/:id/edit
 */

interface MasterFormProps {
    entityName?: string;
    recordId?: string | number;
    isModal?: boolean;
    onClose?: () => void;
    onSuccess?: (id: number | string) => void;
}

export default function MasterForm({
    entityName: propEntityName,
    recordId: propRecordId,
    isModal = false,
    onClose,
    onSuccess
}: MasterFormProps) {
    const { entity, id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    // Use prop values if provided (for modal), otherwise use URL params (for page)
    const entityName = propEntityName || entity ||
        (location.pathname.includes('/licenses') ? 'licenses' : null) ||
        (location.pathname.includes('/allotments') ? 'allotments' : null) ||
        (location.pathname.includes('/bill-of-entries') ? 'bill-of-entries' : null) ||
        (location.pathname.includes('/trades') ? 'trades' : null) ||
        (location.pathname.includes('/incentive-licenses') ? 'incentive-licenses' : null);
    const recordId = propRecordId || id;
    const isEdit = Boolean(recordId);

    // PDF parse panel state (owned by MasterForm — drives panel JSX directly)
    const [boePdfFile, setBoePdfFile] = useState<File | null>(null);
    const [boeParsing, setBoeParsing] = useState(false);
    const [boeParseSummary, setBoeParseSummary] = useState<any>(null);
    const [licensePdfFile, setLicensePdfFile] = useState<File | null>(null);
    const [licenseParsing, setLicenseParsing] = useState(false);
    const [licenseParseSummary, setLicenseParseSummary] = useState<any>(null);

    // Modal state
    const [showBalanceModal, setShowBalanceModal] = useState(false);
    const [savedLicenseId, setSavedLicenseId] = useState<any>(null);

    // UI loading indicator for allotment fetch (owned here because it drives Alert JSX)
    const [fetchingAllotment, setFetchingAllotment] = useState(false);

    // Submit state (saving drives the submit button and must be read in JSX)
    const [saving, setSaving] = useState(false);
    const [fieldErrors, setFieldErrors] = useState<Record<string, any>>({});

    // Use centralized date parser from utility
    const parseDate = (dateString: any) => parseDateUtil(dateString);

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date: any) => {
        if (!date) return null;
        return formatDateForInput(date);
    };

    // Enable browser back button support with filter preservation
    useBackButton(entityName, !isModal);

    // ---------- applyLicenseParse (PDF callback needed by useMasterFormData) ----------
    // Defined before the data hook so it can be passed as a stable callback reference.
    // It closes over setFormData / setUpdatedFields / setItemConditionsBySerial /
    // setActiveNestedTab / setLicenseParseSummary which come from the data hook.
    // We use a ref-forwarding pattern: initialise a placeholder, then reassign after
    // the hook provides the setters. React guarantees the same setter identities
    // across renders, so this is safe.
    const applyLicenseParseRef = { fn: (_data: any, _fileOverride?: File | null, _opts?: Record<string, any>) => {} };

    // ---------- Hook 1: data fetching ----------
    const {
        formData,
        setFormData,
        metadata,
        loading,
        error,
        setError,
        updatedFields,
        setUpdatedFields,
        activeNestedTab,
        setActiveNestedTab,
        itemConditionsBySerial,
        setItemConditionsBySerial,
    } = useMasterFormData({
        entityName,
        recordId,
        isEdit,
        location,
        navigate,
        applyLicenseParse: (data, fileOverride, opts) => applyLicenseParseRef.fn(data, fileOverride, opts),
        setLicensePdfFile,
    });

    // ---------- Hook 2: field change calculations ----------
    const { handleChange, handleFetchImports } = useMasterFormCalculations({
        entityName,
        formData,
        setFormData,
        setUpdatedFields,
        setFetchingAllotment,
    });

    // applyLicenseParse — defined after hooks so it can close over hook setters
    const applyLicenseParse = (data: Record<string, any>, fileOverride?: File | null, opts: Record<string, any> = {}) => {
        const { patch, importRows, conditionBySerial, exportFinancials } = buildLicensePatch(data);
        // `skipAttach` is set when re-parsing from a Licence Copy already
        // stored on the licence — we don't want to attach a duplicate.
        const fileToAttach = opts.skipAttach ? null : (fileOverride || licensePdfFile);
        if (conditionBySerial && Object.keys(conditionBySerial).length > 0) {
            setItemConditionsBySerial(prev => ({ ...prev, ...conditionBySerial }));
        }
        setFormData(prev => {
            const next = { ...prev, ...patch };

            // Merge financial totals into the existing first Export row
            // (preserves user-entered Description / Norm Class / Net Quantity).
            // If no export row exists yet, create a fresh one.
            if (exportFinancials) {
                const existingExports = Array.isArray(prev.export_license) ? prev.export_license : [];
                if (existingExports.length > 0) {
                    const merged = existingExports.map((row: any, i: number) =>
                        i === 0 ? { ...row, ...exportFinancials } : row
                    );
                    next.export_license = merged;
                } else {
                    next.export_license = [{
                        description: "",
                        norm_class: null,
                        start_serial_number: 0,
                        net_quantity: 0,
                        currency: "usd",
                        ...exportFinancials,
                    }];
                }
            }

            // Attach the uploaded PDF as a "LICENSE COPY" document, but only
            // if no LICENSE COPY is already saved on this record.
            if (fileToAttach) {
                const existing = prev.license_documents || [];
                const hasLicenseCopy = existing.some((d: any) => {
                    const t = (d.type || "").toUpperCase();
                    return t === "LICENSE COPY" && (d.id || d.file);
                });
                if (!hasLicenseCopy) {
                    next.license_documents = [
                        ...existing,
                        { type: "LICENSE COPY", file: fileToAttach },
                    ];
                }
            }
            return next;
        });
        setUpdatedFields(prev => ({
            ...prev,
            ...Object.keys(patch).reduce<Record<string, boolean>>((acc, k) => { acc[k] = true; return acc; }, {}),
            ...(fileToAttach ? { license_documents: true } : {}),
            ...(exportFinancials ? { export_license: true } : {}),
        }));
        if (importRows.length > 0) {
            setActiveNestedTab('import_license');
        }
        setLicenseParseSummary(buildLicenseSummary(data));

        const summary = buildLicenseSummary(data);
        const bits = [`Licence ${summary.license_number} parsed`];
        if (summary.company_created) bits.push("new company created");
        else if (summary.matched_company_id) bits.push("company matched");
        bits.push(`${(data.items || []).length} import item(s)`);
        if (summary.unmatchedHsn > 0) bits.push(`${summary.unmatchedHsn} HSN(s) not in master`);
        toast.success(bits.join(" · "));
    };

    // Wire the ref so fetchRecord can call applyLicenseParse
    applyLicenseParseRef.fn = applyLicenseParse;

    const entityTitle = entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    // ---------- Hook 3: form submit ----------
    const { handleSubmit } = useMasterFormSubmit({
        entityName,
        recordId,
        isEdit,
        isModal,
        formData,
        metadata,
        boePdfFile,
        entityTitle,
        onSuccess,
        onClose,
        navigate,
        setSaving,
        setError,
        setFieldErrors,
    });

    // ---------- BOE / License PDF parse panel handlers ----------
    const handleParseBoePdf = async () => {
        if (!boePdfFile) {
            toast.error("Please choose a BOE PDF first");
            return;
        }
        setBoeParsing(true);
        setBoeParseSummary(null);

        // Auto-save the current BOE before overwriting fields with parsed data,
        // so the original state is preserved on the server as a recoverable copy.
        if (isEdit && entityName === 'bill-of-entries') {
            try {
                const snapshot = { ...formData };
                delete snapshot.created_on;
                delete snapshot.created_by;
                delete snapshot.modified_on;
                delete snapshot.modified_by;
                await api.patch(`bill-of-entries/${recordId}/`, snapshot);
                toast.info("BOE saved before fetch");
            } catch {
                // Non-blocking — proceed with fetch even if auto-save fails
            }
        }

        try {
            const fd = new FormData();
            fd.append("file", boePdfFile);
            const { data } = await api.post("bill-of-entries/parse-pdf/", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            const { parsed, prefill, matched_allotment_id, matched_company_id, matched_port_id, company_created, licences } = data;

            // Build patch — only fields we successfully extracted/matched
            const patch: Record<string, any> = {};
            if (parsed.be_number) patch.bill_of_entry_number = parsed.be_number;
            if (parsed.be_date) patch.bill_of_entry_date = parsed.be_date;
            if (matched_company_id) patch.company = parseInt(matched_company_id, 10);
            if (matched_port_id) patch.port = parseInt(matched_port_id, 10);
            if (matched_allotment_id) patch.allotment = [matched_allotment_id];
            if (prefill.exchange_rate) patch.exchange_rate = String(prefill.exchange_rate);
            if (parsed.item_description) patch.product_name = parsed.item_description;

            // Build BOE item_details rows from matched licence rows.
            // Multiple licence rows that point to the same license item (same
            // sr_number) are summed into a single row — the BOE form should
            // carry the total CIF/qty per license item, not duplicates.
            const matchedRows = (licences || []).filter((l: any) => l.match_status === 'matched' && l.matched_item_id);
            if (matchedRows.length > 0) {
                const toNum = (v: any) => {
                    if (v === null || v === undefined || v === '') return 0;
                    const n = parseFloat(v);
                    return isNaN(n) ? 0 : n;
                };
                const byItem = new Map<number, any>();
                for (const l of matchedRows) {
                    const key = parseInt(l.matched_item_id, 10);
                    const existing = byItem.get(key) || { sr_number: key, cif_inr: 0, cif_fc: 0, qty: 0 };
                    existing.cif_inr += toNum(l.cif_inr);
                    existing.cif_fc  += toNum(l.cif_fc);
                    existing.qty     += toNum(l.qty);
                    byItem.set(key, existing);
                }
                // Round to 2dp / 3dp like the form expects
                patch.item_details = Array.from(byItem.values()).map(r => ({
                    sr_number: r.sr_number,
                    cif_inr: Number(r.cif_inr.toFixed(2)),
                    cif_fc:  Number(r.cif_fc.toFixed(2)),
                    qty:     Number(r.qty.toFixed(3)),
                }));
            }

            setFormData(prev => ({ ...prev, ...patch }));
            // Highlight updated fields briefly
            setUpdatedFields(prev => ({
                ...prev,
                ...Object.keys(patch).reduce<Record<string, boolean>>((acc, k) => { acc[k] = true; return acc; }, {}),
            }));

            const unmatched = (licences || []).filter((l: any) => l.match_status !== 'matched').length;
            setBoeParseSummary({
                be_number: parsed.be_number,
                be_date: parsed.be_date,
                port_code: parsed.port_code,
                currency: parsed.currency,
                exchange_rate: prefill.exchange_rate,
                company_created,
                matched_allotment_id,
                matched_company_id,
                buyer_name: parsed.buyer_name,
                licences: licences || [],
                unmatched,
            });

            const bits = [`BOE ${parsed.be_number || ""} parsed`];
            if (company_created) bits.push("new company created");
            if (matched_allotment_id) bits.push(`matched allotment #${matched_allotment_id}`);
            bits.push(`${(licences || []).length} licence row(s), ${unmatched} unmatched`);
            toast.success(bits.join(" · "));
        } catch (err: any) {
            console.error("BOE parse error", err);
            const msg = err?.response?.data?.detail || "Failed to parse BOE PDF";
            toast.error(msg);
        } finally {
            setBoeParsing(false);
        }
    };

    const handleParseLicensePdf = async () => {
        if (!licensePdfFile) {
            toast.error("Please choose a Licence PDF first");
            return;
        }
        setLicenseParsing(true);
        setLicenseParseSummary(null);

        try {
            const fd = new FormData();
            fd.append("file", licensePdfFile);
            const { data } = await api.post("licenses/parse-pdf/", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            // If we're on the create page and the licence already exists,
            // auto-redirect to that existing licence's edit page and re-apply
            // the parsed data there so the user can update without re-uploading.
            if (!isEdit && data.existing_license_id) {
                toast.info(
                    `Licence ${data.parsed?.license_number} already exists — opening it for edit.`
                );
                navigate(`/licenses/${data.existing_license_id}/edit`, {
                    state: {
                        licenseParseData: data,
                        // history.pushState uses structured cloning which
                        // preserves File objects across navigation.
                        licensePdfFile: licensePdfFile,
                    },
                });
                return;
            }

            applyLicenseParse(data);
        } catch (err: any) {
            console.error("Licence parse error", err);
            const msg = err?.response?.data?.detail || "Failed to parse Licence PDF";
            toast.error(msg);
        } finally {
            setLicenseParsing(false);
        }
    };

    // If the licence already has a "LICENSE COPY" document attached, expose it
    // so the form can offer a "Re-fetch & parse" shortcut for old records.
    const existingLicenseCopy = useMemo(() => {
        if (entityName !== "licenses" || !isEdit) return null;
        const docs = Array.isArray(formData.license_documents) ? formData.license_documents : [];
        return docs.find((d: any) => {
            const t = (d?.type || "").toUpperCase();
            return t === "LICENSE COPY" && d?.id && d?.file;
        }) || null;
    }, [entityName, isEdit, formData.license_documents]);

    const existingLicenseCopyName = useMemo(() => {
        if (!existingLicenseCopy?.file) return "";
        const url = String(existingLicenseCopy.file);
        const base = (url.split("?")[0].split("/").pop() || "license-copy.pdf");
        try { return decodeURIComponent(base); } catch { return base; }
    }, [existingLicenseCopy]);

    const handleReparseExistingCopy = async () => {
        if (!existingLicenseCopy?.file) {
            toast.error("No saved Licence Copy found on this record");
            return;
        }
        setLicenseParsing(true);
        setLicenseParseSummary(null);
        try {
            // Fetch the saved copy through the authenticated media endpoint
            // (axios attaches the Bearer header) rather than the public /media/ URL.
            const resp = await api.get(toProtectedMediaPath(existingLicenseCopy.file), { responseType: "blob" });
            const blob = resp.data as Blob;
            const file = new File(
                [blob],
                existingLicenseCopyName || "license-copy.pdf",
                { type: blob.type || "application/pdf" },
            );

            const fd = new FormData();
            fd.append("file", file);
            const { data } = await api.post("licenses/parse-pdf/", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            // Apply the parse without attaching a duplicate LICENSE COPY.
            applyLicenseParse(data, null, { skipAttach: true });
            toast.success("Re-parsed from saved Licence Copy");
        } catch (err: any) {
            console.error("Re-parse error", err);
            const msg = err?.response?.data?.detail || err?.message || "Failed to re-fetch & parse the saved Licence Copy";
            toast.error(msg);
        } finally {
            setLicenseParsing(false);
        }
    };

    const handleModalClose = () => {
        setShowBalanceModal(false);
    };

    const ENTITY_ICON_MAP: Record<string, any> = {
        licenses: FileText,
        allotments: PackagePlus,
        'bill-of-entries': Receipt,
        trades: ArrowLeftRight,
        'incentive-licenses': Award,
    };
    const EntityIcon = ENTITY_ICON_MAP[entityName as string] || FileText;
    const entityColorMap: Record<string, string> = {
        licenses: 'var(--tb-brand)',
        allotments: 'var(--tb-info)',
        'bill-of-entries': 'var(--tb-brand)',
        trades: 'var(--tb-success)',
        'incentive-licenses': 'var(--tb-warning)',
    };
    const entityColor = entityColorMap[entityName as string] || 'var(--tb-brand)';

    const renderField = (fieldName: string, fieldId?: string) => {
        const fieldMeta = metadata.field_meta?.[fieldName] || {};

        // For m2m fields, default to empty array instead of empty string
        let value = formData[fieldName];
        if (value === undefined || value === null) {
            value = (fieldMeta.type === "m2m" || fieldMeta.type === "fk_multi") ? [] : "";
        }

        // Check if field has error
        const fieldError = fieldErrors[fieldName];
        const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);
        const errorClass = hasError ? 'is-invalid' : '';

        // Handle date fields with DatePicker
        if (fieldMeta.type === "date" || fieldName.includes("date") || fieldName.includes("_at") || fieldName.includes("_on")) {
            return (
                <div className="w-full">
                    {/* @ts-expect-error DatePicker onChange type mismatch */}
                    <DatePicker
                        id={fieldId}
                        selected={parseDate(value)}
                        onChange={(date) => handleChange(fieldName, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className={cn("flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] focus-visible:border-ring aria-invalid:border-destructive", errorClass)}
                        wrapperClassName="w-full block"
                        placeholderText="Select date"
                        isClearable
                        showYearDropdown
                        showMonthDropdown
                        dropdownMode="select"
                    />
                </div>
            );
        }

        // Handle FK Select fields or fields with choices using HybridSelect
        if (fieldMeta.type === "select" || fieldMeta.endpoint || fieldMeta.fk_endpoint || fieldMeta.choices) {
            // Check if it's a many-to-many field from metadata or if value is array
            const isMulti = fieldMeta.type === "m2m" || fieldMeta.type === "fk_multi" || Array.isArray(value);

            return (
                <HybridSelect
                    fieldMeta={fieldMeta}
                    value={value}
                    onChange={(val) => handleChange(fieldName, val)}
                    isMulti={isMulti}
                    placeholder={`Select ${fieldName.replace(/_/g, " ")}`}
                />
            );
        }

        // Handle file/image fields
        if (fieldName.includes("logo") || fieldName.includes("signature") || fieldName.includes("stamp") || fieldName.includes("image")) {
            const existingFileUrl = typeof value === 'string' && value ? value : null;
            const hasNewFile = value instanceof File;

            return (
                <div>
                    <input
                        type="file"
                        className={cn("flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] focus-visible:border-ring aria-invalid:border-destructive", errorClass)}
                        onChange={(e) => handleChange(fieldName, e.target.files![0])}
                        accept="image/*"
                    />
                    {existingFileUrl && !hasNewFile && (
                        <div className="mt-2">
                            <small className="text-muted-foreground">Current file:</small>
                            <div className="flex items-center gap-2 mt-1">
                                <a
                                    onClick={() => openDocument(existingFileUrl)}
                                    className="flex items-center gap-1.5 rounded border border-primary/30 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary cursor-pointer hover:bg-primary/10"
                                >
                                    <Eye className="size-4" aria-hidden="true" />
                                    View Current
                                </a>
                                <AuthedImage
                                    path={toProtectedMediaPath(existingFileUrl)}
                                    alt={fieldName}
                                    style={{
                                        maxHeight: '60px',
                                        maxWidth: '100px',
                                        objectFit: 'contain',
                                        border: '1px solid var(--tb-border)',
                                        borderRadius: 'var(--tb-r-sm)',
                                        padding: '4px'
                                    }}
                                />
                            </div>
                        </div>
                    )}
                    {hasNewFile && (
                        <div className="mt-2">
                            <small className="text-success">
                                <CheckCircle className="size-4" aria-hidden="true" />
                                New file selected: {value.name}
                            </small>
                        </div>
                    )}
                </div>
            );
        }

        // Handle boolean fields as switch
        if (typeof value === "boolean" || fieldName.startsWith("is_") || fieldName.startsWith("has_")) {
            const boolValue = typeof value === "boolean" ? value : false;
            return (
                <label className="flex h-9 cursor-pointer items-center gap-2.5 text-sm" htmlFor={`switch-${fieldName}`}>
                    <Switch
                        id={`switch-${fieldName}`}
                        checked={boolValue}
                        onCheckedChange={(checked) => handleChange(fieldName, checked)}
                    />
                    <span className="text-muted-foreground">{boolValue ? "Yes" : "No"}</span>
                </label>
            );
        }

        // Handle textarea for long text fields
        if (fieldName.includes("address") || fieldName.includes("description") || fieldName.includes("note")) {
            return (
                <Textarea
                    id={fieldId}
                    className={errorClass}
                    aria-invalid={hasError || undefined}
                    rows={3}
                    value={value}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                />
            );
        }

        // Handle decimal/number fields
        if (fieldMeta.type === "number" || fieldName.includes("price") || fieldName.includes("rate") || fieldName.includes("quantity") || fieldName.includes("duty")) {
            return (
                <Input
                    id={fieldId}
                    type="number"
                    step={fieldMeta.step || "0.01"}
                    className={errorClass}
                    aria-invalid={hasError || undefined}
                    value={value}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                />
            );
        }

        // Default text input
        return (
            <Input
                id={fieldId}
                type="text"
                className={errorClass}
                aria-invalid={hasError || undefined}
                value={value}
                onChange={(e) => handleChange(fieldName, e.target.value)}
            />
        );
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <div className="flex justify-between items-center mb-4">
                    <div>
                        <div className="mb-1 h-6 w-1/3 animate-pulse rounded-md bg-muted"></div>
                        <div className="h-3.5 w-1/2 animate-pulse rounded-md bg-muted"></div>
                    </div>
                </div>
                <div className="rounded-xl border border-border bg-card shadow-sm">
                    <div className="p-5">
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                            {[...Array(6)].map((_, i) => (
                                <div key={i}>
                                    <div className="mb-1 h-3 w-1/2 animate-pulse rounded-md bg-muted"></div>
                                    <div className="h-9 w-full animate-pulse rounded-md bg-muted"></div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background">
            {/* Compact Header */}
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h4 className="mb-0 font-bold text-foreground">
                        <EntityIcon className="size-5 mr-2" style={{ color: entityColor }} />
                        {isEdit ? 'Edit' : 'New'} {entityTitle}
                        {/* Clickable BOE number → opens saved BOE copy PDF */}
                        {entityName === 'bill-of-entries' && isEdit && formData.bill_of_entry_number && (() => {
                            const pdfUrl = formData.boe_pdf_copy
                                ? ((formData.boe_pdf_copy.startsWith('http') ? '' : (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')) + formData.boe_pdf_copy)
                                : null;
                            return pdfUrl ? (
                                <a
                                    onClick={() => openDocument(pdfUrl)}
                                    className="ml-2 inline-flex items-center gap-1 text-[13.5px] font-semibold text-primary no-underline cursor-pointer hover:underline"
                                    title="View BOE copy PDF"
                                >
                                    <FileText className="size-4" aria-hidden="true" />
                                    {formData.bill_of_entry_number}
                                    <ExternalLink className="size-4" aria-hidden="true" />
                                </a>
                            ) : (
                                <span className="ml-2 text-[13.5px] font-medium text-muted-foreground">
                                    {formData.bill_of_entry_number}
                                </span>
                            );
                        })()}
                    </h4>
                    <small className="text-muted-foreground">{isEdit ? 'Update existing record' : 'Create a new record'}</small>
                </div>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                        if (isModal && onClose) { onClose(); return; }
                        navigateToList(navigate, entityName, { preserveFilters: true });
                    }}
                >
                    <ArrowLeft className="size-4" />Back to List
                </Button>
            </div>

            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="border-b border-border/70 px-6 py-4">
                    <div className="flex items-center justify-between">
                        <h6 className="mb-0 font-semibold">
                            <EntityIcon className="size-5 mr-2" style={{ color: entityColor }} />
                            {entityTitle} Details
                        </h6>
                        {entityName === 'trades' && formData.direction && (
                            <TradeMetaBadges direction={formData.direction} licenseType={formData.license_type} />
                        )}
                    </div>
                </div>
                <div className="p-6">
                    {error && (
                        <Alert variant="destructive" className="mb-4">
                            <TriangleAlert className="size-4" />
                            <AlertDescription>
                                <strong>Validation Error</strong>
                                <div className="mt-1 whitespace-pre-wrap text-sm">{error}</div>
                            </AlertDescription>
                        </Alert>
                    )}

                    {fetchingAllotment && (
                        <Alert className="mb-4">
                            <Loader2 className="size-4 animate-spin" />
                            <AlertDescription>Fetching allotment details…</AlertDescription>
                        </Alert>
                    )}

                    {/* Edit mode: show saved BOE copy link + allow re-upload */}
                    {entityName === 'bill-of-entries' && isEdit && (() => {
                        const pdfUrl = formData.boe_pdf_copy
                            ? ((formData.boe_pdf_copy.startsWith('http') ? '' : (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')) + formData.boe_pdf_copy)
                            : null;
                        return (
                            <section className="mb-4 rounded-md border border-border bg-card p-4 shadow-sm">
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div className="flex items-center gap-2.5">
                                        <span
                                            aria-hidden="true"
                                            className={cn(
                                                "inline-flex size-9 shrink-0 items-center justify-center rounded-lg",
                                                pdfUrl ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground",
                                            )}
                                        >
                                            <FileText className="size-4" aria-hidden="true" />
                                        </span>
                                        <div>
                                            <div className="text-sm font-semibold text-foreground">BOE Copy</div>
                                            {pdfUrl ? (
                                                <a
                                                    onClick={() => openDocument(pdfUrl)}
                                                    className="inline-flex cursor-pointer items-center gap-1 text-[12.5px] text-primary hover:underline"
                                                >
                                                    <ExternalLink className="size-4" aria-hidden="true" />
                                                    View saved BOE PDF
                                                </a>
                                            ) : (
                                                <span className="text-[12.5px] text-muted-foreground/60">No PDF saved yet</span>
                                            )}
                                        </div>
                                    </div>
                                    {/* Allow replacing the copy */}
                                    <div className="flex flex-wrap items-center gap-2">
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="boe-pdf-input"
                                            className="flex h-8 w-full max-w-[260px] rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring"
                                            onChange={(e) => {
                                                setBoePdfFile(e.target.files?.[0] || null);
                                                setBoeParseSummary(null);
                                            }}
                                        />
                                        <button
                                            type="button"
                                            className="flex items-center gap-1.5 rounded border border-primary/30 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary cursor-pointer hover:bg-primary/10"
                                            onClick={handleParseBoePdf}
                                            disabled={!boePdfFile || boeParsing}
                                        >
                                            {boeParsing ? (
                                                <><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent" role="status" aria-hidden="true"></span>Fetching…</>
                                            ) : (
                                                <><Wand2 className="size-4" aria-hidden="true" />Re-fetch</>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </section>
                        );
                    })()}



                    {entityName === 'bill-of-entries' && !isEdit && (
                        <BoeParsePanel
                            boePdfFile={boePdfFile}
                            setBoePdfFile={setBoePdfFile}
                            boeParsing={boeParsing}
                            boeParseSummary={boeParseSummary}
                            setBoeParseSummary={setBoeParseSummary}
                            handleParseBoePdf={handleParseBoePdf}
                        />
                    )}

                    {entityName === 'licenses' && (
                        <LicenseParsePanel
                            licensePdfFile={licensePdfFile}
                            setLicensePdfFile={setLicensePdfFile}
                            licenseParsing={licenseParsing}
                            licenseParseSummary={licenseParseSummary}
                            setLicenseParseSummary={setLicenseParseSummary}
                            existingLicenseCopy={existingLicenseCopy}
                            existingLicenseCopyName={existingLicenseCopyName}
                            handleParseLicensePdf={handleParseLicensePdf}
                            handleReparseExistingCopy={handleReparseExistingCopy}
                        />
                    )}

                    <form onSubmit={handleSubmit} encType="multipart/form-data">
                        {/* Regular Fields */}
                        {(() => {
                            const activeFields = (metadata.form_fields || []).filter((f: string) => !metadata.nested_field_defs?.[f]);

                            const renderOneField = (field: string, colClass?: string) => {
                                const isTextarea = !colClass && (field.includes("address") || field.includes("description") ||
                                    field.includes("note") || field.includes("comment") ||
                                    field.includes("condition") || field.includes("restriction"));
                                const bsToTw = (c: string | undefined) => { if (!c) return isTextarea ? "col-span-full" : ""; const m = c.match(/col(?:-md)?-(\d+)/); if (!m) return ""; const n = parseInt(m[1]); return n >= 12 ? "col-span-full" : n >= 8 ? "sm:col-span-2 md:col-span-3" : n >= 6 ? "sm:col-span-1 md:col-span-2" : n >= 4 ? "" : n >= 3 ? "" : ""; }; const col = bsToTw(colClass);
                                const fieldMeta = metadata.field_meta?.[field] || {};
                                const label = fieldMeta.label || field.replace(/_/g, " ");
                                const helpText = fieldMeta.help_text;
                                const fieldError = fieldErrors[field];
                                const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);
                                const fieldId = `field-${field}`;
                                return (
                                    <div key={field} className={col}>
                                        <label htmlFor={fieldId} className="mb-1.5 block text-xs font-semibold text-muted-foreground">
                                            {label}{fieldMeta.required && <span className="ml-1 text-destructive">*</span>}
                                        </label>
                                        {renderField(field, fieldId)}
                                        {hasError && (
                                            <div className="mt-1 flex items-center gap-1 text-xs text-destructive">
                                                <AlertCircle className="size-4" aria-hidden="true" />
                                                {Array.isArray(fieldError) ? fieldError.join(', ') : fieldError}
                                            </div>
                                        )}
                                        {helpText && !hasError && (
                                            <small className="mt-1 block text-[0.73rem] text-muted-foreground">
                                                <Info className="size-4" aria-hidden="true" />{helpText}
                                            </small>
                                        )}
                                    </div>
                                );
                            };

                            const sections = ENTITY_SECTIONS[entityName as string];
                            if (sections) {
                                const sectionedFields = new Set(sections.flatMap((s: any) => s.fields));
                                const remainingFields = activeFields.filter((f: string) => !sectionedFields.has(f));

                                return (
                                    <div className="flex flex-col gap-3">
                                        {sections.map((section: any) => {
                                            const visibleFields = section.fields.filter((f: string) => activeFields.includes(f));
                                            if (visibleFields.length === 0) return null;
                                            return (
                                                <div key={section.title} className="rounded-md bg-muted/60 px-5 py-4" style={{ borderLeft: `3px solid ${section.color}` }}>
                                                    <div className="mb-3.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.08em]" style={{ color: section.color }}>
                                                        <span className="inline-flex items-center gap-1.5"><FileText className="size-3.5 opacity-70" aria-hidden="true" />{section.title}</span>
                                                    </div>
                                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                                        {visibleFields.map((f: string) => renderOneField(f, section.cols?.[f]))}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {remainingFields.length > 0 && (
                                            <div className="rounded-md border-l-[3px] border-l-border bg-muted/60 px-5 py-4">
                                                <div className="mb-3.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.08em] text-muted-foreground">
                                                    <MoreHorizontal className="size-4" aria-hidden="true" /> Other Fields
                                                </div>
                                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                                    {remainingFields.map((f: string) => renderOneField(f))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            }

                            return (
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                    {activeFields.map((f: string) => renderOneField(f))}
                                </div>
                            );
                        })()}

                        {/* Nested Fields */}
                        {entityName !== 'allotments' && Object.entries(metadata.nested_field_defs || {}).length > 0 && (
                            <div className="mt-4">
                                <div style={{ height: 2, background: `linear-gradient(90deg, ${entityColor} 0%, transparent 100%)`, marginBottom: 20, borderRadius: 1 }}></div>
                                {(entityName === 'licenses' || entityName === 'trades') ? (() => {
                                    const allNestedEntries = Object.entries(metadata.nested_field_defs || {});
                                    // For trades, filter tabs based on license_type
                                    const nestedEntries = entityName === 'trades'
                                        ? allNestedEntries.filter(([key]) => {
                                            const lt = formData.license_type;
                                            if (!lt) return true;
                                            if (lt === 'DFIA') return key !== 'incentive_lines';
                                            if (lt === 'INCENTIVE') return key !== 'lines';
                                            return true;
                                        })
                                        : allNestedEntries;
                                    const activeTab = (activeNestedTab && nestedEntries.some(([k]) => k === activeNestedTab))
                                        ? activeNestedTab
                                        : nestedEntries[0]?.[0];
                                    const tabLabels: Record<string, string> = {
                                        export_license: 'Export Items',
                                        import_license: 'Import Items',
                                        license_documents: 'Documents',
                                        lines: 'Trade Lines',
                                        incentive_lines: 'Incentive Lines',
                                        payments: 'Payments',
                                    };
                                    return (
                                        <>
                                            <ul className="mb-0 flex gap-1 border-b border-border">
                                                {nestedEntries.map(([nestedKey]) => {
                                                    const count = (formData[nestedKey] || []).length;
                                                    const isActive = activeTab === nestedKey;
                                                    const hasErrors = (fieldErrors[nestedKey] || []).some(Boolean);
                                                    const label = tabLabels[nestedKey] || nestedKey.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
                                                    return (
                                                        <li key={nestedKey} role="presentation">
                                                            <button
                                                                role="tab"
                                                                aria-selected={isActive}
                                                                type="button"
                                                                className={cn(
                                                                    "flex cursor-pointer items-center gap-2 rounded-t-md border border-b-0 px-4 py-2 text-[0.83rem] font-medium transition-colors",
                                                                    isActive
                                                                        ? 'border-border bg-card'
                                                                        : 'border-transparent text-muted-foreground hover:text-foreground'
                                                                )}
                                                                style={isActive ? { color: entityColor, borderColor: `${entityColor} ${entityColor} white` } : undefined}
                                                                onClick={() => setActiveNestedTab(nestedKey)}
                                                            >
                                                                <Table className="size-3.5" />
                                                                {label}
                                                                {count > 0 && (
                                                                    <span
                                                                        className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", isActive ? 'text-white' : 'bg-muted text-muted-foreground')}
                                                                        style={isActive ? { backgroundColor: entityColor } : undefined}
                                                                    >
                                                                        {count}
                                                                    </span>
                                                                )}
                                                                {hasErrors && <AlertCircle className="size-4 text-destructive" aria-hidden="true" />}
                                                            </button>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                            <div className="rounded-b-xl border border-t-0 border-border/60 bg-card p-4">
                                                {nestedEntries.map(([nestedKey, nestedDef]) => activeTab === nestedKey ? (
                                                    <NestedFieldArray
                                                        key={nestedKey}
                                                        label={nestedKey.replace(/_/g, " ")}
                                                        fields={nestedDef as any[]}
                                                        value={formData[nestedKey] || []}
                                                        onChange={(value) => handleChange(nestedKey, value)}
                                                        fieldKey={nestedKey}
                                                        onFetchImports={handleFetchImports}
                                                        updatedFields={updatedFields}
                                                        errors={fieldErrors[nestedKey] || []}
                                                        entityName={entityName}
                                                        formData={formData}
                                                        itemConditionsBySerial={itemConditionsBySerial}
                                                    />
                                                ) : null)}
                                            </div>
                                        </>
                                    );
                                })() : Object.entries(metadata.nested_field_defs || {}).map(([nestedKey, nestedDef]) => (
                                    <NestedFieldArray
                                        key={nestedKey}
                                        label={nestedKey.replace(/_/g, " ")}
                                        fields={nestedDef as any[]}
                                        value={formData[nestedKey] || []}
                                        onChange={(value) => handleChange(nestedKey, value)}
                                        fieldKey={nestedKey}
                                        onFetchImports={entityName === "licenses" ? handleFetchImports : undefined}
                                        updatedFields={updatedFields}
                                        errors={fieldErrors[nestedKey] || []}
                                        entityName={entityName}
                                        formData={formData}
                                        itemConditionsBySerial={itemConditionsBySerial}
                                    />
                                ))}
                            </div>
                        )}

                        {/* Action Buttons */}
                        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border/70 pt-4">
                            <Button
                                type="submit"
                                size="lg"
                                disabled={saving}
                                style={{ background: entityColor, border: "none", color: "#fff" }}
                            >
                                {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                                {saving ? "Saving…" : isEdit ? "Update" : "Create"}
                            </Button>

                            {entityName === "licenses" && isEdit && (
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="lg"
                                    onClick={() => { setSavedLicenseId(id); setShowBalanceModal(true); }}
                                    disabled={saving}
                                >
                                    <Eye className="size-4" />View Balance
                                </Button>
                            )}

                            <Button
                                type="button"
                                variant="outline"
                                size="lg"
                                onClick={() => {
                                    if (isModal && onClose) { onClose(); return; }
                                    navigateToList(navigate, entityName, { preserveFilters: true });
                                }}
                                disabled={saving}
                            >
                                <X className="size-4" />Cancel
                            </Button>
                        </div>
                    </form>
                </div>
            </div>

            {/* License Balance Modal */}
            {entityName === 'licenses' && (
                <LicenseBalanceModal
                    show={showBalanceModal}
                    onHide={handleModalClose}
                    licenseId={savedLicenseId}
                />
            )}
        </div>
    );
}
