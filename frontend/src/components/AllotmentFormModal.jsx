import { useState, useEffect } from 'react';
import api from '../api/axios';
import { toast } from 'react-toastify';
import AsyncSelect from 'react-select/async';

export default function AllotmentFormModal({ show, onHide, allotmentId = null, mode = 'create', onSuccess, onSaveNavigate }) {
    const [formData, setFormData] = useState({
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

    useEffect(() => {
        if (show && allotmentId && (mode === 'edit' || mode === 'copy')) {
            fetchAllotmentData();
        } else if (show && mode === 'create') {
            fetchDefaultExchangeRate();
        }
    }, [show, allotmentId, mode]);

    const fetchAllotmentData = async () => {
        setInitialLoad(true);
        try {
            const { data } = await api.get(`/allotments/${allotmentId}/`);

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
            // Fetch the latest exchange rate
            const { data } = await api.get('/masters/exchange-rates/', {
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
            // Reset form with empty exchange rate if fetch fails
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

    const loadCompanyOptions = async (inputValue) => {
        try {
            const { data } = await api.get('/masters/companies/', {
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
            const { data } = await api.get('/masters/ports/', {
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

        try {
            const payload = {
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
                await api.put(`/allotments/${allotmentId}/`, payload);
                toast.success('Allotment updated successfully');
            } else {
                const response = await api.post('/allotments/', payload);
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
            toast.error(error.response?.data?.error || 'Failed to save allotment');
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field, value) => {
        setFormData(prev => {
            const updates = { [field]: value };
            const currentData = { ...prev, ...updates };

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
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}>
            <div className="modal-dialog modal-xl">
                <div className="modal-content" style={{
                    borderRadius: '12px',
                    boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
                    border: 'none'
                }}>
                    <div className="modal-header" style={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white',
                        borderTopLeftRadius: '12px',
                        borderTopRightRadius: '12px',
                        padding: '1.5rem',
                        borderBottom: 'none'
                    }}>
                        <h5 className="modal-title" style={{
                            fontWeight: '600',
                            fontSize: '1.25rem',
                            letterSpacing: '0.3px',
                            flex: 1
                        }}>
                            <i className="bi bi-box-arrow-in-down me-2"></i>
                            {mode === 'create' ? 'Create Allotment' : mode === 'edit' ? 'Edit Allotment' : 'Copy Allotment'}
                        </h5>
                        <button
                            type="button"
                            className="btn-close btn-close-white"
                            onClick={onHide}
                            disabled={loading}
                        ></button>
                    </div>

                    <form onSubmit={handleSubmit}>
                        <div className="modal-body" style={{ padding: '2rem', backgroundColor: '#f8f9fa' }}>
                            {initialLoad ? (
                                <div className="text-center py-5">
                                    <div className="spinner-border" style={{ color: '#667eea' }}></div>
                                    <p className="mt-2">Loading...</p>
                                </div>
                            ) : (
                                <div className="row g-3">
                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Company *</label>
                                        <AsyncSelect
                                            cacheOptions
                                            defaultOptions
                                            value={formData.company}
                                            loadOptions={loadCompanyOptions}
                                            onChange={(value) => handleChange('company', value)}
                                            placeholder="Search company..."
                                            isClearable
                                            required
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Type</label>
                                        <select
                                            className="form-select"
                                            value={formData.type}
                                            onChange={(e) => handleChange('type', e.target.value)}
                                        >
                                            <option value="AT">Allotment</option>
                                            <option value="UT">Utilization</option>
                                        </select>
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Port *</label>
                                        <AsyncSelect
                                            cacheOptions
                                            defaultOptions
                                            value={formData.port}
                                            loadOptions={loadPortOptions}
                                            onChange={(value) => handleChange('port', value)}
                                            placeholder="Search port..."
                                            isClearable
                                            required
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Item Name</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={formData.item_name}
                                            onChange={(e) => handleChange('item_name', e.target.value)}
                                            placeholder="Enter item name"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Required Quantity</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control"
                                            value={formData.required_quantity}
                                            onChange={(e) => handleChange('required_quantity', e.target.value)}
                                            placeholder="Enter required quantity"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">CIF INR</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control"
                                            value={formData.cif_inr}
                                            onChange={(e) => handleChange('cif_inr', e.target.value)}
                                            placeholder="Enter CIF INR"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Exchange Rate</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control"
                                            value={formData.exchange_rate}
                                            onChange={(e) => handleChange('exchange_rate', e.target.value)}
                                            placeholder="Enter exchange rate"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">CIF FC</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control"
                                            value={formData.cif_fc}
                                            onChange={(e) => handleChange('cif_fc', e.target.value)}
                                            placeholder="Enter CIF FC"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Unit Value Per Unit</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control"
                                            value={formData.unit_value_per_unit}
                                            onChange={(e) => handleChange('unit_value_per_unit', e.target.value)}
                                            placeholder="Enter unit value"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Invoice</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            value={formData.invoice}
                                            onChange={(e) => handleChange('invoice', e.target.value)}
                                            placeholder="Enter invoice"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">Estimated Arrival Date</label>
                                        <input
                                            type="date"
                                            className="form-control"
                                            value={formData.estimated_arrival_date}
                                            onChange={(e) => handleChange('estimated_arrival_date', e.target.value)}
                                        />
                                    </div>

                                    <div className="col-md-12">
                                        <label className="form-label fw-bold">BL Detail</label>
                                        <textarea
                                            className="form-control"
                                            rows="2"
                                            value={formData.bl_detail}
                                            onChange={(e) => handleChange('bl_detail', e.target.value)}
                                            placeholder="Enter BL detail"
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <div className="form-check">
                                            <input
                                                className="form-check-input"
                                                type="checkbox"
                                                id="isBoe"
                                                checked={formData.is_boe}
                                                onChange={(e) => handleChange('is_boe', e.target.checked)}
                                            />
                                            <label className="form-check-label fw-bold" htmlFor="isBoe">
                                                Is BOE
                                            </label>
                                        </div>
                                    </div>

                                    <div className="col-md-6">
                                        <div className="form-check">
                                            <input
                                                className="form-check-input"
                                                type="checkbox"
                                                id="isApproved"
                                                checked={formData.is_approved}
                                                onChange={(e) => handleChange('is_approved', e.target.checked)}
                                            />
                                            <label className="form-check-label fw-bold" htmlFor="isApproved">
                                                Approved
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="modal-footer" style={{
                            backgroundColor: '#f8f9fa',
                            borderTop: '1px solid #dee2e6',
                            padding: '1rem 2rem'
                        }}>
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={onHide}
                                disabled={loading}
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className="btn"
                                disabled={loading || initialLoad}
                                style={{
                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                    color: 'white',
                                    border: 'none'
                                }}
                            >
                                {loading ? (
                                    <>
                                        <span className="spinner-border spinner-border-sm me-2"></span>
                                        Saving...
                                    </>
                                ) : (
                                    <>
                                        <i className="bi bi-check-circle me-2"></i>
                                        {mode === 'create' ? 'Create' : mode === 'edit' ? 'Update' : 'Create Copy'}
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
