import {useEffect, useMemo, useState} from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";
import { toast } from "sonner";
import api from "../../api/axios";
import { openDocument, toProtectedMediaPath } from "../../utils/documentDownload";
import AuthedImage from "../../components/AuthedImage";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";
import { primeFkDetailCache } from "../../components/fkDetailCache";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {markNewItemCreated} from "../../utils/filterPersistence";
import {formatDateForInput, parseDate as parseDateUtil} from "../../utils/dateFormatter";
import * as validateFormUtil from "../../utils/formValidation";
import { ValidationRules } from "../../utils/formValidation";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import {navigateToList} from "../../utils/navigationUtils";
import {useBackButton} from "../../hooks/useBackButton";
import { ENTITY_SECTIONS } from "./entitySections";
import { buildLicensePatch, buildLicenseSummary } from "./masterFormHelpers";
import LicenseParsePanel from "./LicenseParsePanel";
import TradeMetaBadges from "./TradeMetaBadges";
import BoeParsePanel from "./BoeParsePanel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { AlertCircle, ArrowLeft, ArrowLeftRight, Award, Check, CheckCircle, CheckCircle2, ExternalLink, Eye, FileText, Info, Loader2, MoreHorizontal, PackagePlus, Paperclip, QrCode, Receipt, RefreshCw, Table, TriangleAlert, Wand2, X } from "lucide-react";

/**
 * Generic Master Form for Create/Edit
 *
 * URL Pattern:
 * - Create: /masters/:entity/create OR /licenses/create
 * - Edit: /masters/:entity/:id/edit OR /licenses/:id/edit
 */


