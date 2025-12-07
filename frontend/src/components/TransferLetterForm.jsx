import {useState, useEffect} from "react";
import { toast } from 'react-toastify';
import api from "../api/axios";
import CreatableSelect from 'react-select/creatable';

/**
 * Reusable Transfer Letter Form Component
 * Used by both Allotment and BOE pages
 */
export default function TransferLetterForm({
    instanceId,
    instanceType, // 'allotment' or 'boe'
    items, // Array of items with id, license_number, cif_fc, and purchase_status
    disabled = false,
    onSuccess,
    onError
}) {
    const [transferLetterData, setTransferLetterData] = useState({
        company: null,
        addressLine1: "",
        addressLine2: "",
        template: "",
        cifEdits: {}
    });
    const [companyOptions, setCompanyOptions] = useState([]);
    const [transferLetters, setTransferLetters] = useState([]);
    const [generating, setGenerating] = useState(false);
    const [selectedItems, setSelectedItems] = useState(items?.map(item => item.id) || []);

    useEffect(() => {
        fetchTransferLetters();
    }, []);

    useEffect(() => {
        // Update selected items when items prop changes
        setSelectedItems(items?.map(item => item.id) || []);
    }, [items]);

    const fetchTransferLetters = async () => {
        try {
            const {data} = await api.get('/masters/transfer-letters/');
            setTransferLetters(data.results || data || []);
        } catch (err) {
            toast.error("Failed to load transfer letters");
        }
    };

    const loadCompanyOptions = async (inputValue) => {
        try {
            const {data} = await api.get(`/masters/companies/?search=${inputValue}`);
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

    const handleCompanyChange = async (selectedCompany, actionMeta) => {
        setTransferLetterData(prev => ({
            ...prev,
            company: selectedCompany
        }));

        // Fetch and populate address if company is selected from existing options (not created)
        if (selectedCompany && selectedCompany.value && actionMeta.action !== 'create-option') {
            try {
                const {data} = await api.get(`/masters/companies/${selectedCompany.value}/`);

                setTransferLetterData(prev => ({
                    ...prev,
                    company: selectedCompany,
                    addressLine1: data.address_line_1 || "",
                    addressLine2: data.address_line_2 || ""
                }));
            } catch (err) {
                toast.error("Failed to fetch company details");
            }
        } else if (!selectedCompany) {
            setTransferLetterData(prev => ({
                ...prev,
                company: null,
                addressLine1: "",
                addressLine2: ""
            }));
        }
    };

    const handleCifEdit = (itemId, value) => {
        setTransferLetterData(prev => ({
            ...prev,
            cifEdits: {
                ...prev.cifEdits,
                [itemId]: value
            }
        }));
    };

    const handleRemoveItem = (itemId) => {
        setSelectedItems(prev => prev.filter(id => id !== itemId));
    };

    const handleAddItem = (itemId) => {
        setSelectedItems(prev => [...prev, itemId]);
    };

    const isItemSelected = (itemId) => selectedItems.includes(itemId);

    const handleGenerate = async (includeLicenseCopy = true) => {
        if (!transferLetterData.template) {
            onError?.("Please select a transfer letter template");
            return;
        }

        const finalCompanyName = transferLetterData.company?.label || '';
        if (!finalCompanyName.trim()) {
            onError?.("Please select or enter a company name");
            return;
        }

        if (selectedItems.length === 0) {
            onError?.("Please select at least one item to generate transfer letter");
            return;
        }

        setGenerating(true);

        // Filter CIF edits to only include selected items
        const filteredCifEdits = {};
        selectedItems.forEach(itemId => {
            if (transferLetterData.cifEdits[itemId] !== undefined) {
                filteredCifEdits[itemId] = transferLetterData.cifEdits[itemId];
            }
        });

        const requestData = {
            company_name: finalCompanyName.trim(),
            address_line1: transferLetterData.addressLine1.trim(),
            address_line2: transferLetterData.addressLine2.trim(),
            template_id: transferLetterData.template,
            cif_edits: filteredCifEdits,
            include_license_copy: includeLicenseCopy,
            selected_items: selectedItems
        };

        try {
            const endpoint = instanceType === 'allotment'
                ? `/allotment-actions/${instanceId}/generate-transfer-letter/`
                : `/bill-of-entries/${instanceId}/generate-transfer-letter/`;

            const response = await api.post(endpoint, requestData, {
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            const copyType = includeLicenseCopy ? 'WithCopy' : 'WithoutCopy';
            link.setAttribute('download', `TransferLetter_${instanceType}_${instanceId}_${copyType}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);

            const message = includeLicenseCopy
                ? "Transfer letter with license copy generated successfully"
                : "Transfer letter without license copy generated successfully";
            onSuccess?.(message);
        } catch (err) {
            onError?.(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGenerating(false);
        }
    };

    return (
        <div className="card mb-4">
            <div className="card-body">
                <h5 className="mb-3">Generate Transfer Letter</h5>

                {/* Company and Address Fields */}
                <div className="row mb-3">
                    <div className="col-md-4">
                        <label className="form-label">Company <span className="text-danger">*</span></label>
                        <CreatableSelect
                            value={transferLetterData.company}
                            onChange={handleCompanyChange}
                            onInputChange={(inputValue) => {
                                if (inputValue.length >= 2) {
                                    loadCompanyOptions(inputValue).then(options => setCompanyOptions(options));
                                }
                            }}
                            options={companyOptions}
                            placeholder="Type to search or enter company name..."
                            isClearable={true}
                            formatCreateLabel={(inputValue) => `Use: "${inputValue}"`}
                            isDisabled={disabled}
                        />
                        <small className="text-muted">Select from dropdown to auto-fill addresses, or type to create custom entry</small>
                    </div>
                    <div className="col-md-4">
                        <label className="form-label">Address Line 1</label>
                        <input
                            type="text"
                            className="form-control"
                            value={transferLetterData.addressLine1}
                            onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine1: e.target.value}))}
                            placeholder="Enter address line 1"
                            disabled={disabled}
                        />
                    </div>
                    <div className="col-md-4">
                        <label className="form-label">Address Line 2</label>
                        <input
                            type="text"
                            className="form-control"
                            value={transferLetterData.addressLine2}
                            onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine2: e.target.value}))}
                            placeholder="Enter address line 2"
                            disabled={disabled}
                        />
                    </div>
                </div>

                {/* Template Selection */}
                <div className="row mb-3">
                    <div className="col-md-6">
                        <label className="form-label">Template</label>
                        <select
                            className="form-select"
                            value={transferLetterData.template}
                            onChange={(e) => setTransferLetterData(prev => ({...prev, template: e.target.value}))}
                            disabled={disabled}
                        >
                            <option value="">— Select Transfer Letter Template —</option>
                            {transferLetters.map((tl) => (
                                <option key={tl.id} value={tl.id}>{tl.name}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Edit CIF (FC) per Item */}
                {items && items.length > 0 && (
                    <div className="mb-3">
                        <h6>Items for Transfer Letter ({selectedItems.length} of {items.length} selected)</h6>
                        <div className="table-responsive">
                            <table className="table table-sm table-bordered">
                                <thead className="table-light">
                                <tr>
                                    <th style={{width: '50px'}}>#</th>
                                    <th>License Number</th>
                                    <th>Purchase Status</th>
                                    <th style={{width: '150px'}}>CIF FC (editable)</th>
                                    <th style={{width: '100px'}}>Action</th>
                                </tr>
                                </thead>
                                <tbody>
                                {items.map((item, idx) => {
                                    const isSelected = isItemSelected(item.id);
                                    return (
                                        <tr key={item.id} className={!isSelected ? 'table-secondary' : ''}>
                                            <td>{idx + 1}</td>
                                            <td>{item.license_number || '-'}</td>
                                            <td>
                                                <span className={`badge ${
                                                    item.purchase_status === 'CO' ? 'bg-success' :
                                                    item.purchase_status === 'FS' ? 'bg-primary' :
                                                    item.purchase_status === 'PP' ? 'bg-warning' :
                                                    'bg-secondary'
                                                }`}>
                                                    {item.purchase_status || 'N/A'}
                                                </span>
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm"
                                                    value={transferLetterData.cifEdits[item.id] !== undefined
                                                        ? transferLetterData.cifEdits[item.id]
                                                        : parseFloat(item.cif_fc || 0).toFixed(2)}
                                                    onChange={(e) => handleCifEdit(item.id, e.target.value)}
                                                    step="0.01"
                                                    disabled={disabled || !isSelected}
                                                />
                                            </td>
                                            <td>
                                                {isSelected ? (
                                                    <button
                                                        className="btn btn-sm btn-danger"
                                                        onClick={() => handleRemoveItem(item.id)}
                                                        disabled={disabled}
                                                        title="Remove from transfer letter"
                                                    >
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                ) : (
                                                    <button
                                                        className="btn btn-sm btn-success"
                                                        onClick={() => handleAddItem(item.id)}
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

                {(!items || items.length === 0) && (
                    <div className="alert alert-warning">
                        No items found. Please add items first.
                    </div>
                )}

                {/* Generate Buttons */}
                <div className="d-flex justify-content-end gap-2">
                    <button
                        className="btn btn-primary"
                        onClick={() => handleGenerate(true)}
                        disabled={generating || disabled || !transferLetterData.template || selectedItems.length === 0}
                    >
                        {generating ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                Generating...
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-text me-2"></i>
                                With Copy ({selectedItems.length})
                            </>
                        )}
                    </button>
                    <button
                        className="btn btn-warning"
                        onClick={() => handleGenerate(false)}
                        disabled={generating || disabled || !transferLetterData.template || selectedItems.length === 0}
                    >
                        {generating ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                Generating...
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-text me-2"></i>
                                Without Copy ({selectedItems.length})
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
