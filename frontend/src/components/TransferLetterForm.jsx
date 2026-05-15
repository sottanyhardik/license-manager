import {useState, useEffect, useMemo} from "react";
import { toast } from 'react-toastify';
import api from "../api/axios";
import CreatableSelect from 'react-select/creatable';
import AsyncSelect from 'react-select/async';
import { formatDate } from '../utils/dateFormatter';

/**
 * Reusable Transfer Letter Form Component
 * Used by both Allotment and BOE pages
 */
export default function TransferLetterForm({
    instanceId,
    instanceType, // 'allotment' | 'boe' | 'trade'
    instanceIdentifier,
    items,
    disabled = false,
    onSuccess,
    onError
}) {
    const [parties, setParties] = useState([
        { id: 1, company: null, addressLine1: '', addressLine2: '', template: null }
    ]);
    const [companyOptions, setCompanyOptions] = useState([]);
    const [licenseEdits, setLicenseEdits] = useState({}); // {license_number: edited_total_cif}
    const [generating, setGenerating] = useState(null); // null | 'with_copy' | 'without_copy' | 'pdf'
    const [selectedItems, setSelectedItems] = useState(items?.map(item => item.id) || []);

    useEffect(() => {
        setSelectedItems(items?.map(item => item.id) || []);
    }, [items]);

    // Group items by license_number, summing CIF FC
    const groupedItems = useMemo(() => {
        const groups = {};
        (items || []).forEach(item => {
            const key = item.license_number || '-';
            if (!groups[key]) {
                groups[key] = {
                    license_number: key,
                    purchase_status: item.purchase_status,
                    item_ids: [],
                    total_cif: 0,
                };
            }
            groups[key].item_ids.push(item.id);
            groups[key].total_cif += parseFloat(item.cif_fc || 0);
        });
        return Object.values(groups);
    }, [items]);

    const loadCompanyOptions = async (inputValue) => {
        try {
            const {data} = await api.get(`masters/companies/?search=${inputValue}`);
            const results = data.results || data || [];
            return results.map(company => ({
                value: company.id,
                label: company.name,
                ...company
            }));
        } catch (err) {
            return [];
        }
    };

    const loadTransferLetterOptions = async (inputValue) => {
        try {
            const {data} = await api.get(`masters/transfer-letters/?search=${inputValue || ''}`);
            const results = data.results || data || [];
            return results.map(tl => ({value: tl.id, label: tl.name}));
        } catch (err) {
            return [];
        }
    };

    const addParty = () => {
        setParties(prev => [...prev, {
            id: Date.now(),
            company: null,
            addressLine1: '',
            addressLine2: '',
            template: null
        }]);
    };

    const removeParty = (id) => {
        setParties(prev => prev.filter(p => p.id !== id));
    };

    const updateParty = (id, updates) => {
        setParties(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
    };

    const handlePartyCompanyChange = async (id, selectedCompany, actionMeta) => {
        updateParty(id, { company: selectedCompany });

        if (selectedCompany && selectedCompany.value && actionMeta.action !== 'create-option') {
            try {
                const {data} = await api.get(`masters/companies/${selectedCompany.value}/`);
                updateParty(id, {
                    company: selectedCompany,
                    addressLine1: data.address_line_1 || '',
                    addressLine2: data.address_line_2 || '',
                });
            } catch (err) {
                toast.error("Failed to fetch company details");
            }
        } else if (!selectedCompany) {
            updateParty(id, { company: null, addressLine1: '', addressLine2: '' });
        }
    };

    const handleLicenseEdit = (licenseNumber, value) => {
        setLicenseEdits(prev => ({ ...prev, [licenseNumber]: value }));
    };

    const isGroupSelected = (licenseNumber) => {
        const group = groupedItems.find(g => g.license_number === licenseNumber);
        return group?.item_ids.every(id => selectedItems.includes(id)) ?? false;
    };

    const toggleGroup = (licenseNumber) => {
        const group = groupedItems.find(g => g.license_number === licenseNumber);
        if (!group) return;
        if (isGroupSelected(licenseNumber)) {
            setSelectedItems(prev => prev.filter(id => !group.item_ids.includes(id)));
        } else {
            setSelectedItems(prev => [...new Set([...prev, ...group.item_ids])]);
        }
    };

    const validParties = parties.filter(p => (p.company?.label || '').trim() && p.template);

    const handleGenerate = async (includeLicenseCopy = true, format = 'zip') => {
        const partiesWithoutTemplate = parties.filter(p => (p.company?.label || '').trim() && !p.template);
        if (partiesWithoutTemplate.length > 0) {
            onError?.(`Please select a template for all parties`);
            return;
        }

        if (validParties.length === 0) {
            onError?.("Please enter at least one company name and select its template");
            return;
        }

        const selectedGroups = groupedItems.filter(g => isGroupSelected(g.license_number));
        if (selectedGroups.length === 0) {
            onError?.("Please select at least one license to generate transfer letter");
            return;
        }

        if (format === 'pdf') {
            setGenerating('pdf');
        } else {
            setGenerating(includeLicenseCopy ? 'with_copy' : 'without_copy');
        }

        // Build per-item cif_edits from license-level edits:
        // set first item in group to edited total, remaining items to 0
        const filteredCifEdits = {};
        groupedItems.forEach(group => {
            const editedTotal = licenseEdits[group.license_number];
            if (editedTotal !== undefined) {
                const activeIds = group.item_ids.filter(id => selectedItems.includes(id));
                activeIds.forEach((id, idx) => {
                    filteredCifEdits[id] = idx === 0 ? editedTotal : '0';
                });
            }
        });

        const requestData = {
            parties: validParties.map(p => ({
                company_name: (p.company?.label || '').trim(),
                address_line1: p.addressLine1.trim(),
                address_line2: p.addressLine2.trim(),
                template_id: p.template?.value || p.template,
            })),
            cif_edits: filteredCifEdits,
            include_license_copy: format === 'pdf' ? true : includeLicenseCopy,
            selected_items: selectedItems,
            include_todays_date: true,
            format,
        };

        try {
            const endpoint = instanceType === 'allotment'
                ? `/allotment-actions/${instanceId}/generate-transfer-letter/`
                : instanceType === 'trade'
                ? `/trades/${instanceId}/generate-transfer-letter/`
                : `/bill-of-entries/${instanceId}/generate-transfer-letter/`;

            const response = await api.post(endpoint, requestData, {responseType: 'blob'});

            const identifier = instanceIdentifier || instanceId;
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;

            if (format === 'pdf') {
                link.setAttribute('download', `TransferLetter_${instanceType}_${identifier}.pdf`);
            } else {
                const copyType = includeLicenseCopy ? 'WithCopy' : 'WithoutCopy';
                link.setAttribute('download', `TransferLetter_${instanceType}_${identifier}_${copyType}.zip`);
            }

            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            const msg = format === 'pdf'
                ? `Transfer letter PDF generated successfully`
                : validParties.length > 1
                ? `Transfer letters for ${validParties.length} parties generated successfully`
                : `Transfer letter ${includeLicenseCopy ? 'with' : 'without'} license copy generated successfully`;
            onSuccess?.(msg);
        } catch (err) {
            onError?.(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGenerating(null);
        }
    };

    return (
        <div className="card mb-4">
            <div className="card-body">
                <h5 className="mb-3">Generate Transfer Letter</h5>

                {/* Recipients */}
                <div className="mb-3">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                        <label className="form-label mb-0 fw-semibold">
                            Recipients
                            {parties.length > 1 && (
                                <span className="badge bg-primary ms-2">{parties.length}</span>
                            )}
                        </label>
                        <button
                            type="button"
                            className="btn btn-sm btn-outline-secondary"
                            onClick={addParty}
                            disabled={disabled}
                        >
                            <i className="bi bi-plus-lg me-1"></i>Add Party
                        </button>
                    </div>

                    <div className="d-flex flex-column gap-2">
                        {parties.map((party, idx) => (
                            <div
                                key={party.id}
                                className="rounded border px-3 py-2"
                                style={{backgroundColor: '#f8f9fa'}}
                            >
                                <div className="row g-2 align-items-center">
                                    {parties.length > 1 && (
                                        <div className="col-auto">
                                            <span
                                                className="badge rounded-pill"
                                                style={{
                                                    backgroundColor: 'var(--primary-color)',
                                                    fontSize: '0.7rem',
                                                    minWidth: '22px'
                                                }}
                                            >
                                                {idx + 1}
                                            </span>
                                        </div>
                                    )}
                                    <div className="col-md-3">
                                        <CreatableSelect
                                            value={party.company}
                                            onChange={(val, action) => handlePartyCompanyChange(party.id, val, action)}
                                            onInputChange={(inputValue) => {
                                                if (inputValue.length >= 2) {
                                                    loadCompanyOptions(inputValue).then(opts => setCompanyOptions(opts));
                                                }
                                            }}
                                            options={companyOptions}
                                            placeholder="Company name..."
                                            isClearable
                                            formatCreateLabel={(v) => `Use: "${v}"`}
                                            isDisabled={disabled}
                                            styles={{
                                                control: (base) => ({...base, minHeight: '34px', fontSize: '0.875rem'}),
                                                valueContainer: (base) => ({...base, padding: '0 8px'}),
                                            }}
                                        />
                                    </div>
                                    <div className="col-md">
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={party.addressLine1}
                                            onChange={(e) => updateParty(party.id, {addressLine1: e.target.value})}
                                            placeholder="Address line 1"
                                            disabled={disabled}
                                        />
                                    </div>
                                    <div className="col-md">
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={party.addressLine2}
                                            onChange={(e) => updateParty(party.id, {addressLine2: e.target.value})}
                                            placeholder="Address line 2"
                                            disabled={disabled}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <AsyncSelect
                                            value={party.template}
                                            onChange={(val) => updateParty(party.id, {template: val})}
                                            loadOptions={loadTransferLetterOptions}
                                            defaultOptions
                                            cacheOptions
                                            placeholder="Template..."
                                            isClearable
                                            isDisabled={disabled}
                                            styles={{
                                                control: (base, state) => ({
                                                    ...base,
                                                    minHeight: '34px',
                                                    fontSize: '0.875rem',
                                                    borderColor: !party.template && (party.company?.label || '').trim()
                                                        ? '#ffc107'
                                                        : base.borderColor,
                                                }),
                                                valueContainer: (base) => ({...base, padding: '0 8px'}),
                                            }}
                                        />
                                    </div>
                                    {parties.length > 1 && (
                                        <div className="col-auto">
                                            <button
                                                type="button"
                                                className="btn btn-sm btn-outline-secondary"
                                                onClick={() => removeParty(party.id)}
                                                disabled={disabled}
                                                title="Remove party"
                                            >
                                                <i className="bi bi-x-lg"></i>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="d-flex justify-content-between mt-1">
                        <small className="text-muted">
                            Select from dropdown to auto-fill addresses, or type to create a custom entry
                        </small>
                        <small className="text-muted">
                            <i className="bi bi-info-circle me-1"></i>
                            Today's date ({formatDate(new Date())}) will be included automatically
                        </small>
                    </div>
                </div>

                {/* Items table */}
                {groupedItems.length > 0 && (
                    <div className="mb-3">
                        <h6>
                            Items for Transfer Letter ({groupedItems.filter(g => isGroupSelected(g.license_number)).length} of {groupedItems.length} selected)
                            {items.length > groupedItems.length && (
                                <span className="text-muted fw-normal ms-2" style={{fontSize: '0.8rem'}}>
                                    ({items.length} rows merged by license)
                                </span>
                            )}
                        </h6>
                        <div className="table-responsive">
                            <table className="table table-sm table-bordered">
                                <thead className="table-light">
                                <tr>
                                    <th style={{width: '50px'}}>#</th>
                                    <th>License Number</th>
                                    <th>Purchase Status</th>
                                    <th style={{width: '170px'}}>Total CIF FC (editable)</th>
                                    <th style={{width: '100px'}}>Action</th>
                                </tr>
                                </thead>
                                <tbody>
                                {groupedItems.map((group, idx) => {
                                    const isSelected = isGroupSelected(group.license_number);
                                    const displayCif = licenseEdits[group.license_number] !== undefined
                                        ? licenseEdits[group.license_number]
                                        : group.total_cif.toFixed(2);
                                    return (
                                        <tr key={group.license_number} className={!isSelected ? 'table-secondary' : ''}>
                                            <td>{idx + 1}</td>
                                            <td>
                                                {group.license_number}
                                                {group.item_ids.length > 1 && (
                                                    <span className="badge bg-info ms-2" style={{fontSize: '0.65rem'}}>
                                                        {group.item_ids.length} rows
                                                    </span>
                                                )}
                                            </td>
                                            <td>
                                                <span className={`badge ${
                                                    group.purchase_status === 'CO' ? 'bg-success' :
                                                    group.purchase_status === 'FS' ? 'bg-primary' :
                                                    group.purchase_status === 'PP' ? 'bg-warning' :
                                                    'bg-secondary'
                                                }`}>
                                                    {group.purchase_status || 'N/A'}
                                                </span>
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm"
                                                    value={displayCif}
                                                    onChange={(e) => handleLicenseEdit(group.license_number, e.target.value)}
                                                    step="0.01"
                                                    disabled={disabled || !isSelected}
                                                />
                                            </td>
                                            <td>
                                                {isSelected ? (
                                                    <button
                                                        className="btn btn-sm btn-outline-secondary"
                                                        onClick={() => toggleGroup(group.license_number)}
                                                        disabled={disabled}
                                                        title="Remove from transfer letter"
                                                    >
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                ) : (
                                                    <button
                                                        className="btn btn-sm btn-outline-secondary"
                                                        onClick={() => toggleGroup(group.license_number)}
                                                        disabled={disabled}
                                                        title="Add to transfer letter"
                                                    >
                                                        <i className="bi bi-plus-lg"></i>
                                                    </button>
                                                )}
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
                    <div className="alert alert-warning">
                        No items found. Please add items first.
                    </div>
                )}

                {/* Generate Buttons */}
                <div className="d-flex justify-content-end gap-2 flex-wrap">
                    <button
                        type="button"
                        className="btn btn-primary"
                        style={{ background: 'linear-gradient(135deg, #4F46E5, #4338CA)', border: 'none' }}
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (generating === null) handleGenerate(true, 'pdf');
                        }}
                        disabled={generating !== null || disabled || validParties.length === 0 || selectedItems.length === 0 || groupedItems.filter(g => isGroupSelected(g.license_number)).length === 0}
                        title="Download all TL pages merged into a single PDF"
                    >
                        {generating === 'pdf' ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                Generating...
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-pdf me-2"></i>
                                Download PDF
                            </>
                        )}
                    </button>
                    <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (generating === null) handleGenerate(true, 'zip');
                        }}
                        disabled={generating !== null || disabled || validParties.length === 0 || selectedItems.length === 0 || groupedItems.filter(g => isGroupSelected(g.license_number)).length === 0}
                    >
                        {generating === 'with_copy' ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                Generating...
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-zip me-2"></i>
                                With Copy ({groupedItems.filter(g => isGroupSelected(g.license_number)).length}{validParties.length > 1 ? ` × ${validParties.length} parties` : ''})
                            </>
                        )}
                    </button>
                    <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (generating === null) handleGenerate(false, 'zip');
                        }}
                        disabled={generating !== null || disabled || validParties.length === 0 || selectedItems.length === 0 || groupedItems.filter(g => isGroupSelected(g.license_number)).length === 0}
                    >
                        {generating === 'without_copy' ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                Generating...
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-zip me-2"></i>
                                Without Copy ({groupedItems.filter(g => isGroupSelected(g.license_number)).length}{validParties.length > 1 ? ` × ${validParties.length} parties` : ''})
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
