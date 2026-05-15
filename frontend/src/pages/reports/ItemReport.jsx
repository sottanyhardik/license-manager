import React, {useEffect, useState, useMemo} from "react";
import {useNavigate} from "react-router-dom";
import AsyncSelectField from "../../components/AsyncSelectField";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {toast} from "react-toastify";
import Select from "react-select";
import {useDebouncedFilters} from "../../hooks/useDebounce";

export default function ItemReport() {
    const navigate = useNavigate();
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
    const [productDescSearch, setProductDescSearch] = useState('');
    const [hsnCodeSearch, setHsnCodeSearch] = useState('');
    const [selectedNorms, setSelectedNorms] = useState([]);
    const [selectedNotifications, setSelectedNotifications] = useState([]);
    const [expiryDateFrom, setExpiryDateFrom] = useState('');
    const [expiryDateTo, setExpiryDateTo] = useState('');

    // Inline edit states
    const [editingCell, setEditingCell] = useState(null); // {itemId, field}
    const [editValue, setEditValue] = useState("");
    const [togglingRestriction, setTogglingRestriction] = useState({});

    // Debounce all filters together - wait 500ms after last change
    const filters = useMemo(() => ({
        selectedItemNames,
        minBalance,
        minAvailQty,
        licenseStatus,
        selectedCompanies,
        excludeCompanies,
        isRestricted,
        purchaseStatus,
        productDescSearch,
        hsnCodeSearch,
        selectedNorms,
        selectedNotifications,
        expiryDateFrom,
        expiryDateTo
    }), [selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies, isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications, expiryDateFrom, expiryDateTo]);

    const { debouncedFilters, isPending } = useDebouncedFilters(filters, 500);

    useEffect(() => {
        let isMounted = true;

        const fetchItems = async () => {
            try {
                const response = await api.get('item-report/available-items/');
                const items = response.data || [];
                if (isMounted) {
                    setAvailableItems(items.map(item => ({value: item.id, label: item.name})));
                }
            } catch (error) {
                console.error('Failed to load available items:', error);
                if (isMounted) {
                    setAvailableItems([]);
                }
            }
        };

        fetchItems();

        return () => {
            isMounted = false;
        };
    }, []);

    useEffect(() => {
        // Load report if at least one item name is selected OR if searching by product description or HSN code
        // Uses debounced filters to avoid excessive API calls
        if (debouncedFilters.selectedItemNames.length > 0 || debouncedFilters.productDescSearch || debouncedFilters.hsnCodeSearch) {
            loadReport();
        } else {
            setReportData(null);
        }
    }, [debouncedFilters]);

    const loadReport = async () => {
        setLoading(true);
        try {
            let url = `reports/item-report/?format=json`;

            // Use debounced filter values
            const {
                selectedItemNames: items,
                selectedCompanies: companies,
                excludeCompanies: excluded,
                minBalance: minBal,
                minAvailQty: minQty,
                licenseStatus: status,
                isRestricted: restricted,
                purchaseStatus: pStatus,
                productDescSearch: prodDesc,
                hsnCodeSearch: hsnCode,
                selectedNorms: norms,
                selectedNotifications: notifications,
                expiryDateFrom: expFrom,
                expiryDateTo: expTo
            } = debouncedFilters;

            if (items.length > 0) {
                url += `&item_names=${items.join(',')}`;
            }

            if (companies.length > 0) {
                url += `&company_ids=${companies.join(',')}`;
            }

            if (excluded.length > 0) {
                url += `&exclude_company_ids=${excluded.join(',')}`;
            }

            url += `&min_balance=${minBal}`;
            url += `&min_avail_qty=${minQty}`;
            url += `&license_status=${status}`;

            if (restricted !== 'all') {
                url += `&is_restricted=${restricted}`;
            }

            if (pStatus.length > 0) {
                url += `&purchase_status=${pStatus.join(',')}`;
            }

            if (prodDesc) {
                url += `&product_description=${encodeURIComponent(prodDesc)}`;
            }

            if (hsnCode) {
                url += `&hsn_code=${encodeURIComponent(hsnCode)}`;
            }

            if (norms.length > 0) {
                url += `&norms=${norms.join(',')}`;
            }

            if (notifications.length > 0) {
                url += `&notification_numbers=${notifications.join(',')}`;
            }

            if (expFrom) url += `&expiry_date_from=${expFrom}`;
            if (expTo) url += `&expiry_date_to=${expTo}`;

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

            if (productDescSearch) {
                url += `&product_description=${encodeURIComponent(productDescSearch)}`;
            }

            if (hsnCodeSearch) {
                url += `&hsn_code=${encodeURIComponent(hsnCodeSearch)}`;
            }

            if (selectedNorms.length > 0) {
                url += `&norms=${selectedNorms.join(',')}`;
            }

            if (selectedNotifications.length > 0) {
                url += `&notification_numbers=${selectedNotifications.join(',')}`;
            }

            if (expiryDateFrom) url += `&expiry_date_from=${expiryDateFrom}`;
            if (expiryDateTo) url += `&expiry_date_to=${expiryDateTo}`;

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

    const handleNormsChange = (values) => {
        setSelectedNorms(values || []);
    };

    const handleNotificationsChange = (values) => {
        setSelectedNotifications(values || []);
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
        setProductDescSearch('');
        setHsnCodeSearch('');
        setSelectedNorms([]);
        setSelectedNotifications([]);
        setExpiryDateFrom('');
        setExpiryDateTo('');
    };

    const hasActiveFilters = selectedItemNames.length > 0 || minBalance !== 200 || minAvailQty !== 0 || licenseStatus !== 'active' || selectedCompanies.length > 0 || excludeCompanies.length > 0 || isRestricted !== 'all' || (purchaseStatus.length !== 3 || !purchaseStatus.includes('GE') || !purchaseStatus.includes('MI') || !purchaseStatus.includes('SM')) || productDescSearch !== '' || hsnCodeSearch !== '' || selectedNorms.length > 0 || selectedNotifications.length > 0 || expiryDateFrom !== '' || expiryDateTo !== '';

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
        <div style={{ minHeight: '100vh' }}>
            {/* Tabler-style page header */}
            <div className="page-header">
                <div style={{ minWidth: 0 }}>
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Reports
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Item Report
                    </div>
                    <h1>Item Report</h1>
                    {reportData && (
                        <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--tb-text-secondary)' }}>
                            <i className="bi bi-calendar-event me-1"></i>
                            {reportData.report_date}
                            <span style={{ margin: '0 8px', opacity: 0.5 }}>•</span>
                            <i className="bi bi-box-seam me-1"></i>
                            {reportData.total_items} items
                        </div>
                    )}
                </div>
                <div className="page-actions">
                    <button
                        type="button"
                        className="btn btn-outline-secondary btn-sm"
                        onClick={handleExport}
                        disabled={downloading || (selectedItemNames.length === 0 && !productDescSearch && !hsnCodeSearch)}
                    >
                        {downloading ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true" style={{ width: 12, height: 12 }} />
                                Generating…
                            </>
                        ) : (
                            <>
                                <i className="bi bi-file-earmark-excel me-1" aria-hidden="true"></i>
                                Excel
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Filters Section */}
            <div className="row mb-3">
                <div className="col-12">
                    <div className="surface-card">
                        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}
                             className="d-flex justify-content-between align-items-center">
                            <h5 className="mb-0" style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                                <i className="bi bi-sliders me-2" style={{ color: 'var(--primary-color)' }}></i>
                                Filters
                                {isPending && (
                                    <span className="ms-2" style={{ fontSize: '0.85rem', color: 'var(--bs-gray-500)' }}>
                                        <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                                        Updating...
                                    </span>
                                )}
                            </h5>
                            {hasActiveFilters && (
                                <button
                                    type="button"
                                    className="btn btn-outline-secondary btn-sm"
                                    onClick={handleClearFilters}
                                >
                                    <i className="bi bi-x-circle me-1"></i>
                                    Clear Filters
                                </button>
                            )}
                        </div>
                        <div style={{ padding: '14px 16px' }}>
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

                                <div className="col-lg-2 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-calendar-range me-1"></i>
                                        Expiry Date From
                                    </label>
                                    <input
                                        type="date"
                                        className="form-control"
                                        value={expiryDateFrom}
                                        onChange={(e) => setExpiryDateFrom(e.target.value)}
                                    />
                                </div>

                                <div className="col-lg-2 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-calendar-range me-1"></i>
                                        Expiry Date To
                                    </label>
                                    <input
                                        type="date"
                                        className="form-control"
                                        value={expiryDateTo}
                                        onChange={(e) => setExpiryDateTo(e.target.value)}
                                    />
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

                                <div className="col-lg-6 col-md-6">
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

                                <div className="col-lg-3 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-tags me-1"></i>
                                        Norms
                                    </label>
                                    <Select
                                        isMulti
                                        value={[
                                            {value: 'E1', label: 'E1'},
                                            {value: 'E5', label: 'E5'},
                                            {value: 'E126', label: 'E126'},
                                            {value: 'E132', label: 'E132'}
                                        ].filter(opt => selectedNorms.includes(opt.value))}
                                        onChange={(selected) => handleNormsChange(selected ? selected.map(s => s.value) : [])}
                                        options={[
                                            {value: 'E1', label: 'E1'},
                                            {value: 'E5', label: 'E5'},
                                            {value: 'E126', label: 'E126'},
                                            {value: 'E132', label: 'E132'}
                                        ]}
                                        placeholder="Select norms..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>

                                <div className="col-lg-3 col-md-6">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-bell me-1"></i>
                                        Notification
                                    </label>
                                    <Select
                                        isMulti
                                        value={[
                                            {value: '019/2015', label: '019/2015'},
                                            {value: '098/2009', label: '098/2009'},
                                            {value: '025/2023', label: '025/2023'}
                                        ].filter(opt => selectedNotifications.includes(opt.value))}
                                        onChange={(selected) => handleNotificationsChange(selected ? selected.map(s => s.value) : [])}
                                        options={[
                                            {value: '019/2015', label: '019/2015'},
                                            {value: '098/2009', label: '098/2009'},
                                            {value: '025/2023', label: '025/2023'}
                                        ]}
                                        placeholder="Select notification..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                            </div>

                            <div className="row g-3 mt-2">
                                <div className="col-lg-6 col-md-12">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-file-text me-1"></i>
                                        Product Description
                                    </label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Search by product description..."
                                        value={productDescSearch}
                                        onChange={(e) => setProductDescSearch(e.target.value)}
                                    />
                                </div>
                                <div className="col-lg-6 col-md-12">
                                    <label className="form-label fw-bold mb-2">
                                        <i className="bi bi-upc-scan me-1"></i>
                                        HSN Code
                                    </label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Search by HSN code..."
                                        value={hsnCodeSearch}
                                        onChange={(e) => setHsnCodeSearch(e.target.value)}
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
                                            {productDescSearch !== '' && <span className="badge bg-primary ms-2">Product Desc: "{productDescSearch}"</span>}
                                            {hsnCodeSearch !== '' && <span className="badge bg-primary ms-2">HSN Code: "{hsnCodeSearch}"</span>}
                                            {selectedNorms.length > 0 && <span className="badge bg-primary ms-2">Norms: {selectedNorms.length}</span>}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Sticky Totals Bar */}
            {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length > 0 && (
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
                                    <div className="d-flex align-items-center gap-2">
                                        <span className="text-muted small">Balance CIF:</span>
                                        <span className="fw-bold text-primary">
                                            {(() => {
                                                const uniqueLicenses = {};
                                                reportData.items.forEach(item => {
                                                    if (!uniqueLicenses[item.license_id]) {
                                                        uniqueLicenses[item.license_id] = item.balance_cif || 0;
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

                    {!loading && selectedItemNames.length === 0 && !productDescSearch && !hsnCodeSearch && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-tag" style={{fontSize: '3rem', color: 'var(--primary-color)'}}></i>
                                <h5 className="mt-3 text-primary">Select Filters to View Report</h5>
                                <p className="text-muted">Please select item names, search by product description, or search by HSN code to load the report data</p>
                            </div>
                        </div>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length === 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-inbox" style={{fontSize: '3rem', color: 'var(--bs-gray-300)'}}></i>
                                <h5 className="mt-3 text-muted">No items found</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                                <div className="mt-3 text-start" style={{maxWidth: '600px', margin: '0 auto'}}>
                                    <p className="small text-muted mb-2"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
                                    <ul className="small text-muted">
                                        <li>Setting License Status to "All"</li>
                                        <li>Lowering the Min Balance (CIF) to 100</li>
                                        <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length > 0 && (
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
                                                backgroundColor: 'var(--bs-gray-50)',
                                                minWidth: '60px'
                                            }}>Sr No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '60px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--bs-gray-50)',
                                                minWidth: '150px'
                                            }}>License No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '210px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--bs-gray-50)',
                                                minWidth: '120px'
                                            }}>License Date
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '330px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--bs-gray-50)',
                                                minWidth: '140px',
                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                borderRight: '2px solid #dee2e6'
                                            }}>Expiry Date
                                            </th>
                                            <th style={{minWidth: '200px'}}>Exporter Name</th>
                                            <th style={{minWidth: '100px'}}>Serial No</th>
                                            <th style={{minWidth: '100px'}}>HSN Code</th>
                                            <th style={{minWidth: '250px'}}>Product Description</th>
                                            <th style={{minWidth: '200px'}}>Item Name</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Qty</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Bal</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Balance CIF</th>
                                            <th className="text-center" style={{minWidth: '120px'}}>Is Restricted</th>
                                            <th style={{minWidth: '200px'}}>Notes</th>
                                            <th style={{minWidth: '200px'}}>Condition Sheet</th>
                                            <th style={{minWidth: '250px'}}>Transfer Status</th>
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
                                                                            backgroundColor: 'var(--bs-gray-50)',
                                                                            fontWeight: '500'
                                                                        }}>{srNo - itemIdx}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '60px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)',
                                                                        fontWeight: '600'
                                                                    }}>
                                                                        <div
                                                                            className="d-flex align-items-center justify-content-between">
                                                                            <span>{firstItem.license_number}</span>
                                                                            <button
                                                                                className="btn btn-sm btn-outline-secondary ms-2"
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
                                                                        backgroundColor: 'var(--bs-gray-50)'
                                                                    }}>{formatDate(firstItem.license_date)}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '330px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)',
                                                                        boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                        borderRight: '2px solid #dee2e6'
                                                                    }}>{formatDate(firstItem.license_expiry_date)}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)'
                                                                    }}>{firstItem.exporter_name || '-'}</td>
                                                                </>
                                                            )}
                                                            <td className="text-center"
                                                                style={{verticalAlign: 'middle'}}>
                                                                {item.serial_number}
                                                                <ConditionBadge type={item.condition_type} size="xs" />
                                                            </td>
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
                                                                        backgroundColor: 'var(--bs-gray-50)'
                                                                    }}>{firstItem.available_balance.toFixed(2)}</td>
                                                                    <td className="text-end text-primary fw-semibold"
                                                                        rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)'
                                                                    }}>{firstItem.balance_cif.toFixed(2)}</td>
                                                                    <td className="text-center" rowSpan={rowSpan}
                                                                        style={{
                                                                            verticalAlign: 'middle',
                                                                            backgroundColor: 'var(--bs-gray-50)'
                                                                        }}>
                                                                        {/* Restriction is derived from condition_type (licence's
                                                                            condition sheet) — read-only display. */}
                                                                        {firstItem.condition_type
                                                                            ? <ConditionBadge type={firstItem.condition_type} />
                                                                            : <span className="badge bg-success">
                                                                                  <i className="bi bi-shield-check me-1"></i>Open
                                                                              </span>}
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)'
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
                                                                        backgroundColor: 'var(--bs-gray-50)'
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
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--bs-gray-50)',
                                                                        fontSize: '0.85rem',
                                                                        lineHeight: '1.4'
                                                                    }}>
                                                                        {firstItem.latest_transfer ? (
                                                                            <div>{firstItem.latest_transfer}</div>
                                                                        ) : (
                                                                            <span className="text-muted">-</span>
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
                                            <td colSpan="10" className="text-end" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: 'var(--bs-gray-200)',
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
                                            <td colSpan="4"></td>
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
