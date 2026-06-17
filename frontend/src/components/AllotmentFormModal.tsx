import { useState, useEffect } from 'react';
import api from '../api/axios';
import { toast } from "sonner";
import AsyncSelect from 'react-select/async';
import { extractFormErrors, formatNonFieldErrors, getFieldError } from '../utils/formErrors';
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { AlertCircle, Building2, Check, DollarSign, FileText, Loader2, Package, ToggleRight, TriangleAlert, X } from "lucide-react";

export default function AllotmentFormModal({ show, onHide, allotmentId = null, mode = 'create', onSuccess, onSaveNavigate }) {
    const [formData, setFormData] = useState<Record<string, any>>({
        company: null,
        type: 'AT',
        port: null,
        item_name: '',
        required_quantity: '',
        cif_inr: '',
        exchange_rate: '',
        cif_fc: '',
        unit_value_per_unit: '',
        invoice: '',
        estimated_arrival_date: '',
        bl_detail: '',
        is_boe: false,
        is_approved: false
    });
    const [loading, setLoading] = useState(false);
    const [initialLoad, setInitialLoad] = useState(true);
    const [fieldErrors, setFieldErrors] = useState({});
    const [nonFieldErrors, setNonFieldErrors] = useState([]);

    useEffect(() => {
        const fetchAllotmentData = async () => {
            setInitialLoad(true);
            try {
                const { data } = await api.get(`allotments/${allotmentId}/`);

                setFormData({
                    company: data.company ? { value: data.company, label: data.company_name } : null,
                    type: data.type || 'AT',
                    port: data.port ? { value: data.port, label: data.port_name } : null,
                    item_name: data.item_name || '',
                    required_quantity: data.required_quantity || '',
                    cif_inr: data.cif_inr || '',
                    exchange_rate: data.exchange_rate || '',
                    cif_fc: data.cif_fc || '',
                    unit_value_per_unit: data.unit_value_per_unit || '',
                    invoice: mode === 'copy' ? '' : data.invoice || '',
                    estimated_arrival_date: data.estimated_arrival_date || '',
                    bl_detail: data.bl_detail || '',
                    is_boe: data.is_boe || false,
                    is_approved: mode === 'copy' ? false : data.is_approved || false
                });
            } catch (error) {
                console.error('Error fetching allotment:', error);
                toast.error('Failed to load allotment data');
            } finally {
                setInitialLoad(false);
            }
        };

        const fetchDefaultExchangeRate = async () => {
            setInitialLoad(true);
            try {
                const { data } = await api.get('masters/exchange-rates/', {
                    params: { page_size: 1, ordering: '-date' }
                });

                const defaultRate = data.results?.[0]?.usd || '';

                setFormData({
                    company: null,
                    type: 'AT',
                    port: null,
                    item_name: '',
                    required_quantity: '',
                    cif_inr: '',
                    exchange_rate: defaultRate,
                    cif_fc: '',
                    unit_value_per_unit: '',
                    invoice: '',
                    estimated_arrival_date: '',
                    bl_detail: '',
                    is_boe: false,
                    is_approved: false
                });
            } catch (error) {
                console.error('Error fetching exchange rate:', error);
                setFormData({
                    company: null,
                    type: 'AT',
                    port: null,
                    item_name: '',
                    required_quantity: '',
                    cif_inr: '',
                    exchange_rate: '',
                    cif_fc: '',
                    unit_value_per_unit: '',
                    invoice: '',
                    estimated_arrival_date: '',
                    bl_detail: '',
                    is_boe: false,
                    is_approved: false
                });
            } finally {
                setInitialLoad(false);
            }
        };

        if (show && allotmentId && (mode === 'edit' || mode === 'copy')) {
            fetchAllotmentData();
        } else if (show && mode === 'create') {
            fetchDefaultExchangeRate();
        }
    }, [show, allotmentId, mode]);

    const loadCompanyOptions = async (inputValue) => {
        try {
            const { data } = await api.get('masters/companies/', {
                params: { search: inputValue, page_size: 50 }
            });
            return data.results.map(company => ({
                value: company.id,
                label: company.name
            }));
        } catch (error) {
            console.error('Error loading companies:', error);
            return [];
        }
    };

    const loadPortOptions = async (inputValue) => {
        try {
            const { data } = await api.get('masters/ports/', {
                params: { search: inputValue, page_size: 50 }
            });
            return data.results.map(port => ({
                value: port.id,
                label: port.name
            }));
        } catch (error) {
            console.error('Error loading ports:', error);
            return [];
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setFieldErrors({});
        setNonFieldErrors([]);

        try {
            const payload: Record<string, any> = {
                company: formData.company?.value,
                type: formData.type,
                port: formData.port?.value,
                item_name: formData.item_name,
                required_quantity: formData.required_quantity,
                cif_inr: formData.cif_inr,
                exchange_rate: formData.exchange_rate,
                cif_fc: formData.cif_fc,
                unit_value_per_unit: formData.unit_value_per_unit,
                invoice: formData.invoice || null,
                estimated_arrival_date: formData.estimated_arrival_date || null,
                bl_detail: formData.bl_detail || null,
                is_boe: formData.is_boe,
                is_approved: formData.is_approved
            };

            let savedId = allotmentId;
            if (mode === 'edit') {
                await api.put(`allotments/${allotmentId}/`, payload);
                toast.success('Allotment updated successfully');
            } else {
                const response = await api.post('allotments/', payload);
                savedId = response.data.id;
                toast.success('Allotment created successfully');
            }

            if (onSuccess) onSuccess();
            onHide();

            // Navigate to allocation page after save
            if (onSaveNavigate && savedId) {
                onSaveNavigate(savedId);
            }
        } catch (error) {
            console.error('Error saving allotment:', error);
            const { fieldErrors: errors, nonFieldErrors: nonErrors } = extractFormErrors(error);
            setFieldErrors(errors);
            setNonFieldErrors(nonErrors);

            if (nonErrors.length > 0) {
                toast.error(formatNonFieldErrors(nonErrors));
            } else if (Object.keys(errors).length > 0) {
                toast.error('Please fix the errors in the form');
            } else {
                toast.error('Failed to save allotment');
            }
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field, value) => {
        setFormData(prev => {
            const updates: Record<string, any> = { [field]: value };
            const currentData: Record<string, any> = { ...prev, ...updates };

            // Auto-calculate cif_fc from unit_value_per_unit and required_quantity
            if ((field === "unit_value_per_unit" || field === "required_quantity" || field === "exchange_rate")
                && currentData.unit_value_per_unit && currentData.required_quantity) {
                const unitValue = parseFloat(currentData.unit_value_per_unit);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(unitValue) && !isNaN(requiredQty) && requiredQty > 0) {
                    updates.cif_fc = (unitValue * requiredQty).toFixed(2);
                    currentData.cif_fc = updates.cif_fc;
                }
            }
            // If cif_fc provided but unit_value not, calculate unit_value
            else if (field === "cif_fc" && currentData.cif_fc && currentData.required_quantity && !currentData.unit_value_per_unit) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0) {
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                    currentData.unit_value_per_unit = updates.unit_value_per_unit;
                }
            }

            // Calculate cif_fc from cif_inr and exchange_rate
            if ((field === "cif_inr" || field === "exchange_rate") && currentData.cif_inr && currentData.exchange_rate) {
                const cifInr = parseFloat(currentData.cif_inr);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifInr) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_fc = (cifInr / exchangeRate).toFixed(2);
                    currentData.cif_fc = updates.cif_fc;

                    // Also calculate unit_value_per_unit if we have required_quantity
                    if (currentData.required_quantity) {
                        const requiredQty = parseFloat(currentData.required_quantity);
                        if (!isNaN(requiredQty) && requiredQty > 0) {
                            updates.unit_value_per_unit = (Math.ceil((parseFloat(updates.cif_fc) / requiredQty) * 1000) / 1000).toFixed(3);
                        }
                    }
                }
            }
            // Calculate cif_inr from cif_fc and exchange_rate
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
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0 &&
                    (field === "cif_fc" || field === "required_quantity")) {
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                }
            }

            return { ...prev, ...updates };
        });
    };

    if (!show) return null;

    return (
        <Dialog open={show} onOpenChange={(o) => !o && !loading && onHide()}>
            <DialogContent className="max-h-[95vh] w-[95vw] max-w-4xl overflow-hidden p-0">
                {/* Custom gradient header */}
                <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' }}>
                    <h5 className="flex items-center gap-2 text-[1.15rem] font-semibold tracking-tight text-white">
                        <Package className="size-5" />
                        {mode === 'create' ? 'Create Allotment' : mode === 'edit' ? 'Edit Allotment' : 'Copy Allotment'}
                    </h5>
                    <button type="button" onClick={onHide} disabled={loading} aria-label="Close" className="flex size-8 cursor-pointer items-center justify-center rounded-sm border-0 bg-transparent text-white opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
                </div>

                    <form onSubmit={handleSubmit}>
                        <div className="overflow-y-auto bg-muted/40" style={{ maxHeight: 'calc(95vh - 130px)', padding: '1.5rem' }}>
                            {/* Non-Field Errors */}
                            {nonFieldErrors.length > 0 && (
                                <div className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive" role="alert">
                                    <TriangleAlert className="size-4 mt-0.5 shrink-0" /><div><strong className="font-semibold">Error:</strong> <span className="font-medium">{formatNonFieldErrors(nonFieldErrors)}</span></div>
                                </div>
                            )}

                            {initialLoad ? (
                                <div className="text-center py-5">
                                    <span className="inline-block size-7 animate-spin rounded-full border-2 border-current border-t-transparent text-primary" />
                                    <p className="mt-2 text-muted-foreground">Loading...</p>
                                </div>
                            ) : (
                                <div className="flex flex-col gap-3">

                                    {/* Section: Basic Information */}
                                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: '3px solid var(--tb-brand)' }}>
                                        <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-brand)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <Building2 className="size-4" aria-hidden="true" /> Basic Information
                                        </div>
                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                                            <div className="sm:col-span-3">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Company <span className="text-danger">*</span></label>
                                                <AsyncSelect
                                                    cacheOptions
                                                    defaultOptions
                                                    value={formData.company}
                                                    loadOptions={loadCompanyOptions}
                                                    onChange={(value) => handleChange('company', value)}
                                                    placeholder="Search company..."
                                                    isClearable
                                                    required
                                                    className={getFieldError(fieldErrors, 'company') ? 'is-invalid' : ''}
                                                />
                                                {getFieldError(fieldErrors, 'company') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>
                                                        <AlertCircle className="size-4" aria-hidden="true" />{getFieldError(fieldErrors, 'company')}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Type</label>
                                                <select
                                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm"
                                                    value={formData.type}
                                                    onChange={(e) => handleChange('type', e.target.value)}
                                                >
                                                    <option value="AT">Allotment</option>
                                                    <option value="UT">Utilization</option>
                                                </select>
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Port <span className="text-danger">*</span></label>
                                                <AsyncSelect
                                                    cacheOptions
                                                    defaultOptions
                                                    value={formData.port}
                                                    loadOptions={loadPortOptions}
                                                    onChange={(value) => handleChange('port', value)}
                                                    placeholder="Search port..."
                                                    isClearable
                                                    required
                                                    className={getFieldError(fieldErrors, 'port') ? 'is-invalid' : ''}
                                                />
                                                {getFieldError(fieldErrors, 'port') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>
                                                        <AlertCircle className="size-4" aria-hidden="true" />{getFieldError(fieldErrors, 'port')}
                                                    </div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-3">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Item Name</label>
                                                <input
                                                    type="text"
                                                    className={"flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive"}
                                                    value={formData.item_name}
                                                    onChange={(e) => handleChange('item_name', e.target.value)}
                                                    placeholder="Enter item name"
                                                />
                                                {getFieldError(fieldErrors, 'item_name') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'item_name')}</div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-3">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Required Quantity</label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    className={"flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive"}
                                                    value={formData.required_quantity}
                                                    onChange={(e) => handleChange('required_quantity', e.target.value)}
                                                    placeholder="0.00"
                                                />
                                                {getFieldError(fieldErrors, 'required_quantity') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'required_quantity')}</div>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Section: Financial Details */}
                                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: '3px solid var(--tb-success)' }}>
                                        <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-success)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <DollarSign className="size-4" aria-hidden="true" /> Financial Details
                                        </div>
                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>CIF INR</label>
                                                <div className="relative">
                                                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12px] font-semibold text-muted-foreground">₹</span>
                                                    <input type="number" step="0.01" className="flex h-9 w-full rounded-md border border-input bg-card pl-6 pr-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring" value={formData.cif_inr} onChange={(e) => handleChange('cif_inr', e.target.value)} placeholder="0.00" />
                                                </div>
                                                {getFieldError(fieldErrors, 'cif_inr') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'cif_inr')}</div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Exchange Rate</label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    className={"flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive"}
                                                    value={formData.exchange_rate}
                                                    onChange={(e) => handleChange('exchange_rate', e.target.value)}
                                                    placeholder="e.g. 83.50"
                                                />
                                                {getFieldError(fieldErrors, 'exchange_rate') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'exchange_rate')}</div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>CIF FC</label>
                                                <div className="relative">
                                                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12px] font-semibold text-muted-foreground">$</span>
                                                    <input type="number" step="0.01" className="flex h-9 w-full rounded-md border border-input bg-card pl-6 pr-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring" value={formData.cif_fc} onChange={(e) => handleChange('cif_fc', e.target.value)} placeholder="0.00" />
                                                </div>
                                                {getFieldError(fieldErrors, 'cif_fc') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'cif_fc')}</div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Unit Value / Unit</label>
                                                <div className="relative">
                                                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[12px] font-semibold text-muted-foreground">$</span>
                                                    <input type="number" step="0.001" className="flex h-9 w-full rounded-md border border-input bg-card pl-6 pr-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring" value={formData.unit_value_per_unit} onChange={(e) => handleChange('unit_value_per_unit', e.target.value)} placeholder="0.000" />
                                                </div>
                                                {getFieldError(fieldErrors, 'unit_value_per_unit') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'unit_value_per_unit')}</div>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Section: Additional Info */}
                                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: '3px solid var(--tb-warning)' }}>
                                        <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-warning-text)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <FileText className="size-4" aria-hidden="true" /> Additional Info
                                        </div>
                                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Invoice</label>
                                                <input
                                                    type="text"
                                                    className={"flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive"}
                                                    value={formData.invoice}
                                                    onChange={(e) => handleChange('invoice', e.target.value)}
                                                    placeholder="Invoice number"
                                                />
                                                {getFieldError(fieldErrors, 'invoice') && (
                                                    <div className="mt-0.5 text-[11.5px] text-destructive" style={{ fontSize: 12 }}>{getFieldError(fieldErrors, 'invoice')}</div>
                                                )}
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>Estimated Arrival Date</label>
                                                <input
                                                    type="date"
                                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm"
                                                    value={formData.estimated_arrival_date}
                                                    onChange={(e) => handleChange('estimated_arrival_date', e.target.value)}
                                                />
                                            </div>
                                            <div className="sm:col-span-2">
                                                <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground" style={{ fontSize: 12.5, fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>BL Detail</label>
                                                <textarea
                                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm"
                                                    rows={1}
                                                    value={formData.bl_detail}
                                                    onChange={(e) => handleChange('bl_detail', e.target.value)}
                                                    placeholder="BL detail"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* Section: Status */}
                                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '16px 20px', borderLeft: '3px solid var(--tb-brand)' }}>
                                        <div style={{ fontSize: 10.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-brand)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <ToggleRight className="size-4" aria-hidden="true" /> Status Flags
                                        </div>
                                        <div className="flex gap-4">
                                            <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium">
                                                <Switch
                                                    checked={formData.is_boe}
                                                    onCheckedChange={(v) => handleChange('is_boe', v)}
                                                />
                                                Is BOE
                                            </label>
                                            <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium">
                                                <Switch
                                                    checked={formData.is_approved}
                                                    onCheckedChange={(v) => handleChange('is_approved', v)}
                                                />
                                                Approved
                                            </label>
                                        </div>
                                    </div>

                                </div>
                            )}
                        </div>

                        <div className="flex justify-end gap-2 border-t border-border bg-muted/40 px-6 py-3">
                            <Button type="button" variant="outline" onClick={onHide} disabled={loading}>
                                <X className="size-4" />Cancel
                            </Button>
                            <Button type="submit" disabled={loading || initialLoad}>
                                {loading ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                                {loading ? 'Saving…' : mode === 'create' ? 'Create' : mode === 'edit' ? 'Update' : 'Create Copy'}
                            </Button>
                        </div>
                    </form>
            </DialogContent>
        </Dialog>
    );
}
