import React, {useEffect, useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {toast} from "react-toastify";
import Select from "react-select";

export default function ItemReport() {
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedItemNames, setSelectedItemNames] = useState([]);
    const [availableItems, setAvailableItems] = useState([]);
    const [minBalance, setMinBalance] = useState(200);
    const [minAvailQty, setMinAvailQty] = useState(0);
    const [licenseStatus, setLicenseStatus] = useState('active');
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [isRestricted, setIsRestricted] = useState('all'); // 'all', 'true', 'false'
    const [purchaseStatus, setPurchaseStatus] = useState(['GE', 'MI', 'SM']); // Default: GE, MI, SM

    // Inline edit states
    const [editingCell, setEditingCell] = useState(null); // {itemId, field}
    const [editValue, setEditValue] = useState("");
    const [togglingRestriction, setTogglingRestriction] = useState({});

    useEffect(() => {
        loadAvailableItems();
    }, []);

    useEffect(() => {
        // Only load report if at least one item name is selected
        if (selectedItemNames.length > 0) {
            loadReport();
        } else {
            setReportData(null);
        }
    }, [selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies, isRestricted, purchaseStatus]);

    const loadAvailableItems = async () => {
        try {
            const response = await api.get('item-report/available-items/');
            const items = response.data || [];
            setAvailableItems(items.map(item => ({value: item.id, label: item.name})));
        } catch (error) {
            console.error('Failed to load available items:', error);
            setAvailableItems([]);
        }
    };

    const loadReport = async () => {
        setLoading(true);
        try {
            let url = `reports/item-report/?format=json`;

            if (selectedItemNames.length > 0) {
                url += `&item_names=${selectedItemNames.join(',')}`;
            }

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }

            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }

            url += `&min_balance=${minBalance}`;
            url += `&min_avail_qty=${minAvailQty}`;
            url += `&license_status=${licenseStatus}`;

            if (isRestricted !== 'all') {
                url += `&is_restricted=${isRestricted}`;
            }

            if (purchaseStatus.length > 0) {
                url += `&purchase_status=${purchaseStatus.join(',')}`;
            }

            const response = await api.get(url);
            setReportData(response.data);
        } catch (error) {
            toast.error('Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = `reports/item-report/?format=excel`;

            if (selectedItemNames.length > 0) {
                url += `&item_names=${selectedItemNames.join(',')}`;
            }

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }

            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }

            url += `&min_balance=${minBalance}`;
            url += `&min_avail_qty=${minAvailQty}`;
            url += `&license_status=${licenseStatus}`;

            if (isRestricted !== 'all') {
                url += `&is_restricted=${isRestricted}`;
            }

            if (purchaseStatus.length > 0) {
                url += `&purchase_status=${purchaseStatus.join(',')}`;
            }

            const response = await api.get(url, {
                responseType: 'blob',
            });

            const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `item_report.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            toast.error('Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleItemNameChange = (values) => {
        setSelectedItemNames(values || []);
    };

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handlePurchaseStatusChange = (values) => {
        setPurchaseStatus(values || []);
    };

    const handleClearFilters = () => {
        setSelectedItemNames([]);
        setMinBalance(200);
        setMinAvailQty(0);
        setLicenseStatus('active');
        setSelectedCompanies([]);
        setExcludeCompanies([]);
        setIsRestricted('all');
        setPurchaseStatus(['GE', 'MI', 'SM']);
    };

    const hasActiveFilters = selectedItemNames.length > 0 || minBalance !== 200 || minAvailQty !== 0 || licenseStatus !== 'active' || selectedCompanies.length > 0 || excludeCompanies.length > 0 || isRestricted !== 'all' || (purchaseStatus.length !== 3 || !purchaseStatus.includes('GE') || !purchaseStatus.includes('MI') || !purchaseStatus.includes('SM'));

    // Inline editing handlers
    const startEdit = (itemId, field, currentValue) => {
        setEditingCell({itemId, field});
        setEditValue(currentValue || "");
    };

    const cancelEdit = () => {
        setEditingCell(null);
        setEditValue("");
    };

    const saveEdit = async (item) => {
        if (!editingCell) return;

        const {itemId, field} = editingCell;

        try {
            // Update notes or condition_sheet on the license
            const updateData = {};
            if (field === 'notes') {
                updateData.balance_report_notes = editValue;
            } else if (field === 'condition_sheet') {
                updateData.condition_sheet = editValue;
            }
            await api.patch(`licenses/${item.license_id}/`, updateData);

            toast.success('Updated successfully');
            cancelEdit();

            // Update only the current row instead of reloading entire report
            const updatedItems = reportData.items.map(i => {
                if (i.id === item.id) {
                    return {
                        ...i,
                        notes: field === 'notes' ? editValue : i.notes,
                        condition_sheet: field === 'condition_sheet' ? editValue : i.condition_sheet
                    };
                }
                return i;
            });

            setReportData({
                ...reportData,
                items: updatedItems
            });
        } catch (error) {
            toast.error('Failed to update. Please try again.');
        }
    };

    const handleItemNamesEdit = async (item, selectedOptions) => {
        try {
            const itemNameIds = selectedOptions ? selectedOptions.map(v => v.value) : [];
            await api.patch(`license-items/${item.id}/`, {
                items: itemNameIds
            });
            toast.success('Item names updated successfully');

            // Fetch updated item data to check if it still matches filters
            let url = `reports/item-report/?format=json`;
            if (selectedItemNames.length > 0) {
                url += `&item_names=${selectedItemNames.join(',')}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;
            if (isRestricted !== 'all') {
                url += `&is_restricted=${isRestricted}`;
            }

            const response = await api.get(url);
            const updatedReportData = response.data;

            // Find the updated item in the new data
            const updatedItem = updatedReportData.items.find(i => i.id === item.id);

            if (updatedItem) {
                // Item still matches filters - update the row
                const updatedItems = reportData.items.map(i =>
                    i.id === item.id ? updatedItem : i
                );
                setReportData({
                    ...reportData,
                    items: updatedItems
                });
            } else {
                // Item no longer matches filters - remove it from the list
                const filteredItems = reportData.items.filter(i => i.id !== item.id);
                setReportData({
                    ...reportData,
                    items: filteredItems,
                    total_items: filteredItems.length
                });
                toast.info('Item removed from list as it no longer matches the filters');
            }
        } catch (error) {
            toast.error('Failed to update item names. Please try again.');
        }
    };

    const handleToggleRestriction = async (item, e) => {
        e.stopPropagation();

        if (togglingRestriction[item.id]) return; // Prevent double clicks

        setTogglingRestriction({...togglingRestriction, [item.id]: true});

        try {
            const newValue = !item.is_restricted;
            await api.patch(`license-items/${item.id}/`, {
                is_restricted: newValue
            });

            // Update the item in the list
            const updatedItems = reportData.items.map(i => {
                if (i.id === item.id) {
                    return {...i, is_restricted: newValue};
                }
                // Update all items from the same license (they share is_restricted)
                if (i.license_id === item.license_id) {
                    return {...i, is_restricted: newValue};
                }
                return i;
            });

            setReportData({
                ...reportData,
                items: updatedItems
            });

            toast.success(`Is Restricted updated to ${newValue ? 'Yes' : 'No'}`);
        } catch (err) {
            console.error('Failed to toggle restriction:', err);
            toast.error('Failed to update Is Restricted');
        } finally {
            setTogglingRestriction({...togglingRestriction, [item.id]: false});
        }
    };

    const itemNameOptions = availableItems;

    return (
        <div className="container-fluid px-3 py-3" style={{backgroundColor: '#f8f9fa', minHeight: '100vh'}}>
            {/* Header Section */}
            <div className="row mb-4">
                <div className="col-12">
                    <div className="card shadow-sm border-0">
                        <div className="card-body">
                            <div className="d-flex justify-content-between align-items-center flex-wrap">
                                <div className="mb-2 mb-md-0">
                                    <h2 className="mb-1">
                                        <i className="bi bi-list-ul me-2 text-primary"></i>
                                        Item Report
                                    </h2>
                                    <p className="text-muted mb-0 small">
                                        {reportData && (
                                            <>
                                                <i className="bi bi-calendar-event me-1"></i>
                                                Report Date: {reportData.report_date}
                                                <span className="mx-2">•</span>
                                                <i className="bi bi-box-seam me-1"></i>
                                                Total Items: {reportData.total_items}
                                            </>
                                        )}
                                    </p>
                                </div>
                                <div className="d-flex gap-2">
                                    <button
                                        className="btn btn-success"
                                        onClick={handleExport}
                                        disabled={downloading || selectedItemNames.length === 0}
                                    >
                                        {downloading ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2" role="status"
                                                      aria-hidden="true"></span>
                                                Downloading...
                                            </>
                                        ) : (
                                            <>
                                                <i className="bi bi-file-earmark-excel me-2"></i>
                                                Export to Excel
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters Section */}
            <div className="row mb-4">
                <div className="col-12">
                    <div className="card shadow-sm border-0">
                        <div
                            className="card-header bg-white border-bottom d-flex justify-content-between align-items-center">
                            <h5 className="mb-0">
                                <i className="bi bi-sliders me-2"></i>
                                Filters
                            </h5>
                            {hasActiveFilters && (
                                <button className="btn btn-sm btn-outline-secondary" onClick={handleClearFilters}>
                                    <i className="bi bi-x-circle me-1"></i>
                                    Clear Filters
                                </button>
                            )}
                        </div>
                        <div className="card-body">
                            <div className="row g-3">
                                <div className="col-lg-2 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-currency-dollar me-1"></i>
                                        Min Balance (CIF)
                                    </label>
                                    <select
                                        className="form-select"
                                        value={minBalance}
                                        onChange={(e) => setMinBalance(parseInt(e.target.value))}
                                    >
                                        <option value="100">₹ 100</option>
                                        <option value="200">₹ 200</option>
                                        <option value="500">₹ 500</option>
                                        <option value="1000">₹ 1,000</option>
                                        <option value="5000">₹ 5,000</option>
                                        <option value="10000">₹ 10,000</option>
                                    </select>
                                </div>

                                <div className="col-lg-2 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-box-seam me-1"></i>
                                        Min Avail Qty
                                    </label>
                                    <select
                                        className="form-select"
                                        value={minAvailQty}
                                        onChange={(e) => setMinAvailQty(parseInt(e.target.value))}
                                    >
                                        <option value="0">0</option>
                                        <option value="100">100</option>
                                        <option value="500">500</option>
                                        <option value="1000">1,000</option>
                                        <option value="5000">5,000</option>
                                        <option value="10000">10,000</option>
                                    </select>
                                </div>

                                <div className="col-lg-2 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-calendar-check me-1"></i>
                                        License Status
                                    </label>
                                    <select
                                        className="form-select"
                                        value={licenseStatus}
                                        onChange={(e) => setLicenseStatus(e.target.value)}
                                    >
                                        <option value="active">Active</option>
                                        <option value="expiring_soon">Expiring Soon</option>
                                        <option value="expired">Expired</option>
                                        <option value="all">All</option>
                                    </select>
                                </div>

                                <div className="col-lg-3 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-building me-1"></i>
                                        Include Companies
                                    </label>
                                    <div style={{minHeight: '38px'}}>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={selectedCompanies}
                                            onChange={handleCompanyChange}
                                            isMulti={true}
                                            placeholder="All companies..."
                                            loadOnMount={false}
                                        />
                                    </div>
                                </div>

                                <div className="col-lg-3 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-dash-circle me-1"></i>
                                        Exclude Companies
                                    </label>
                                    <div style={{minHeight: '38px'}}>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={excludeCompanies}
                                            onChange={handleExcludeCompanyChange}
                                            isMulti={true}
                                            placeholder="None excluded..."
                                            loadOnMount={false}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="row g-3 mt-2">
                                <div className="col-lg-3 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-shield-lock me-1"></i>
                                        Is Restricted
                                    </label>
                                    <select
                                        className="form-select"
                                        value={isRestricted}
                                        onChange={(e) => setIsRestricted(e.target.value)}
                                    >
                                        <option value="all">All</option>
                                        <option value="true">Restricted</option>
                                        <option value="false">Not Restricted</option>
                                    </select>
                                </div>

                                <div className="col-lg-9 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-cart-check me-1"></i>
                                        Purchase Status
                                    </label>
                                    <Select
                                        isMulti
                                        value={[
                                            {value: 'GE', label: 'GE Purchase'},
                                            {value: 'GO', label: 'GE Operating'},
                                            {value: 'SM', label: 'SM Purchase'},
                                            {value: 'MI', label: 'Conversion'},
                                            {value: 'IP', label: 'IP'},
                                            {value: 'CO', label: 'CO'}
                                        ].filter(opt => purchaseStatus.includes(opt.value))}
                                        onChange={(selected) => handlePurchaseStatusChange(selected ? selected.map(s => s.value) : [])}
                                        options={[
                                            {value: 'GE', label: 'GE Purchase'},
                                            {value: 'GO', label: 'GE Operating'},
                                            {value: 'SM', label: 'SM Purchase'},
                                            {value: 'MI', label: 'Conversion'},
                                            {value: 'IP', label: 'IP'},
                                            {value: 'CO', label: 'CO'}
                                        ]}
                                        placeholder="Select purchase status..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                            </div>

                            <div className="row g-3 mt-2">
                                <div className="col-12">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-tag me-1"></i>
                                        Filter by Item Name (Multi-select)
                                    </label>
                                    <Select
                                        isMulti
                                        value={itemNameOptions.filter(opt => selectedItemNames.includes(opt.value))}
                                        onChange={(selected) => handleItemNameChange(selected ? selected.map(s => s.value) : [])}
                                        options={itemNameOptions}
                                        placeholder="Select item names..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                            </div>

                            {hasActiveFilters && (
                                <div className="mt-3">
                                    <div
                                        className="alert alert-info d-flex justify-content-between align-items-center py-2 mb-0">
                                        <div>
                                            <i className="bi bi-funnel-fill me-2"></i>
                                            <strong>Active Filters:</strong>
                                            {minBalance !== 200 && <span className="badge bg-primary ms-2">Min Balance: ₹{minBalance}</span>}
                                            {minAvailQty !== 0 && <span className="badge bg-primary ms-2">Min Qty: {minAvailQty}</span>}
                                            {licenseStatus !== 'active' && <span
                                                className="badge bg-primary ms-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                            {selectedCompanies.length > 0 && <span className="badge bg-primary ms-2">Incl. Companies: {selectedCompanies.length}</span>}
                                            {excludeCompanies.length > 0 && <span className="badge bg-primary ms-2">Excl. Companies: {excludeCompanies.length}</span>}
                                            {isRestricted !== 'all' && <span className="badge bg-primary ms-2">Is Restricted: {isRestricted === 'true' ? 'Yes' : 'No'}</span>}
                                            {purchaseStatus.length > 0 && purchaseStatus.length < 6 && <span className="badge bg-primary ms-2">Purchase Status: {purchaseStatus.length}</span>}
                                            {selectedItemNames.length > 0 && <span className="badge bg-primary ms-2">Item Names: {selectedItemNames.length}</span>}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Sticky Totals Bar */}
            {!loading && selectedItemNames.length > 0 && reportData && reportData.items.length > 0 && (
                <div className="row mb-3">
                    <div className="col-12">
                        <div className="card shadow-sm border-0" style={{
                            position: 'sticky',
                            top: '70px',
                            zIndex: 1020
                        }}>
                            <div className="card-body bg-light py-2">
                                <div className="d-flex justify-content-end align-items-center gap-4">
                                    <div className="fw-bold text-dark">Total:</div>
                                    <div className="d-flex align-items-center gap-2">
                                        <span className="text-muted small">Avail Qty:</span>
                                        <span className="fw-bold text-dark">
                                            {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                                minimumFractionDigits: 3,
                                                maximumFractionDigits: 3
                                            })}
                                        </span>
                                    </div>
                                    <div className="d-flex align-items-center gap-2">
                                        <span className="text-muted small">Avail Bal:</span>
                                        <span className="fw-bold text-success">
                                            {(() => {
                                                const uniqueLicenses = {};
                                                reportData.items.forEach(item => {
                                                    if (!uniqueLicenses[item.license_id]) {
                                                        uniqueLicenses[item.license_id] = item.available_balance || 0;
                                                    }
                                                });
                                                return Object.values(uniqueLicenses).reduce((sum, val) => sum + val, 0).toLocaleString('en-IN', {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                });
                                            })()}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Report Table */}
            <div className="row">
                <div className="col-12">
                    {loading && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <div className="spinner-border text-primary mb-3" role="status"
                                     style={{width: '3rem', height: '3rem'}}>
                                    <span className="visually-hidden">Loading...</span>
                                </div>
                                <h5 className="text-muted">Loading Item Report...</h5>
                                <p className="text-muted small">Please wait while we fetch the data</p>
                            </div>
                        </div>
                    )}

                    {!loading && selectedItemNames.length === 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-tag" style={{fontSize: '3rem', color: '#667eea'}}></i>
                                <h5 className="mt-3 text-primary">Select Item Names to View Report</h5>
                                <p className="text-muted">Please select at least one item name from the filter above to
                                    load the report data</p>
                            </div>
                        </div>
                    )}

                    {!loading && selectedItemNames.length > 0 && reportData && reportData.items.length === 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-inbox" style={{fontSize: '3rem', color: '#ccc'}}></i>
                                <h5 className="mt-3 text-muted">No items found</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                            </div>
                        </div>
                    )}

                    {!loading && selectedItemNames.length > 0 && reportData && reportData.items.length > 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body p-0">
                                <div className="table-responsive" style={{overflowX: 'auto'}}>
                                    <table className="table table-hover table-sm mb-0"
                                           style={{tableLayout: 'auto', minWidth: '1400px'}}>
                                        <thead style={{position: 'sticky', top: 0, zIndex: 10}}>
                                        <tr className="table-light">
                                            <th className="text-center" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: '#f8f9fa',
                                                minWidth: '60px'
                                            }}>Sr No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '60px',
                                                zIndex: 11,
                                                backgroundColor: '#f8f9fa',
                                                minWidth: '150px'
                                            }}>License No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '210px',
                                                zIndex: 11,
                                                backgroundColor: '#f8f9fa',
                                                minWidth: '120px'
                                            }}>License Date
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '330px',
                                                zIndex: 11,
                                                backgroundColor: '#f8f9fa',
                                                minWidth: '140px',
                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                borderRight: '2px solid #dee2e6'
                                            }}>Expiry Date
                                            </th>
                                            <th style={{minWidth: '100px'}}>Serial No</th>
                                            <th style={{minWidth: '100px'}}>HSN Code</th>
                                            <th style={{minWidth: '250px'}}>Product Description</th>
                                            <th style={{minWidth: '200px'}}>Item Name</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Qty</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Bal</th>
                                            <th className="text-center" style={{minWidth: '120px'}}>Is Restricted</th>
                                            <th style={{minWidth: '200px'}}>Notes</th>
                                            <th style={{minWidth: '200px'}}>Condition Sheet</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {(() => {
                                            // Group items by license_id
                                            const groupedByLicense = {};
                                            reportData.items.forEach(item => {
                                                if (!groupedByLicense[item.license_id]) {
                                                    groupedByLicense[item.license_id] = [];
                                                }
                                                groupedByLicense[item.license_id].push(item);
                                            });

                                            let srNo = 0;
                                            return Object.values(groupedByLicense).map((licenseItems) => {
                                                const firstItem = licenseItems[0];
                                                const rowSpan = licenseItems.length;

                                                return licenseItems.map((item, itemIdx) => {
                                                    srNo++;
                                                    const isFirstRow = itemIdx === 0;

                                                    return (
                                                        <tr key={item.id} style={{
                                                            borderBottom: itemIdx === licenseItems.length - 1 ? '2px solid #dee2e6' : '',
                                                            verticalAlign: 'middle'
                                                        }}>
                                                            {isFirstRow && (
                                                                <>
                                                                    <td className="text-center" rowSpan={rowSpan}
                                                                        style={{
                                                                            position: 'sticky',
                                                                            left: 0,
                                                                            zIndex: 9,
                                                                            verticalAlign: 'middle',
                                                                            backgroundColor: '#f8f9fa',
                                                                            fontWeight: '500'
                                                                        }}>{srNo - itemIdx}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '60px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa',
                                                                        fontWeight: '600'
                                                                    }}>
                                                                        <div
                                                                            className="d-flex align-items-center justify-content-between">
                                                                            <span>{firstItem.license_number}</span>
                                                                            <button
                                                                                className="btn btn-sm btn-outline-success ms-2"
                                                                                style={{
                                                                                    padding: '2px 8px',
                                                                                    fontSize: '0.75rem'
                                                                                }}
                                                                                onClick={() => {
                                                                                    window.open(`/api/licenses/${firstItem.license_id}/merged-documents/`, '_blank');
                                                                                }}
                                                                                title="View/Download merged documents"
                                                                            >
                                                                                Copy
                                                                            </button>
                                                                        </div>
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '210px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa'
                                                                    }}>{formatDate(firstItem.license_date)}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '330px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa',
                                                                        boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                        borderRight: '2px solid #dee2e6'
                                                                    }}>{formatDate(firstItem.license_expiry_date)}</td>
                                                                </>
                                                            )}
                                                            <td className="text-center"
                                                                style={{verticalAlign: 'middle'}}>{item.serial_number}</td>
                                                            <td style={{verticalAlign: 'middle'}}>{item.hs_code || '-'}</td>
                                                            <td style={{verticalAlign: 'middle'}}>{item.product_description || '-'}</td>
                                                            <td>
                                                                <Select
                                                                    isMulti
                                                                    value={item.item_names.map(i => ({
                                                                        value: i.id,
                                                                        label: i.name
                                                                    }))}
                                                                    onChange={(selected) => handleItemNamesEdit(item, selected)}
                                                                    options={itemNameOptions}
                                                                    placeholder="Select item names..."
                                                                    className="basic-multi-select"
                                                                    classNamePrefix="select"
                                                                    styles={{
                                                                        control: (base) => ({
                                                                            ...base,
                                                                            minHeight: '32px',
                                                                            fontSize: '0.875rem'
                                                                        })
                                                                    }}
                                                                />
                                                            </td>
                                                            <td className="text-end">{item.available_quantity.toFixed(3)}</td>
                                                            {isFirstRow && (
                                                                <>
                                                                    <td className="text-end text-success fw-semibold"
                                                                        rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa'
                                                                    }}>{firstItem.available_balance.toFixed(2)}</td>
                                                                    <td className="text-center" rowSpan={rowSpan}
                                                                        style={{
                                                                            verticalAlign: 'middle',
                                                                            backgroundColor: '#f8f9fa'
                                                                        }}>
                                                                        <span
                                                                            style={{cursor: togglingRestriction[firstItem.id] ? 'wait' : 'pointer', display: 'inline-block'}}
                                                                            onClick={(e) => handleToggleRestriction(firstItem, e)}
                                                                            title="Click to toggle"
                                                                        >
                                                                            {togglingRestriction[firstItem.id] ? (
                                                                                <span className="spinner-border spinner-border-sm" role="status"></span>
                                                                            ) : firstItem.is_restricted ? (
                                                                                <span className="badge bg-warning text-dark">
                                                                                    <i className="bi bi-shield-lock me-1"></i>
                                                                                    Yes
                                                                                </span>
                                                                            ) : (
                                                                                <span className="badge bg-success">
                                                                                    <i className="bi bi-shield-check me-1"></i>
                                                                                    No
                                                                                </span>
                                                                            )}
                                                                        </span>
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa'
                                                                    }}>
                                                                        {editingCell?.itemId === firstItem.id && editingCell?.field === 'notes' ? (
                                                                            <div className="d-flex gap-1">
                                                                                <input
                                                                                    type="text"
                                                                                    className="form-control form-control-sm"
                                                                                    value={editValue}
                                                                                    onChange={(e) => setEditValue(e.target.value)}
                                                                                    autoFocus
                                                                                />
                                                                                <button
                                                                                    className="btn btn-sm btn-success"
                                                                                    onClick={() => saveEdit(firstItem)}
                                                                                >
                                                                                    <i className="bi bi-check"></i>
                                                                                </button>
                                                                                <button
                                                                                    className="btn btn-sm btn-secondary"
                                                                                    onClick={cancelEdit}
                                                                                >
                                                                                    <i className="bi bi-x"></i>
                                                                                </button>
                                                                            </div>
                                                                        ) : (
                                                                            <div
                                                                                className="d-flex align-items-center justify-content-between"
                                                                                style={{cursor: 'pointer'}}
                                                                                onClick={() => startEdit(firstItem.id, 'notes', firstItem.notes)}
                                                                            >
                                                                                <span>{firstItem.notes || '-'}</span>
                                                                                <i className="bi bi-pencil text-muted ms-2"></i>
                                                                            </div>
                                                                        )}
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: '#f8f9fa'
                                                                    }}>
                                                                        {editingCell?.itemId === firstItem.id && editingCell?.field === 'condition_sheet' ? (
                                                                            <div className="d-flex gap-1">
                                                                                <input
                                                                                    type="text"
                                                                                    className="form-control form-control-sm"
                                                                                    value={editValue}
                                                                                    onChange={(e) => setEditValue(e.target.value)}
                                                                                    autoFocus
                                                                                />
                                                                                <button
                                                                                    className="btn btn-sm btn-success"
                                                                                    onClick={() => saveEdit(firstItem)}
                                                                                >
                                                                                    <i className="bi bi-check"></i>
                                                                                </button>
                                                                                <button
                                                                                    className="btn btn-sm btn-secondary"
                                                                                    onClick={cancelEdit}
                                                                                >
                                                                                    <i className="bi bi-x"></i>
                                                                                </button>
                                                                            </div>
                                                                        ) : (
                                                                            <div
                                                                                className="d-flex align-items-center justify-content-between"
                                                                                style={{cursor: 'pointer'}}
                                                                                onClick={() => startEdit(firstItem.id, 'condition_sheet', firstItem.condition_sheet)}
                                                                            >
                                                                                <span>{firstItem.condition_sheet || '-'}</span>
                                                                                <i className="bi bi-pencil text-muted ms-2"></i>
                                                                            </div>
                                                                        )}
                                                                    </td>
                                                                </>
                                                            )}
                                                        </tr>
                                                    );
                                                });
                                            });
                                        })()}
                                        </tbody>
                                        <tfoot style={{position: 'sticky', bottom: 0, zIndex: 10}}>
                                        <tr className="table-secondary fw-bold">
                                            <td colSpan="8" className="text-end" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: '#e2e3e5',
                                                fontWeight: '600'
                                            }}>
                                                Total:
                                            </td>
                                            <td className="text-end" style={{fontWeight: '600'}}>
                                                {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toFixed(3)}
                                            </td>
                                            <td className="text-end text-success" style={{fontWeight: '600'}}>
                                                {(() => {
                                                    // Calculate unique license balance total (don't double count licenses with multiple items)
                                                    const uniqueLicenses = {};
                                                    reportData.items.forEach(item => {
                                                        if (!uniqueLicenses[item.license_id]) {
                                                            uniqueLicenses[item.license_id] = item.available_balance || 0;
                                                        }
                                                    });
                                                    return Object.values(uniqueLicenses).reduce((sum, val) => sum + val, 0).toFixed(2);
                                                })()}
                                            </td>
                                            <td colSpan="3"></td>
                                        </tr>
                                        </tfoot>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