export default function MasterForm({
    entityName: propEntityName,
    recordId: propRecordId,
    isModal = false,
    onClose,
    onSuccess
}) {
    const {entity, id} = useParams();
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

    const [formData, setFormData] = useState<Record<string, any>>({});
    const [metadata, setMetadata] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [fetchingAllotment, setFetchingAllotment] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState<Record<string, any>>({});
    const [updatedFields, setUpdatedFields] = useState<Record<string, boolean>>({});
    const [showBalanceModal, setShowBalanceModal] = useState(false); // License balance modal state
    const [savedLicenseId, setSavedLicenseId] = useState(null); // Store saved license ID for modal
    const [activeNestedTab, setActiveNestedTab] = useState(null);
    const [boePdfFile, setBoePdfFile] = useState(null);
    const [boeParsing, setBoeParsing] = useState(false);
    const [boeParseSummary, setBoeParseSummary] = useState(null);
    const [licensePdfFile, setLicensePdfFile] = useState(null);
    const [licenseParsing, setLicenseParsing] = useState(false);
    const [licenseParseSummary, setLicenseParseSummary] = useState(null);
    // {serialNumber: "AU" | "2%" | "3%" | "5%"} — drives the per-row condition
    // badge in the Import Items table.
    const [itemConditionsBySerial, setItemConditionsBySerial] = useState<Record<string, any>>({});

    // Enable browser back button support with filter preservation
    useBackButton(entityName, !isModal);

    // Use centralized date parser from utility
    const parseDate = (dateString) => {
        return parseDateUtil(dateString);
    };

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        return formatDateForInput(date);
    };

    // Fetch metadata and existing data
    useEffect(() => {
        if (!entityName) return;
        fetchMetadata();
        if (isEdit) {
            fetchRecord();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityName, recordId]);

    const fetchMetadata = async () => {
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/`;
            } else {
                apiPath = `masters/${entityName}/`;
            }

            // Use GET to fetch metadata (custom structure with form_fields, field_meta, etc.)
            const {data} = await api.get(apiPath);

            setMetadata({
                form_fields: data.form_fields || data.fields || [],
                nested_field_defs: data.nested_field_defs || {},
                field_meta: data.field_meta || {}
            });

            // Apply default values from field_meta when creating new record (not editing)
            if (!isEdit && data.field_meta) {
                const defaults = {};
                const fkDefaults = {}; // Store FK defaults to fetch labels

                Object.keys(data.field_meta).forEach(fieldName => {
                    const fieldConfig = data.field_meta[fieldName];
                    if (fieldConfig.default !== undefined && fieldConfig.default !== null) {
                        defaults[fieldName] = fieldConfig.default;

                        // Track FK fields with defaults to fetch their labels
                        // Note: type can be 'fk' or 'select' (enhanced by backend)
                        if ((fieldConfig.type === 'fk' || fieldConfig.type === 'select') && typeof fieldConfig.default === 'number') {
                            const endpoint = fieldConfig.fk_endpoint || fieldConfig.endpoint || data.fk_endpoint_overrides?.[fieldName];
                            const labelField = fieldConfig.label_field || data.label_field_overrides?.[fieldName] || 'name';

                            fkDefaults[fieldName] = {
                                id: fieldConfig.default,
                                endpoint: endpoint,
                                labelField: labelField
                            };
                        }
                    }
                });

                // For FK defaults, just set the ID - AsyncSelectField will fetch the label
                if (Object.keys(fkDefaults).length > 0) {
                    const fkValues = Object.keys(fkDefaults).reduce((acc, fieldName) => {
                        acc[fieldName] = fkDefaults[fieldName].id;
                        return acc;
                    }, {});

                    setFormData(prev => ({ ...prev, ...fkValues }));
                }

                // Only set non-FK defaults if we found any
                const nonFkDefaults = Object.keys(defaults)
                    .filter(key => !fkDefaults[key])
                    .reduce((obj, key) => {
                        obj[key] = defaults[key];
                        return obj;
                    }, {});

                if (Object.keys(nonFkDefaults).length > 0) {
                    setFormData(prevData => ({...prevData, ...nonFkDefaults}));
                }
            }
        } catch (err) {
            console.error('[MasterForm] Error fetching metadata:', err);
            console.error('[MasterForm] Error response:', err.response?.data);
            toast.error("Failed to load form metadata: " + (err.response?.data?.detail || err.message));
        }
    };

    const fetchRecord = async () => {
        setLoading(true);
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/${recordId}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/${recordId}/`;
            } else {
                apiPath = `masters/${entityName}/${recordId}/`;
            }
            const {data} = await api.get(apiPath);

            // Pre-populate the AsyncSelectField cache from the *_detail
            // fields the serializer already returns inline. Saves one GET
            // per FK per row when the page renders.
            if (entityName === 'licenses' && Array.isArray(data.import_license)) {
                data.import_license.forEach(row => {
                    if (row.hs_code_detail) {
                        primeFkDetailCache('/masters/hs-codes/', row.hs_code_detail);
                    }
                    if (Array.isArray(row.items_detail)) {
                        row.items_detail.forEach(item =>
                            primeFkDetailCache('/masters/item-names/', item)
                        );
                    }
                });
                // Rebuild the condition-badge map from persisted condition_type
                // so badges show on plain edit loads (no parse step required).
                const loadedConditions = {};
                data.import_license.forEach(row => {
                    if (row.condition_type && row.serial_number != null) {
                        loadedConditions[row.serial_number] = row.condition_type;
                    }
                });
                setItemConditionsBySerial(loadedConditions);
            }
            setFormData(data);

            // If we arrived here via /licenses/create → existing-license redirect
            // (from handleParseLicensePdf), the parsed PDF response was passed in
            // location state. Re-apply it now so the user sees prefilled fields.
            const parseData = location.state?.licenseParseData;
            if (parseData && entityName === 'licenses') {
                const carriedFile = location.state?.licensePdfFile || null;
                if (carriedFile) {
                    setLicensePdfFile(carriedFile);
                }
                // Pass the file directly so the License Copy document gets
                // attached on this render — setLicensePdfFile is async.
                applyLicenseParse(parseData, carriedFile);
                // Clear the state so a manual reload doesn't re-apply it.
                navigate(location.pathname, { replace: true, state: null });
            }
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

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
            const matchedRows = (licences || []).filter(l => l.match_status === 'matched' && l.matched_item_id);
            if (matchedRows.length > 0) {
                const toNum = (v) => {
                    if (v === null || v === undefined || v === '') return 0;
                    const n = parseFloat(v);
                    return isNaN(n) ? 0 : n;
                };
                const byItem = new Map();
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
                ...Object.keys(patch).reduce((acc, k) => { acc[k] = true; return acc; }, {}),
            }));

            const unmatched = (licences || []).filter(l => l.match_status !== 'matched').length;
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
        } catch (err) {
            console.error("BOE parse error", err);
            const msg = err?.response?.data?.detail || "Failed to parse BOE PDF";
            toast.error(msg);
        } finally {
            setBoeParsing(false);
        }
    };

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
                    const merged = existingExports.map((row, i) =>
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
                const hasLicenseCopy = existing.some(d => {
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
            ...Object.keys(patch).reduce((acc, k) => { acc[k] = true; return acc; }, {}),
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
        } catch (err) {
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
        return docs.find(d => {
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
        } catch (err) {
            console.error("Re-parse error", err);
            const msg = err?.response?.data?.detail || err?.message || "Failed to re-fetch & parse the saved Licence Copy";
            toast.error(msg);
        } finally {
            setLicenseParsing(false);
        }
    };

    const handleChange = async (field, value) => {
        const updates: Record<string, any> = {[field]: value};

        // Auto-calculate registration_number when license_number changes
        if (field === "license_number" && value && entityName === "licenses") {
            // Remove first character if it's a zero
            const regNumber = value.startsWith("0") ? value.substring(1) : value;
            updates.registration_number = regNumber;
        }

        // Auto-calculate registration_date when license_date changes
        if (field === "license_date" && value && entityName === "licenses") {
            updates.registration_date = value;

            // Also calculate license_expiry_date (license_date + 1 year)
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 1);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch (err) {
                // Silently fail for date calculation errors
            }
        }

        // Auto-calculate license_expiry_date for incentive licenses (2 years from license_date)
        if (field === "license_date" && value && entityName === "incentive-licenses") {
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 2);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch (err) {
                // Silently fail for date calculation errors
            }
        }

        // Fetch allotment details when allotment is selected in bill-of-entries
        if (field === "allotment" && entityName === "bill-of-entries") {
            // Handle both array and single value
            let allotmentIds = [];
            if (Array.isArray(value)) {
                allotmentIds = value;
            } else if (value) {
                allotmentIds = [value];
            }

            if (allotmentIds.length > 0) {
                setFetchingAllotment(true);
                try {
                    // Fetch details from all selected allotments
                    const allItemDetails = [];
                    let firstExchangeRate = null;
                    let firstProductName = null;
                    let firstPort = null;
                    let firstCompany = null;

                    for (const allotmentId of allotmentIds) {
                        const {data} = await api.get(`bill-of-entries/fetch-allotment-details/?allotment_id=${allotmentId}`);

                        // Use exchange_rate, product_name, port, and company from first allotment
                        if (!firstExchangeRate && data.exchange_rate) {
                            firstExchangeRate = data.exchange_rate;
                        }
                        if (!firstProductName && data.product_name) {
                            firstProductName = data.product_name;
                        }
                        if (!firstPort && data.port) {
                            firstPort = data.port;
                        }
                        if (!firstCompany && data.company) {
                            firstCompany = data.company;
                        }

                        // Merge all item details from all allotments
                        if (data.item_details && data.item_details.length > 0) {
                            allItemDetails.push(...data.item_details);
                        }
                    }

                    // Update form fields with fetched data
                    // Only set exchange_rate from allotment if the BOE doesn't already have one
                    const currentExcRate = parseFloat(formData.exchange_rate);
                    if (firstExchangeRate && (!currentExcRate || currentExcRate === 0)) {
                        updates.exchange_rate = firstExchangeRate;
                    }
                    if (firstProductName) {
                        updates.product_name = firstProductName;
                    }
                    if (firstPort) {
                        updates.port = firstPort;
                    }
                    if (firstCompany) {
                        updates.company = firstCompany;
                    }
                    if (allItemDetails.length > 0) {
                        // Preserve frozen (ledger-imported) rows — never overwrite them
                        const existingItems = formData.item_details || [];
                        const frozenItems = existingItems.filter(item => item.is_frozen);
                        const frozenSrNumbers = new Set(frozenItems.map(item => item.sr_number));
                        const filteredAllotmentItems = allItemDetails.filter(item => !frozenSrNumbers.has(item.sr_number));
                        updates.item_details = [...frozenItems, ...filteredAllotmentItems];
                    } else if ((formData.item_details || []).some(item => item.is_frozen)) {
                        // No new allotment items but frozen rows exist — keep them
                        updates.item_details = (formData.item_details || []).filter(item => item.is_frozen);
                    }
                } catch (err) {
                    toast.error("Failed to fetch allotment details: " + (err.response?.data?.error || err.message));
                } finally{
                    setFetchingAllotment(false);
                }
            }
        }

        // Allotment calculations
        if (entityName === "allotments") {
            // Get current form data with the new update applied
            const currentData = {...formData, ...updates};

            // Priority 1: Calculate cif_fc from unit_value_per_unit and required_quantity
            // Calculate whenever unit_value, quantity, or exchange_rate changes
            if ((field === "unit_value_per_unit" || field === "required_quantity" || field === "exchange_rate")
                && currentData.unit_value_per_unit && currentData.required_quantity) {
                const unitValue = parseFloat(currentData.unit_value_per_unit);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(unitValue) && !isNaN(requiredQty) && requiredQty > 0) {
                    updates.cif_fc = (unitValue * requiredQty).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation
                }
            }
            // Priority 2: If cif_fc provided but unit_value not, calculate unit_value
            else if (field === "cif_fc" && currentData.cif_fc && currentData.required_quantity && !currentData.unit_value_per_unit) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0) {
                    // Round up to 3 decimal places
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                    currentData.unit_value_per_unit = updates.unit_value_per_unit; // Update for reference
                }
            }

            // Calculate cif_fc from cif_inr and exchange_rate (if cif_inr and exchange_rate present)
            if ((field === "cif_inr" || field === "exchange_rate") && currentData.cif_inr && currentData.exchange_rate) {
                const cifInr = parseFloat(currentData.cif_inr);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifInr) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_fc = (cifInr / exchangeRate).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation

                    // Also calculate unit_value_per_unit if we have required_quantity
                    if (currentData.required_quantity) {
                        const requiredQty = parseFloat(currentData.required_quantity);
                        if (!isNaN(requiredQty) && requiredQty > 0) {
                            updates.unit_value_per_unit = (Math.ceil((parseFloat(updates.cif_fc) / requiredQty) * 1000) / 1000).toFixed(3);
                        }
                    }
                }
            }
            // Calculate cif_inr from cif_fc and exchange_rate (if cif_fc and exchange_rate present)
            else if ((field === "cif_fc" || field === "exchange_rate") && currentData.cif_fc && currentData.exchange_rate) {
                const cifFc = parseFloat(currentData.cif_fc);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifFc) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_inr = (cifFc * exchangeRate).toFixed(2);
                }
            }

            // Calculate unit_value_per_unit from cif_fc and required_quantity
            if ((field === "cif_fc" || field === "required_quantity") && currentData.cif_fc && currentData.required_quantity) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                // Only auto-calculate unit price if it's not already set or if user is changing cif_fc/quantity
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0 &&
                    (field === "cif_fc" || field === "required_quantity")) {
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                }
            }
        }

        setFormData(prev => ({
            ...prev,
            ...updates
        }));
    };

    const handleFetchImports = async (exportIndex, exportItem) => {
        // Validate required fields
        if (!exportItem.norm_class) {
            alert("Please select a Norm Class first");
            return;
        }

        if (!exportItem.start_serial_number) {
            alert("Please enter Start Serial Number first");
            return;
        }

        try {
            // Fetch the SION norm class with its import items
            const {data: sionData} = await api.get(`masters/sion-classes/${exportItem.norm_class}/`);

            if (!sionData.import_norm || sionData.import_norm.length === 0) {
                alert("No import items found for this SION norm class");
                return;
            }

            // Get start serial number from export item (form field only, not saved)
            const startSerial = parseInt(exportItem.start_serial_number) || 0;
            const existingImports = formData.import_license || [];

            // Track existing serial numbers to prevent duplicates
            const existingSerialNumbers = new Set(existingImports.map(item => item.serial_number));

            const updatedImports = [...existingImports];
            const newlyUpdatedFields = {};
            let addedCount = 0;
            let updatedCount = 0;

            // Process each SION import item
            sionData.import_norm.forEach((sionImport) => {
                const targetSerialNumber = startSerial + (sionImport.serial_number || 0);

                // Check if this serial number already exists
                const existingIndex = existingImports.findIndex(item => item.serial_number === targetSerialNumber);

                if (existingIndex >= 0) {
                    // Serial number exists - only update empty fields
                    const existing = existingImports[existingIndex];
                    let fieldsUpdated = false;

                    // Update hs_code if empty
                    if (!existing.hs_code && sionImport.hsn_code) {
                        updatedImports[existingIndex].hs_code = sionImport.hsn_code;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.hs_code`] = true;
                    }

                    // Update description if empty
                    if (!existing.description && sionImport.description) {
                        updatedImports[existingIndex].description = sionImport.description;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.description`] = true;
                    }

                    // Update unit if empty
                    if (!existing.unit && sionImport.unit) {
                        updatedImports[existingIndex].unit = sionImport.unit;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.unit`] = true;
                    }

                    if (fieldsUpdated) updatedCount++;
                } else if (!existingSerialNumbers.has(targetSerialNumber)) {
                    // Serial number doesn't exist - add new item
                    const newIndex = updatedImports.length;
                    const netQty = parseFloat(exportItem.net_quantity) || 1;
                    const newItem = {
                        serial_number: targetSerialNumber,
                        hs_code: sionImport.hsn_code || null,
                        description: sionImport.description || "",
                        duty_type: sionImport.duty_type || "Basic",
                        quantity: parseFloat((netQty * (sionImport.quantity || 0)).toFixed(4)),
                        unit: sionImport.unit || "KG",
                        cif_fc: 0,
                        cif_inr: 0,
                        items: []
                    };

                    updatedImports.push(newItem);
                    existingSerialNumbers.add(targetSerialNumber);

                    // Mark all fields as updated for new items
                    Object.keys(newItem).forEach(key => {
                        newlyUpdatedFields[`import_license.${newIndex}.${key}`] = true;
                    });

                    addedCount++;
                }
            });

            // Update form data and highlighted fields
            handleChange("import_license", updatedImports);
            setUpdatedFields(prev => ({...prev, ...newlyUpdatedFields}));

            let message = [];
            if (addedCount > 0) message.push(`Added ${addedCount} new import items`);
            if (updatedCount > 0) message.push(`Updated ${updatedCount} existing items`);
            if (message.length > 0) {
                toast.success(message.join('. '));
            } else {
                toast.info("No changes made");
            }

        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to fetch import items from SION");
        }
    };

    // Frontend validation function
    const validateForm = () => {
        const errors: Record<string, any> = {};

        // Collect required fields from metadata and validate using utility
        if (metadata.form_fields) {
            metadata.form_fields.forEach(fieldName => {
                const fieldMeta = metadata.field_meta?.[fieldName] || {};
                const label = fieldMeta.label || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                const value = formData[fieldName];
                const rules = [];

                // Add required rule
                if (fieldMeta.required) {
                    rules.push(ValidationRules.REQUIRED);
                }

                // Add type-specific validations
                if (fieldMeta.type === 'email' || fieldName.includes('email')) {
                    rules.push(ValidationRules.EMAIL);
                }
                if (fieldMeta.type === 'url' || fieldName.includes('url')) {
                    rules.push(ValidationRules.URL);
                }
                if (fieldMeta.type === 'number' || fieldMeta.type === 'decimal' || fieldMeta.type === 'integer') {
                    if (fieldMeta.type === 'integer') {
                        rules.push(ValidationRules.INTEGER);
                    } else {
                        rules.push(ValidationRules.NUMBER);
                    }
                }
                if (fieldMeta.min_value !== undefined) {
                    rules.push({ type: ValidationRules.MIN_VALUE, value: fieldMeta.min_value });
                }
                if (fieldMeta.max_value !== undefined) {
                    rules.push({ type: ValidationRules.MAX_VALUE, value: fieldMeta.max_value });
                }
                if (fieldMeta.min_length) {
                    rules.push({ type: ValidationRules.MIN_LENGTH, value: fieldMeta.min_length });
                }
                if (fieldMeta.max_length) {
                    rules.push({ type: ValidationRules.MAX_LENGTH, value: fieldMeta.max_length });
                }

                // Validate field if it has rules
                if (rules.length > 0) {
                    const fieldErrors = validateFormUtil.validateField(value, rules, label);
                    if (fieldErrors.length > 0) {
                        errors[fieldName] = fieldErrors;
                    }
                }
            });
        }

        // License-specific validations
        if (entityName === 'licenses') {
            // Validate license number format
            if (formData.license_number && !/^[A-Z0-9/-]+$/.test(formData.license_number)) {
                errors.license_number = ['License number can only contain uppercase letters, numbers, hyphens, and slashes'];
            }

            // Validate dates
            if (formData.license_date && formData.license_expiry_date) {
                const licenseDate = new Date(formData.license_date);
                const expiryDate = new Date(formData.license_expiry_date);
                if (expiryDate <= licenseDate) {
                    errors.license_expiry_date = ['Expiry date must be after license date'];
                }
            }

            // Validate export items using validation utility
            if (formData.export_license && Array.isArray(formData.export_license)) {
                const exportSchema = {
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description'
                    },
                    net_quantity: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.NON_NEGATIVE],
                        label: 'Net Quantity'
                    }
                };
                const exportErrors = validateFormUtil.validateNestedArray(formData.export_license, exportSchema);
                if (exportErrors.length > 0) {
                    errors.export_license = exportErrors;
                }
            }

            // Validate import items using validation utility
            if (formData.import_license && Array.isArray(formData.import_license)) {
                const importSchema = {
                    hs_code: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'HS Code'
                    },
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description'
                    },
                    serial_number: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.INTEGER],
                        label: 'Serial Number'
                    },
                    unit: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Unit'
                    }
                };
                const importErrors = validateFormUtil.validateNestedArray(formData.import_license, importSchema);
                if (importErrors.length > 0) {
                    errors.import_license = importErrors;
                }
            }

            // Validate documents (if adding new ones)
            if (formData.license_documents && Array.isArray(formData.license_documents)) {
                const docErrors = [];
                formData.license_documents.forEach((doc, index) => {
                    // Only validate if file is provided (new document)
                    if (doc.file && doc.file instanceof File) {
                        const docSchema = {
                            type: {
                                rules: [ValidationRules.REQUIRED],
                                label: 'Document Type'
                            }
                        };
                        const itemErrors = validateFormUtil.validateForm(doc, docSchema);
                        if (Object.keys(itemErrors).length > 0) {
                            docErrors[index] = itemErrors;
                        }
                    }
                });
                if (docErrors.length > 0) {
                    errors.license_documents = docErrors;
                }
            }
        }

        return errors;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

        // Frontend validation
        const validationErrors = validateForm();
        if (Object.keys(validationErrors).length > 0) {
            setFieldErrors(validationErrors);

            // Build user-friendly error messages
            const errorMessages = [];
            const fieldNameMap = {
                'license_number': 'License Number',
                'license_date': 'License Date',
                'license_expiry_date': 'License Expiry Date',
                'exporter': 'Exporter',
                'port': 'Port',
                'export_license': 'Export Items',
                'import_license': 'Import Items',
                'license_documents': 'Documents',
                'hs_code': 'HS Code',
                'description': 'Description',
                'quantity': 'Quantity',
                'serial_number': 'Serial Number',
                'type': 'Type',
                'file': 'File',
                'net_quantity': 'Net Quantity',
                'norm_class': 'Norm Class',
                'unit': 'Unit'
            };

            Object.entries(validationErrors).forEach(([field, fieldErrors]) => {
                const friendlyName = fieldNameMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                if (Array.isArray(fieldErrors)) {
                    // Check if it's an array of error objects (nested items)
                    if (fieldErrors.some(item => item && typeof item === 'object')) {
                        fieldErrors.forEach((itemErrors, index) => {
                            if (itemErrors && typeof itemErrors === 'object') {
                                Object.entries(itemErrors).forEach(([subField, subErrors]) => {
                                    const subName = fieldNameMap[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                    const message = Array.isArray(subErrors) ? subErrors.join(', ') : subErrors;
                                    errorMessages.push(`${friendlyName} #${index + 1} - ${subName}: ${message}`);
                                });
                            }
                        });
                    } else {
                        // Simple array of error strings
                        errorMessages.push(`${friendlyName}: ${fieldErrors.join(', ')}`);
                    }
                } else if (typeof fieldErrors === 'string') {
                    errorMessages.push(`${friendlyName}: ${fieldErrors}`);
                }
            });

            const errorMsg = 'Please fix the following errors:\n\n' + errorMessages.join('\n');
            setError(errorMsg);
            toast.error('Please fix validation errors before submitting');

            // Scroll to first error
            setTimeout(() => {
                const firstErrorField = document.querySelector('.is-invalid');
                if (firstErrorField) {
                    firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    (firstErrorField as HTMLElement).focus();
                }
            }, 100);

            setSaving(false);
            return;
        }

        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/`;
            } else {
                apiPath = `masters/${entityName}/`;
            }

            // Check if formData contains any File objects (including nested).
            // NOTE: boePdfFile is intentionally excluded here — it is uploaded
            // as a separate PATCH after the main JSON save so that nested arrays
            // like item_details are not broken by multipart encoding.
            const hasFiles = () => {
                const checkForFiles = (obj) => {
                    if (obj instanceof File) return true;
                    if (Array.isArray(obj)) {
                        return obj.some(item => checkForFiles(item));
                    }
                    if (obj && typeof obj === 'object') {
                        return Object.values(obj).some(val => checkForFiles(val));
                    }
                    return false;
                };
                return checkForFiles(formData);
            };

            let response;
            if (hasFiles()) {
                // Use FormData for file uploads
                const formDataObj = new FormData();

                // Helper function to append data to FormData
                const appendToFormData = (key, value, parentKey = '') => {
                    const fullKey = parentKey ? `${parentKey}.${key}` : key;

                    // Skip empty 'id' fields in nested arrays (for new items)
                    if (key === 'id' && (value === '' || value === null || value === undefined) && parentKey.includes('[')) {
                        return; // Don't append empty id fields for nested items
                    }

                    if (value instanceof File) {
                        formDataObj.append(fullKey, value);
                    } else if (Array.isArray(value)) {
                        value.forEach((item, index) => {
                            if (item instanceof File) {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            } else if (typeof item === 'object' && item !== null) {
                                Object.entries(item).forEach(([subKey, subValue]) => {
                                    appendToFormData(subKey, subValue, `${fullKey}[${index}]`);
                                });
                            } else {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            }
                        });
                    } else if (value && typeof value === 'object' && !(value instanceof Date)) {
                        Object.entries(value).forEach(([subKey, subValue]) => {
                            appendToFormData(subKey, subValue, fullKey);
                        });
                    } else if (value !== null && value !== undefined) {
                        // Allow empty strings for nested fields (important for nested arrays)
                        // Only skip truly null/undefined values
                        formDataObj.append(fullKey, value === '' ? '' : value);
                    }
                };

                Object.entries(formData).forEach(([key, value]) => {
                    // boe_pdf_copy is handled by the dedicated PATCH below — never
                    // include the existing URL string (or even a new File) here, or
                    // DRF rejects the string as "not a file".
                    if (entityName === 'bill-of-entries' && key === 'boe_pdf_copy') return;
                    appendToFormData(key, value);
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${id}/`, formDataObj, {
                        headers: {'Content-Type': 'multipart/form-data'}
                    });
                } else {
                    response = await api.post(apiPath, formDataObj, {
                        headers: {'Content-Type': 'multipart/form-data'}
                    });
                }
            } else {
                // Use regular JSON for non-file data
                // Clean up date fields
                const cleanedFormData = {...formData};

                // Remove audit fields (should never be sent from frontend)
                delete cleanedFormData.created_on;
                delete cleanedFormData.created_by;
                delete cleanedFormData.modified_on;
                delete cleanedFormData.modified_by;

                // boe_pdf_copy comes back from GET as a URL string. Sending it on
                // PATCH triggers DRF's "submitted data was not a file" error. The
                // dedicated multipart PATCH below handles new uploads.
                if (entityName === 'bill-of-entries') {
                    delete cleanedFormData.boe_pdf_copy;
                }

                Object.keys(cleanedFormData).forEach(key => {
                    if (key.includes('date') || key.includes('_at') || key.includes('_on')) {
                        const value = cleanedFormData[key];
                        if (value === '' || value === undefined) {
                            // Empty dates should be null
                            cleanedFormData[key] = null;
                        } else if (value instanceof Date) {
                            // Convert Date objects to YYYY-MM-DD
                            cleanedFormData[key] = formatDateForAPI(value);
                        } else if (typeof value === 'string' && value.length > 0) {
                            // Parse and reformat string dates (handles both YYYY-MM-DD and dd-MM-yyyy)
                            const date = parseDate(value);
                            if (date) {
                                cleanedFormData[key] = formatDateForAPI(date);
                            }
                        }
                    }
                });

                // Clean up nested arrays: remove empty 'id' fields for new items
                Object.keys(cleanedFormData).forEach(key => {
                    if (Array.isArray(cleanedFormData[key])) {
                        cleanedFormData[key] = cleanedFormData[key].map(item => {
                            if (item && typeof item === 'object') {
                                const cleanedItem = {...item};
                                // Remove id if it's empty string, null, or undefined
                                if (cleanedItem.id === '' || cleanedItem.id === null || cleanedItem.id === undefined) {
                                    delete cleanedItem.id;
                                }
                                return cleanedItem;
                            }
                            return item;
                        });
                    }
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${recordId}/`, cleanedFormData);
                } else {
                    response = await api.post(apiPath, cleanedFormData);
                }
            }

            // Mark newly created items for highlighting in list
            if (!isEdit && response.data?.id) {
                markNewItemCreated(response.data.id);
            }

            // Upload the BOE PDF copy separately (as multipart PATCH) so that
            // the main JSON save above is not broken by multipart encoding of nested arrays.
            if (entityName === 'bill-of-entries' && boePdfFile) {
                const savedId = response.data?.id || recordId;
                if (savedId) {
                    try {
                        const pdfFd = new FormData();
                        pdfFd.append('boe_pdf_copy', boePdfFile, boePdfFile.name);
                        pdfFd.append('is_fetch', 'true');
                        await api.patch(`bill-of-entries/${savedId}/`, pdfFd, {
                            headers: { 'Content-Type': 'multipart/form-data' },
                        });
                    } catch {
                        // Non-critical — main BOE was saved; log silently
                        console.warn('[BOE] Failed to upload PDF copy');
                    }
                }
            }

            // Set flag to restore filters when returning to list
            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                returnTo: 'list',
                timestamp: new Date().getTime()
            }));

            // Show success message
            toast.success(isEdit ? `${entityTitle} updated successfully` : `${entityTitle} created successfully`);

            // If modal mode, call onSuccess and onClose
            if (isModal && onSuccess) {
                const savedId = response.data?.id || recordId;
                onSuccess(savedId);
            }

            if (isModal && onClose) {
                onClose();
                return;
            }

            // Redirect based on entity type (only for non-modal)
            let redirectPath;
            if (entityName === 'licenses') {
                redirectPath = '/licenses';
            } else if (entityName === 'allotments') {
                // For allotments, redirect to action page after save
                const savedId = response.data.id || recordId;
                redirectPath = `/allotments/${savedId}/allocate`;
            } else if (entityName === 'bill-of-entries') {
                redirectPath = `/bill-of-entries`;
            } else if (entityName === 'trades') {
                redirectPath = `/trades`;
            } else if (entityName === 'incentive-licenses') {
                redirectPath = '/incentive-licenses';
            } else {
                redirectPath = `/masters/${entityName}`;
            }
            navigate(redirectPath);
        } catch (err) {
            console.error('Save error:', err.response?.data);

            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                // Format backend errors using utility
                const formattedErrors = validateFormUtil.formatBackendErrors(err.response.data);
                setFieldErrors(formattedErrors);

                // Create a user-friendly error message with better field names
                const errorMessages = [];
                const fieldNameMap = {
                    'license_number': 'License Number',
                    'license_date': 'License Date',
                    'license_expiry_date': 'License Expiry Date',
                    'exporter': 'Exporter',
                    'port': 'Port',
                    'export_license': 'Export Items',
                    'import_license': 'Import Items',
                    'license_documents': 'Documents',
                    'hs_code': 'HS Code',
                    'description': 'Description',
                    'quantity': 'Quantity',
                    'serial_number': 'Serial Number',
                    'type': 'Type',
                    'file': 'File',
                    'net_quantity': 'Net Quantity',
                    'norm_class': 'Norm Class',
                    'unit': 'Unit',
                    'cif_fc': 'CIF (FC)',
                    'cif_inr': 'CIF (INR)'
                };

                // Helper function to get friendly field name
                const getFriendlyFieldName = (fieldPath) => {
                    // Handle nested paths like export_license[0].hs_code
                    const match = fieldPath.match(/^(\w+)(?:\[(\d+)\])?\.?(\w+)?/);
                    if (match) {
                        const [, mainField, index, subField] = match;
                        const mainName = fieldNameMap[mainField] || mainField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                        if (index !== undefined && subField) {
                            const subName = fieldNameMap[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                            return `${mainName} #${parseInt(index) + 1} - ${subName}`;
                        } else if (index !== undefined) {
                            return `${mainName} #${parseInt(index) + 1}`;
                        }
                        return mainName;
                    }
                    return fieldNameMap[fieldPath] || fieldPath.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                };

                // Helper function to process errors recursively
                const processErrors = (errors, fieldPath = '') => {
                    if (Array.isArray(errors)) {
                        errors.forEach((error, index) => {
                            if (typeof error === 'object' && error !== null) {
                                // Handle nested field errors (like license_documents[0].type)
                                if (error.non_field_errors) {
                                    const friendlyName = getFriendlyFieldName(`${fieldPath}[${index}]`);
                                    errorMessages.push(`${friendlyName}: ${error.non_field_errors.join(', ')}`);
                                }
                                Object.entries(error).forEach(([key, value]) => {
                                    if (key !== 'non_field_errors') {
                                        const nestedPath = `${fieldPath}[${index}].${key}`;
                                        processErrors(value, nestedPath);
                                    }
                                });
                            } else if (typeof error === 'string') {
                                const friendlyName = getFriendlyFieldName(fieldPath);
                                errorMessages.push(`${friendlyName}: ${error}`);
                            }
                        });
                    } else if (typeof errors === 'string') {
                        const friendlyName = getFriendlyFieldName(fieldPath);
                        errorMessages.push(`${friendlyName}: ${errors}`);
                    } else if (typeof errors === 'object' && errors !== null) {
                        Object.entries(errors).forEach(([key, value]) => {
                            const nestedPath = fieldPath ? `${fieldPath}.${key}` : key;
                            processErrors(value, nestedPath);
                        });
                    }
                };

                // Handle top-level non_field_errors
                if (err.response.data.non_field_errors) {
                    errorMessages.push(...err.response.data.non_field_errors);
                }

                // Process all field errors
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (field !== 'non_field_errors') {
                        processErrors(errors, field);
                    }
                });

                const errorMsg = errorMessages.length > 0
                    ? 'Please fix the following errors:\n\n' + errorMessages.join('\n')
                    : "Validation errors occurred. Please check the form.";
                setError(errorMsg);
                toast.error('Validation failed. Please check the form for errors.');

                // Scroll to first error
                setTimeout(() => {
                    const firstErrorField = document.querySelector('.is-invalid');
                    if (firstErrorField) {
                        firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        (firstErrorField as HTMLElement).focus();
                    }
                }, 100);
            } else {
                // Handle other error formats
                let errorMsg = "Failed to save record";

                if (err.response?.data?.detail) {
                    errorMsg = err.response.data.detail;
                } else if (err.response?.data?.error) {
                    errorMsg = err.response.data.error;
                } else if (err.response?.data?.message) {
                    errorMsg = err.response.data.message;
                } else if (typeof err.response?.data === 'string') {
                    errorMsg = err.response.data;
                } else if (err.response?.status === 400) {
                    errorMsg = "Invalid data provided. Please check your input.";
                } else if (err.response?.status === 403) {
                    errorMsg = "You don't have permission to perform this action.";
                } else if (err.response?.status === 404) {
                    errorMsg = "Record not found.";
                } else if (err.response?.status === 500) {
                    errorMsg = "Server error occurred. Please try again or contact support.";
                } else if (err.message) {
                    errorMsg = `Error: ${err.message}`;
                }

                setError(errorMsg);
                toast.error(errorMsg);
            }
        } finally {
            setSaving(false);
        }
    };

    const renderField = (fieldName) => {
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
                        selected={parseDate(value)}
                        onChange={(date) => handleChange(fieldName, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className={`flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] focus-visible:border-ring  aria-invalid:border-destructive ${errorClass}`}
                        wrapperClassName="w-100 d-block"
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
                        className={`flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] focus-visible:border-ring  aria-invalid:border-destructive ${errorClass}`}
                        onChange={(e) => handleChange(fieldName, e.target.files[0])}
                        accept="image/*"
                    />
                    {existingFileUrl && !hasNewFile && (
                        <div className="mt-2">
                            <small className="text-muted">Current file:</small>
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
                type="text"
                className={errorClass}
                aria-invalid={hasError || undefined}
                value={value}
                onChange={(e) => handleChange(fieldName, e.target.value)}
            />
        );
    };

    const handleModalClose = () => {
        setShowBalanceModal(false);
    };

    const entityTitle = entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    const ENTITY_ICON_MAP = {
        licenses: FileText,
        allotments: PackagePlus,
        'bill-of-entries': Receipt,
        trades: ArrowLeftRight,
        'incentive-licenses': Award,
    };
    const EntityIcon = ENTITY_ICON_MAP[entityName] || FileText;
    const entityColorMap = {
        licenses: 'var(--tb-brand)',
        allotments: 'var(--tb-info)',
        'bill-of-entries': 'var(--tb-brand)',
        trades: 'var(--tb-success)',
        'incentive-licenses': 'var(--tb-warning)',
    };
    const entityColor = entityColorMap[entityName] || 'var(--tb-brand)';

    if (loading) {
        return (
            <div className="container-fluid" style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
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
        <div className="container-fluid" style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
            {/* Compact Header */}
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h4 className="mb-0 font-bold" style={{ color: 'var(--tb-text)' }}>
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
                                    className="ms-2"
                                    title="View BOE copy PDF"
                                    style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--primary-color)', textDecoration: 'none', cursor: 'pointer' }}
                                >
                                    <FileText className="size-4" aria-hidden="true" />
                                    {formData.bill_of_entry_number}
                                    <ExternalLink className="size-4" aria-hidden="true" />
                                </a>
                            ) : (
                                <span className="ms-2" style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--text-secondary)' }}>
                                    {formData.bill_of_entry_number}
                                </span>
                            );
                        })()}
                    </h4>
                    <small className="text-muted">{isEdit ? 'Update existing record' : 'Create a new record'}</small>
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
                        <div className="alert alert-danger flex items-start gap-2 mb-4">
                            <TriangleAlert className="size-4" aria-hidden="true" />
                            <div>
                                <strong>Validation Error</strong>
                                <div className="mt-1" style={{ whiteSpace: 'pre-wrap', fontSize: 14 }}>{error}</div>
                            </div>
                        </div>
                    )}

                    {fetchingAllotment && (
                        <div className="alert alert-info flex items-center gap-2 mb-4">
                            <span className="inline-block size-4 flex-shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                            Fetching allotment details...
                        </div>
                    )}

                    {/* Edit mode: show saved BOE copy link + allow re-upload */}
                    {entityName === 'bill-of-entries' && isEdit && (() => {
                        const pdfUrl = formData.boe_pdf_copy
                            ? ((formData.boe_pdf_copy.startsWith('http') ? '' : (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')) + formData.boe_pdf_copy)
                            : null;
                        return (
                            <section className="surface-card mb-4" style={{ padding: 16 }}>
                                <div className="flex items-center justify-between flex-wrap" style={{ gap: 12 }}>
                                    <div className="flex items-center" style={{ gap: 10 }}>
                                        <span
                                            aria-hidden="true"
                                            style={{
                                                width: 36, height: 36, borderRadius: 8,
                                                background: pdfUrl ? 'var(--danger-bg)' : 'var(--surface-sunken)',
                                                color: pdfUrl ? 'var(--danger-color)' : 'var(--text-tertiary)',
                                                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                            }}
                                        >
                                            <FileText className="size-4" aria-hidden="true" />
                                        </span>
                                        <div>
                                            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>BOE Copy</div>
                                            {pdfUrl ? (
                                                <a
                                                    onClick={() => openDocument(pdfUrl)}
                                                    style={{ fontSize: 12.5, color: 'var(--primary-color)', cursor: 'pointer' }}
                                                >
                                                    <ExternalLink className="size-4" aria-hidden="true" />
                                                    View saved BOE PDF
                                                </a>
                                            ) : (
                                                <span style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>No PDF saved yet</span>
                                            )}
                                        </div>
                                    </div>
                                    {/* Allow replacing the copy */}
                                    <div className="flex items-center" style={{ gap: 8, flexWrap: 'wrap' }}>
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="boe-pdf-input"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            style={{ maxWidth: 260 }}
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
                            const activeFields = (metadata.form_fields || []).filter(f => !metadata.nested_field_defs?.[f]);

                            const renderOneField = (field: string, colClass?: string) => {
                                const isTextarea = !colClass && (field.includes("address") || field.includes("description") ||
                                    field.includes("note") || field.includes("comment") ||
                                    field.includes("condition") || field.includes("restriction"));
                                const bsToTw = (c) => { if (!c) return isTextarea ? "col-span-full" : ""; const m = c.match(/col(?:-md)?-(\d+)/); if (!m) return ""; const n = parseInt(m[1]); return n >= 12 ? "col-span-full" : n >= 8 ? "sm:col-span-2 md:col-span-3" : n >= 6 ? "sm:col-span-1 md:col-span-2" : n >= 4 ? "" : n >= 3 ? "" : ""; }; const col = bsToTw(colClass);
                                const fieldMeta = metadata.field_meta?.[field] || {};
                                const label = fieldMeta.label || field.replace(/_/g, " ");
                                const helpText = fieldMeta.help_text;
                                const fieldError = fieldErrors[field];
                                const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);
                                return (
                                    <div key={field} className={col}>
                                        <label className="form-label" style={{ fontSize: 12, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                            {label}{fieldMeta.required && <span className="text-danger ml-1">*</span>}
                                        </label>
                                        {renderField(field)}
                                        {hasError && (
                                            <div className="mt-0.5 text-[11.5px] text-destructive block" style={{ fontSize: 12, marginTop: 4 }}>
                                                <AlertCircle className="size-4" aria-hidden="true" />
                                                {Array.isArray(fieldError) ? fieldError.join(', ') : fieldError}
                                            </div>
                                        )}
                                        {helpText && !hasError && (
                                            <small className="form-text block mt-1" style={{ color: 'var(--text-secondary)', fontSize: '0.73rem' }}>
                                                <Info className="size-4" aria-hidden="true" />{helpText}
                                            </small>
                                        )}
                                    </div>
                                );
                            };

                            const sections = ENTITY_SECTIONS[entityName];
                            if (sections) {
                                const sectionedFields = new Set(sections.flatMap(s => s.fields));
                                const remainingFields = activeFields.filter(f => !sectionedFields.has(f));

                                return (
                                    <div className="flex flex-col gap-3">
                                        {sections.map(section => {
                                            const visibleFields = section.fields.filter(f => activeFields.includes(f));
                                            if (visibleFields.length === 0) return null;
                                            return (
                                                <div key={section.title} style={{ background: 'var(--tb-sunken)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: `3px solid ${section.color}` }}>
                                                    <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: section.color, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <span style={{display:"inline-flex",alignItems:"center",gap:6}}><FileText className="size-3.5" style={{opacity:0.7}}/>{section.title}</span>
                                                    </div>
                                                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                                        {visibleFields.map(f => renderOneField(f, section.cols?.[f]))}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {remainingFields.length > 0 && (
                                            <div style={{ background: 'var(--tb-sunken)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: '3px solid var(--tb-border-strong)' }}>
                                                <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-text-secondary)', marginBottom: '14px' }}>
                                                    <MoreHorizontal className="size-4" aria-hidden="true" /> Other Fields
                                                </div>
                                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                                    {remainingFields.map(f => renderOneField(f))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            }

                            return (
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
                                    {activeFields.map(f => renderOneField(f))}
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
                                    const tabLabels = {
                                        export_license: 'Export Items',
                                        import_license: 'Import Items',
                                        license_documents: 'Documents',
                                        lines: 'Trade Lines',
                                        incentive_lines: 'Incentive Lines',
                                        payments: 'Payments',
                                    };
                                    return (
                                        <>
                                            <ul className="flex gap-1 border-b border-border" style={{ marginBottom: 0 }}>
                                                {nestedEntries.map(([nestedKey]) => {
                                                    const count = (formData[nestedKey] || []).length;
                                                    const isActive = activeTab === nestedKey;
                                                    const hasErrors = (fieldErrors[nestedKey] || []).some(Boolean);
                                                    const label = tabLabels[nestedKey] || nestedKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                                    return (
                                                        <li key={nestedKey} className="nav-item">
                                                            <button
                                                                type="button"
                                                                className={`flex cursor-pointer items-center gap-2 rounded-t-md border border-b-0 px-4 py-2 text-sm font-medium transition-colors ${isActive ? 'border-border bg-card text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
                                                                onClick={() => setActiveNestedTab(nestedKey)}
                                                                style={{ fontSize: '0.83rem', fontWeight: isActive ? '600' : '500', padding: '8px 16px', color: isActive ? entityColor : 'var(--tb-text-secondary)', borderColor: isActive ? `${entityColor} ${entityColor} white` : 'transparent', borderRadius: '8px 8px 0 0' }}
                                                            >
                                                                <Table className="size-3.5" />
                                                                {label}
                                                                {count > 0 && (
                                                                    <span className="badge rounded-pill" style={{ backgroundColor: isActive ? entityColor : 'var(--tb-border-soft)', color: isActive ? 'white' : 'var(--tb-text-secondary)', fontSize: 11, padding: '2px 7px' }}>
                                                                        {count}
                                                                    </span>
                                                                )}
                                                                {hasErrors && <AlertCircle className="size-4" aria-hidden="true" />}
                                                            </button>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                            <div style={{ border: '1px solid var(--tb-border-soft)', borderTop: 'none', borderRadius: '0 0 10px 10px', padding: '20px 16px', background: 'var(--tb-card-bg)' }}>
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
