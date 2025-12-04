import React, {useEffect, useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {formatIndianNumber} from "../../utils/numberFormatter";

export default function ItemPivotReport() {
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [sionNorms, setSionNorms] = useState([]);
    const [filtersCollapsed, setFiltersCollapsed] = useState(false);
    const [activeNormTab, setActiveNormTab] = useState(null);
    const [availableNorms, setAvailableNorms] = useState([]);
    const [minBalance, setMinBalance] = useState(200);
    const [licenseStatus, setLicenseStatus] = useState('active');

    useEffect(() => {
        loadFilterOptions();
        loadAvailableNorms();
    }, []);

    // Reload available norms when filters change (but not on initial mount)
    useEffect(() => {
        // Skip first render (already loaded above)
        if (minBalance !== 200 || licenseStatus !== 'active') {
            loadAvailableNorms();
        }
    }, [minBalance, licenseStatus]);

    // Load report when active norm tab changes or filters change
    useEffect(() => {
        if (activeNormTab) {
            loadReport(activeNormTab);
        }
    }, [activeNormTab, selectedCompanies, excludeCompanies, minBalance, licenseStatus]);

    const loadFilterOptions = async () => {
        try {
            // Load SION norms (only active ones)
            const normsResponse = await api.get('masters/sion-classes/?is_active=true');
            const normsData = normsResponse.data?.results || normsResponse.data || [];
            setSionNorms(Array.isArray(normsData) ? normsData : []);
        } catch (error) {
            console.error('Error loading filter options:', error);
            setSionNorms([]);
        }
    };

    const loadAvailableNorms = async () => {
        try {
            // Fetch only the list of norm classes (lightweight endpoint)
            let url = `item-pivot/available-norms/`;
            console.log('Fetching available norms from:', url);
            const response = await api.get(url);
            console.log('Response:', response);
            console.log('Response data:', response.data);

            const norms = response.data || [];
            // Response is now array of {norm_class, description} objects
            setAvailableNorms(Array.isArray(norms) ? norms : []);

            // Don't automatically set first norm as active - wait for user click
            console.log('Available norms loaded:', norms.length);
        } catch (error) {
            console.error('Error loading available norms:', error);
            console.error('Error details:', error.response?.data);
            setAvailableNorms([]);
        }
    };

    const loadReport = async (normClass) => {
        if (!normClass) return;

        setLoading(true);
        try {
            let url = `license/reports/item-pivot/?format=json&days=30&sion_norm=${normClass}`;

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;

            console.log('Fetching report for norm:', normClass, 'URL:', url);
            const response = await api.get(url);
            console.log('Report data received:', response.data);
            setReportData(response.data);
        } catch (error) {
            console.error('Error loading report:', error);
            alert('Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = `license/reports/item-pivot/?format=excel&days=30`;

            if (activeNormTab) {
                url += `&sion_norm=${activeNormTab}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;

            const response = await api.get(url, {
                responseType: 'blob',
            });

            const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `item_pivot_report.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error('Error downloading report:', error);
            alert('Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handleClearFilters = () => {
        setSelectedCompanies([]);
        setExcludeCompanies([]);
        setMinBalance(200);
        setLicenseStatus('active');
    };

    const hasActiveFilters = selectedCompanies.length > 0 || excludeCompanies.length > 0 || minBalance !== 200 || licenseStatus !== 'active';

    const getTotalLicenseCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            Object.values(notifications).forEach(licenses => {
                total += licenses.length;
            });
        });
        return total;
    };

    const getTotalNotificationCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            total += Object.keys(notifications).length;
        });
        return total;
    };

    // Calculate summary for a notification
    const calculateNotificationSummary = (licenses) => {
        const summary = {
            openingBalance: 0,
            regularItems: {},
            restrictedItemsByPercentage: {}, // Group by restriction percentage
            totalAvailable: 0
        };

        // Calculate opening balance (sum of all license balances)
        licenses.forEach(license => {
            const balance = parseFloat(license.balance_cif || 0);
            summary.openingBalance += balance;
        });

        // First pass: Calculate restriction values per license (not per item, as it's shared)
        const processedRestrictions = new Set(); // Track processed license+percentage combinations
        licenses.forEach(license => {
            if (reportData?.items) {
                reportData.items.forEach(item => {
                    const itemData = license.items?.[item.name];
                    if (itemData && itemData.restriction !== null && itemData.restriction !== undefined) {
                        const restrictionPercentage = parseFloat(itemData.restriction || 0);
                        const restrictionKey = `${license.license_number}_${restrictionPercentage}`;

                        // Only add restriction value once per license per percentage
                        if (!processedRestrictions.has(restrictionKey)) {
                            processedRestrictions.add(restrictionKey);

                            if (!summary.restrictedItemsByPercentage[restrictionPercentage]) {
                                summary.restrictedItemsByPercentage[restrictionPercentage] = {
                                    items: {},
                                    sharedRestrictionValue: 0
                                };
                            }
                            summary.restrictedItemsByPercentage[restrictionPercentage].sharedRestrictionValue += parseFloat(itemData.restriction_value || 0);
                        }
                    }
                });
            }
        });

        // Second pass: Calculate item quantities
        if (reportData?.items) {
            reportData.items.forEach(item => {
                let itemAvailable = 0;
                let hasRestriction = false;
                let restrictionPercentage = 0;

                licenses.forEach(license => {
                    const itemData = license.items?.[item.name];
                    if (itemData) {
                        // Available quantity
                        itemAvailable += parseFloat(itemData.available_quantity || 0);

                        // Check if item has restriction
                        if (itemData.restriction !== null && itemData.restriction !== undefined) {
                            hasRestriction = true;
                            restrictionPercentage = parseFloat(itemData.restriction || 0);
                        }
                    }
                });

                if (itemAvailable > 0) {
                    const itemSummary = {
                        available: itemAvailable
                    };

                    if (hasRestriction) {
                        // Add item to its restriction percentage group
                        if (!summary.restrictedItemsByPercentage[restrictionPercentage]) {
                            summary.restrictedItemsByPercentage[restrictionPercentage] = {
                                items: {},
                                sharedRestrictionValue: 0
                            };
                        }
                        summary.restrictedItemsByPercentage[restrictionPercentage].items[item.name] = itemSummary;
                    } else {
                        summary.regularItems[item.name] = itemSummary;
                    }

                    summary.totalAvailable += itemAvailable;
                }
            });
        }

        return summary;
    };


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
                                        <i className="bi bi-table me-2 text-primary"></i>
                                        Item Pivot Report
                                    </h2>
                                    <p className="text-muted mb-0 small">
                                        {reportData && (
                                            <>
                                                <i className="bi bi-calendar-event me-1"></i>
                                                Report Date: {reportData.report_date}
                                                <span className="mx-2">•</span>
                                            </>
                                        )}
                                        <i className="bi bi-tag-fill me-1"></i>
                                        Active Norm: {activeNormTab || 'Loading...'}
                                        {reportData && (
                                            <>
                                                <span className="mx-2">•</span>
                                                <i className="bi bi-bell me-1"></i>
                                                {getTotalNotificationCount()} Notifications
                                                <span className="mx-2">•</span>
                                                <i className="bi bi-file-text me-1"></i>
                                                {getTotalLicenseCount()} Licenses
                                            </>
                                        )}
                                    </p>
                                </div>
                                <div className="d-flex gap-2">
                                    <button
                                        className="btn btn-outline-primary"
                                        onClick={() => setFiltersCollapsed(!filtersCollapsed)}
                                    >
                                        <i className={`bi bi-funnel${hasActiveFilters ? '-fill' : ''} me-2`}></i>
                                        {filtersCollapsed ? 'Show' : 'Hide'} Filters
                                        {hasActiveFilters && <span className="badge bg-primary ms-2">Active</span>}
                                    </button>
                                    <button
                                        className="btn btn-success"
                                        onClick={handleExport}
                                        disabled={downloading}
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
            {!filtersCollapsed && (
                <div className="row mb-4">
                    <div className="col-12">
                        <div className="card shadow-sm border-0" style={{maxWidth: '1400px'}}>
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
                                    <div className="col-lg-3 col-md-6">
                                        <label className="form-label fw-bold mb-2">
                                            <i className="bi bi-currency-dollar me-1"></i>
                                            Minimum Balance (CIF)
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

                                    <div className="col-lg-3 col-md-6">
                                        <label className="form-label fw-bold mb-2">
                                            <i className="bi bi-calendar-check me-1"></i>
                                            License Status
                                        </label>
                                        <select
                                            className="form-select"
                                            value={licenseStatus}
                                            onChange={(e) => setLicenseStatus(e.target.value)}
                                        >
                                            <option value="active">Active ({">"} 1 month)</option>
                                            <option value="expiring_soon">Expiring Soon (≤ 30 days)</option>
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

                                {hasActiveFilters && (
                                    <div className="mt-3">
                                        <div
                                            className="alert alert-info d-flex justify-content-between align-items-center py-2 mb-0">
                                            <div>
                                                <i className="bi bi-funnel-fill me-2"></i>
                                                <strong>Active Filters:</strong>
                                                {minBalance !== 200 && <span className="badge bg-primary ms-2">Min Balance: ₹{minBalance}</span>}
                                                {licenseStatus !== 'active' && <span
                                                    className="badge bg-primary ms-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                                {selectedCompanies.length > 0 && <span
                                                    className="badge bg-primary ms-2">Incl. Companies: {selectedCompanies.length}</span>}
                                                {excludeCompanies.length > 0 && <span className="badge bg-primary ms-2">Excl. Companies: {excludeCompanies.length}</span>}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Norm Tabs */}
            <div className="row mb-4">
                <div className="col-12">
                    <div className="card shadow-sm border-0">
                        <div className="card-body p-3">
                            <h6 className="mb-3 text-primary">
                                <i className="bi bi-tag-fill me-2"></i>
                                Available Norms ({availableNorms.length})
                                <small className="text-muted ms-2">(includes E1, E5, E126, E132 conversion norms)</small>
                            </h6>
                            {availableNorms.length > 0 ? (
                                <div className="d-flex flex-wrap gap-2">
                                    {availableNorms.map((normObj) => {
                                        const normClass = normObj.norm_class || normObj;
                                        const description = normObj.description || '';
                                        const isConversionNorm = ['E1', 'E5', 'E126', 'E132'].includes(normClass);
                                        return (
                                            <button
                                                key={normClass}
                                                className={`btn btn-sm ${activeNormTab === normClass ? (isConversionNorm ? 'btn-success' : 'btn-primary') : (isConversionNorm ? 'btn-outline-success' : 'btn-outline-primary')}`}
                                                onClick={() => {
                                                    if (activeNormTab !== normClass) {
                                                        setReportData(null);
                                                    }
                                                    setActiveNormTab(normClass);
                                                }}
                                                type="button"
                                                style={{
                                                    minWidth: '120px',
                                                    fontWeight: activeNormTab === normClass ? 'bold' : 'normal',
                                                    transition: 'all 0.3s ease',
                                                    textAlign: 'center',
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    alignItems: 'center',
                                                    padding: '8px 12px'
                                                }}
                                            >
                                                <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: description ? '4px' : '0'}}>
                                                    <i className={`bi ${isConversionNorm ? 'bi-arrow-repeat' : 'bi-tag-fill'} me-1`}></i>
                                                    <span style={{fontSize: '1rem', fontWeight: '600'}}>{normClass}</span>
                                                    {loading && activeNormTab === normClass && (
                                                        <span className="spinner-border spinner-border-sm ms-2" role="status"
                                                              style={{width: '0.8rem', height: '0.8rem'}}></span>
                                                    )}
                                                </div>
                                                {description && (
                                                    <small style={{fontSize: '0.7rem', opacity: 0.85, lineHeight: '1.2'}}>
                                                        {description}
                                                    </small>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="text-center py-3">
                                    <i className="bi bi-inbox text-muted" style={{fontSize: '2rem'}}></i>
                                    <p className="text-muted mb-0 mt-2">No norms available.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Report Tables - Only show active norm */}
            <div className="row">
                <div className="col-12">
                    {/* Loading state */}
                    {loading && activeNormTab && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <div className="spinner-border text-primary mb-3" role="status" style={{width: '3rem', height: '3rem'}}>
                                    <span className="visually-hidden">Loading...</span>
                                </div>
                                <h5 className="text-muted">Loading {activeNormTab} Report...</h5>
                                <p className="text-muted small">Please wait while we fetch the data</p>
                            </div>
                        </div>
                    )}

                    {/* No data message after loading */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification && (!reportData.licenses_by_norm_notification[activeNormTab] || Object.keys(reportData.licenses_by_norm_notification[activeNormTab] || {}).length === 0) && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-inbox" style={{fontSize: '3rem', color: '#ccc'}}></i>
                                <h5 className="mt-3 text-muted">No licenses found for {activeNormTab}</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                            </div>
                        </div>
                    )}

                    {/* Show report data */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification?.[activeNormTab] && Object.keys(reportData.licenses_by_norm_notification[activeNormTab]).length > 0 && (
                        <div>
                            {/* Notifications within active norm */}
                            {Object.entries(reportData.licenses_by_norm_notification[activeNormTab]).sort().map(([notification, licenses]) => (
                                <div key={`${activeNormTab}-${notification}`} className="mb-4">
                                    <div className="card shadow-sm border-0">
                                        <div
                                            className="card-header bg-gradient text-primary d-flex justify-content-between align-items-center"
                                            style={{background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'}}>
                                            <div>
                                                <h5 className="mb-0">
                                                    <i className="bi bi-bell-fill me-2"></i>
                                                    Notification Number: {notification}
                                                    {notification === 'Unknown' && (
                                                        <span className="badge bg-warning text-dark ms-2"
                                                              title="Notification number is blank or missing">
                                                            <i className="bi bi-exclamation-triangle-fill me-1"></i>
                                                            Missing
                                                        </span>
                                                    )}
                                                </h5>
                                                <small className="opacity-75">
                                                    {licenses.length} License{licenses.length !== 1 ? 's' : ''}
                                                </small>
                                            </div>
                                            <span className="badge bg-white text-dark">{licenses.length}</span>
                                        </div>
                                        <div className="card-body p-0">
                                            <div className="table-responsive" style={{overflowX: 'auto'}}>
                                                <table className="table table-hover table-sm mb-0"
                                                       style={{tableLayout: 'auto', minWidth: '860px'}}>
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
                                                            minWidth: '120px'
                                                        }}>DFIA No
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '100px'
                                                        }}>DFIA Dt
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '100px'
                                                        }}>Expiry Dt
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '380px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '150px'
                                                        }}>Exporter
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '120px'
                                                        }}>Notif No
                                                        </th>
                                                        <th className="text-end" style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '100px'
                                                        }}>Total CIF
                                                        </th>
                                                        <th className="text-end" style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 11,
                                                            backgroundColor: '#f8f9fa',
                                                            minWidth: '110px',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid #dee2e6'
                                                        }}>Balance CIF
                                                        </th>
                                                        {reportData.items.filter(item => item.name).map(item => {
                                                            const colSpan = item.has_restriction ? 8 : 6;
                                                            return (
                                                                <th key={`${item.id}-qty`} colSpan={colSpan}
                                                                    className="text-center bg-info bg-opacity-10"
                                                                    style={{minWidth: '200px'}}>
                                                                    <i className="bi bi-box-seam me-1"></i>
                                                                    {item.name}
                                                                </th>
                                                            );
                                                        })}
                                                    </tr>
                                                    <tr className="table-secondary">
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '60px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '380px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 11,
                                                            backgroundColor: '#e2e3e5',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid #dee2e6'
                                                        }}></th>
                                                        {reportData.items.filter(item => item.name).map(item => (
                                                            <React.Fragment key={`${item.id}-headers`}>
                                                                <th style={{minWidth: '90px', fontSize: '0.85rem'}}>HSN
                                                                    Code
                                                                </th>
                                                                <th style={{
                                                                    minWidth: '150px',
                                                                    fontSize: '0.85rem'
                                                                }}>Description
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '90px',
                                                                    fontSize: '0.85rem'
                                                                }}>Total QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: '0.85rem'
                                                                }}>Allotted QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: '0.85rem'
                                                                }}>Debited QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '110px',
                                                                    fontSize: '0.85rem'
                                                                }}>Balance QTY
                                                                </th>
                                                                {item.has_restriction && (
                                                                    <>
                                                                        <th className="text-center" style={{
                                                                            minWidth: '90px',
                                                                            fontSize: '0.85rem'
                                                                        }}>Restriction %
                                                                        </th>
                                                                        <th className="text-end" style={{
                                                                            minWidth: '120px',
                                                                            fontSize: '0.85rem'
                                                                        }}>Restriction Val
                                                                        </th>
                                                                    </>
                                                                )}
                                                            </React.Fragment>
                                                        ))}
                                                    </tr>
                                                    </thead>
                                                    <tbody>
                                                    {licenses.map((license, idx) => (
                                                        <tr key={license.license_number} className="align-middle">
                                                            <td className="text-center fw-bold" style={{
                                                                position: 'sticky',
                                                                left: 0,
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>{idx + 1}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '60px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>{license.license_number}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '180px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>{formatDate(license.license_date)}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '280px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>{formatDate(license.license_expiry_date)}</td>
                                                            <td className="text-truncate" style={{
                                                                position: 'sticky',
                                                                left: '380px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff',
                                                                maxWidth: '150px'
                                                            }} title={license.exporter}>
                                                                {license.exporter}
                                                            </td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '530px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>
                                                                {license.notification_number}
                                                                {license.notification_number === 'Unknown' && (
                                                                    <i className="bi bi-exclamation-triangle-fill text-warning ms-1"
                                                                       title="Missing notification number"></i>
                                                                )}
                                                            </td>
                                                            <td className="text-end fw-semibold" style={{
                                                                position: 'sticky',
                                                                left: '650px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff'
                                                            }}>{license.total_cif.toFixed(2)}</td>
                                                            <td className="text-end fw-semibold text-success" style={{
                                                                position: 'sticky',
                                                                left: '750px',
                                                                zIndex: 1,
                                                                backgroundColor: '#fff',
                                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                borderRight: '2px solid #dee2e6'
                                                            }}>{license.balance_cif.toFixed(2)}</td>
                                                            {reportData.items.filter(item => item.name).map(item => {
                                                                const itemData = license.items[item.name] || {};
                                                                const hasData = itemData.quantity > 0;
                                                                return (
                                                                    <React.Fragment
                                                                        key={`${license.license_number}-${item.id}`}>
                                                                        <td className={hasData ? 'bg-light' : ''}>
                                                                            {itemData.hs_code || '-'}
                                                                        </td>
                                                                        <td className={`text-truncate ${hasData ? 'bg-light' : ''}`}
                                                                            style={{maxWidth: '180px'}}
                                                                            title={itemData.description || ''}>
                                                                            {itemData.description || '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light' : ''}`}>
                                                                            {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light fw-semibold text-primary' : ''}`}>
                                                                            {itemData.allotted_quantity ? itemData.allotted_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light' : ''}`} style={hasData ? {color: '#d97706'} : {}}>
                                                                            {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light text-success fw-semibold' : ''}`}>
                                                                            {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        {item.has_restriction && (
                                                                            <>
                                                                                <td className={`text-center ${hasData ? 'bg-light' : ''}`}>
                                                                                    {itemData.restriction !== null && itemData.restriction !== undefined ? (
                                                                                        <span
                                                                                            className="badge bg-info">{itemData.restriction}%</span>
                                                                                    ) : '-'}
                                                                                </td>
                                                                                <td className={`text-end ${hasData ? 'bg-light fw-semibold' : ''}`}>
                                                                                    {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                                </td>
                                                                            </>
                                                                        )}
                                                                    </React.Fragment>
                                                                );
                                                            })}
                                                        </tr>
                                                    ))}
                                                    <tr className="table-warning fw-bold" style={{
                                                        position: 'sticky',
                                                        bottom: 0,
                                                        backgroundColor: '#fff3cd'
                                                    }}>
                                                        <td className="text-uppercase" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 1,
                                                            backgroundColor: '#fff3cd'
                                                        }} colSpan="5">
                                                            <i className="bi bi-calculator me-2"></i>
                                                            TOTAL
                                                        </td>
                                                        <td style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 1,
                                                            backgroundColor: '#fff3cd'
                                                        }}></td>
                                                        <td className="text-end text-primary" style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 1,
                                                            backgroundColor: '#fff3cd'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.total_cif, 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-end text-success" style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 1,
                                                            backgroundColor: '#fff3cd',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid #dee2e6'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.balance_cif, 0).toFixed(2)}
                                                        </td>
                                                        {reportData.items.filter(item => item.name).map(item => {
                                                            const totalQty = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.quantity || 0);
                                                            }, 0);
                                                            const totalAllotted = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.allotted_quantity || 0);
                                                            }, 0);
                                                            const totalDebited = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.debited_quantity || 0);
                                                            }, 0);
                                                            const totalAvail = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.available_quantity || 0);
                                                            }, 0);
                                                            const totalRestrictionVal = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.restriction_value || 0);
                                                            }, 0);
                                                            return (
                                                                <React.Fragment key={`total-${item.id}`}>
                                                                    <td className="text-muted">-</td>
                                                                    <td className="text-muted">-</td>
                                                                    <td className="text-end">
                                                                        {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end text-primary">
                                                                        {totalAllotted > 0 ? totalAllotted.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end" style={{color: '#d97706'}}>
                                                                        {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end text-success">
                                                                        {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                                    </td>
                                                                    {item.has_restriction && (
                                                                        <>
                                                                            <td className="text-muted">-</td>
                                                                            <td className="text-end fw-bold">
                                                                                {totalRestrictionVal > 0 ? totalRestrictionVal.toFixed(2) : '-'}
                                                                            </td>
                                                                        </>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </tr>
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* Summary Table */}
                                            {(() => {
                                                const summary = calculateNotificationSummary(licenses);
                                                return (
                                                    <div className="mt-4 px-3 pb-3">
                                                        <h6 className="mb-3 text-primary">
                                                            <i className="bi bi-calculator me-2"></i>
                                                            Summary
                                                        </h6>
                                                        <div style={{maxWidth: '1200px'}}>
                                                            <table className="table table-bordered table-sm" style={{tableLayout: 'fixed', width: '1200px'}}>
                                                                <thead className="table-light">
                                                                <tr>
                                                                    <th style={{width: '100px'}}>Sr No</th>
                                                                    <th style={{width: '800px'}}>Item Name</th>
                                                                    <th className="text-end" style={{width: '300px'}}>Available Balance QTY</th>
                                                                </tr>
                                                                </thead>
                                                                <tbody>
                                                                {/* Opening Balance */}
                                                                <tr className="table-info">
                                                                    <td colSpan="2" className="text-center fw-bold">OPENING BALANCE</td>
                                                                    <td className="text-end fw-bold">
                                                                        {formatIndianNumber(summary.openingBalance, 2)}
                                                                    </td>
                                                                </tr>

                                                                {/* Regular Items */}
                                                                {Object.entries(summary.regularItems).map(([itemName, itemData], idx) => (
                                                                    <tr key={itemName}>
                                                                        <td className="text-center">{idx + 1}</td>
                                                                        <td className="fw-bold">{itemName}</td>
                                                                        <td className="text-end">
                                                                            {formatIndianNumber(itemData.available, 2)}
                                                                        </td>
                                                                    </tr>
                                                                ))}

                                                                {/* Restricted Items Grouped by Percentage */}
                                                                {Object.keys(summary.restrictedItemsByPercentage).length > 0 && (
                                                                    <>
                                                                        {Object.entries(summary.restrictedItemsByPercentage)
                                                                            .sort(([pctA], [pctB]) => parseFloat(pctA) - parseFloat(pctB))
                                                                            .map(([percentage, groupData], groupIdx) => {
                                                                                const startIdx = Object.keys(summary.regularItems).length +
                                                                                    Object.entries(summary.restrictedItemsByPercentage)
                                                                                        .slice(0, groupIdx)
                                                                                        .reduce((acc, [, data]) => acc + Object.keys(data.items).length, 0);

                                                                                return (
                                                                                    <React.Fragment key={percentage}>
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan="3" className="text-center fw-bold">
                                                                                                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                                                                                                RESTRICTED ITEMS - {percentage}%
                                                                                            </td>
                                                                                        </tr>
                                                                                        {Object.entries(groupData.items).map(([itemName, itemData], idx) => (
                                                                                            <tr key={itemName} className="table-light">
                                                                                                <td className="text-center">{startIdx + idx + 1}</td>
                                                                                                <td className="fw-bold">{itemName}</td>
                                                                                                <td className="text-end">
                                                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                                                </td>
                                                                                            </tr>
                                                                                        ))}
                                                                                        {/* Balance for this restriction percentage (shared across all items) */}
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan="2" className="text-center fw-bold">Balance {percentage}%</td>
                                                                                            <td className="text-end fw-bold">
                                                                                                {formatIndianNumber(groupData.sharedRestrictionValue, 2)}
                                                                                            </td>
                                                                                        </tr>
                                                                                    </React.Fragment>
                                                                                );
                                                                            })}
                                                                    </>
                                                                )}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    </div>
                                </div>
                            ))}

                            {/* Notes and Conditions Section */}
                            {activeNormTab && reportData?.norm_notes_conditions?.[activeNormTab] && (
                                reportData.norm_notes_conditions[activeNormTab].notes?.length > 0 || reportData.norm_notes_conditions[activeNormTab].conditions?.length > 0
                            ) && (
                                <div className="card shadow-sm border-0 mb-4">
                                    <div className="card-header bg-light">
                                        <h5 className="mb-0">
                                            <i className="bi bi-info-circle-fill me-2 text-info"></i>
                                            SION Norm {activeNormTab} - Notes & Conditions
                                        </h5>
                                    </div>
                                    <div className="card-body">
                                        <div className="row">
                                            {/* Notes Section */}
                                            {reportData.norm_notes_conditions[activeNormTab].notes?.length > 0 && (
                                                <div className="col-md-6 mb-3 mb-md-0">
                                                    <h6 className="text-primary mb-3">
                                                        <i className="bi bi-sticky-fill me-2"></i>
                                                        Notes
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData.norm_notes_conditions[activeNormTab].notes
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((note, index) => (
                                                                <div key={index} className="list-group-item border-start border-primary border-3">
                                                                    <div className="d-flex w-100 justify-content-between align-items-start">
                                                                        <span className="badge bg-primary rounded-pill me-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow-1" style={{whiteSpace: 'pre-wrap'}}>
                                                                            {note.note_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Conditions Section */}
                                            {reportData.norm_notes_conditions[activeNormTab].conditions?.length > 0 && (
                                                <div className="col-md-6">
                                                    <h6 className="text-warning mb-3">
                                                        <i className="bi bi-exclamation-triangle-fill me-2"></i>
                                                        Conditions
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData.norm_notes_conditions[activeNormTab].conditions
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((condition, index) => (
                                                                <div key={index} className="list-group-item border-start border-warning border-3">
                                                                    <div className="d-flex w-100 justify-content-between align-items-start">
                                                                        <span className="badge bg-warning text-dark rounded-pill me-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow-1" style={{whiteSpace: 'pre-wrap'}}>
                                                                            {condition.condition_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* No norm selected message */}
                    {!loading && !activeNormTab && availableNorms.length > 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-tag" style={{fontSize: '3rem', color: '#667eea'}}></i>
                                <h5 className="mt-3 text-primary">Select a Norm to View Report</h5>
                                <p className="text-muted">Click on any norm tab above to load the report data</p>
                            </div>
                        </div>
                    )}

                    {/* No norms available */}
                    {!loading && availableNorms.length === 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-inbox" style={{fontSize: '3rem', color: '#ccc'}}></i>
                                <h5 className="mt-3 text-muted">No Norms Available</h5>
                                <p className="text-muted">No active norm classes found in the system.</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
